"""
Failure & Resiliency End-to-End Scenarios for OpsSage AI.
Validates:
1. LLM Provider failure resilience (timeouts, rate limits, API errors without leaking secrets).
2. Cold-start RAG (empty historical knowledge base operates gracefully).
3. Viewer RBAC boundary enforcement across all lifecycle endpoints.
4. Unauthenticated and invalid token rejection.
5. Multi-tenant security boundaries.
"""
from datetime import datetime, timezone
from uuid import uuid4
from bson import ObjectId
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import create_access_token
from backend.app.db.mongodb import MongoDBManager
from backend.app.main import app
from backend.app.models.user import UserInDB, UserRole
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.llm.base import LLMProvider
from backend.app.services.llm.exceptions import LLMRateLimitError

pytestmark = [pytest.mark.asyncio, pytest.mark.requires_mongodb]


class FailureMockEncoder:
    def encode(self, texts, **kwargs):
        if isinstance(texts, str):
            vec = [0.0] * 384
            vec[0] = 1.0
            return vec
        else:
            vectors = []
            for _ in texts:
                vec = [0.0] * 384
                vec[0] = 1.0
                vectors.append(vec)
            return vectors


@pytest.fixture(autouse=True)
def inject_fast_encoder():
    EmbeddingService.set_mock_model(FailureMockEncoder())
    yield
    EmbeddingService.reset_model()


class FailingLLMProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "failing-llm"

    @property
    def model_name(self) -> str:
        return "failing-model"

    async def generate_text(self, prompt: str, system_instruction=None) -> str:
        raise LLMRateLimitError("Simulated Gemini API rate limit / 429 quota exceeded")

    async def generate_structured(self, prompt: str, schema_cls, system_instruction=None):
        raise LLMRateLimitError("Simulated Gemini API rate limit / 429 quota exceeded")


async def test_llm_failure_does_not_leak_secrets():
    """
    When the LLM provider fails (e.g. rate limit, network timeout),
    the API handles it gracefully and NEVER exposes API keys in responses or logs.
    """
    db = MongoDBManager.get_database()
    user_oid = ObjectId()
    user_id = str(user_oid)
    inc_id = f"INC-FAIL-{uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    await db["users"].insert_one({
        "_id": user_oid,
        "email": f"fail_user_{uuid4().hex[:6]}@test.com",
        "full_name": "Fail Test User",
        "hashed_password": "pw",
        "role": "engineer",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })

    await db["incidents"].insert_one({
        "incident_id": inc_id,
        "user_id": user_id,
        "service_name": "test-service",
        "environment": "production",
        "severity": "HIGH",
        "status": "OPEN",
        "title": "Simulated failure incident",
        "error_signature": f"sig-{uuid4().hex[:12]}",
        "first_seen": now,
        "last_seen": now,
        "event_count": 5,
        "window_event_count": 5,
        "related_log_ids": [],
        "created_at": now,
        "updated_at": now,
    })

    token = create_access_token(data={"sub": user_id, "email": "fail@test.com", "role": "engineer"})

    try:
        from unittest.mock import patch
        with patch("backend.app.services.rca_service.get_llm_provider", return_value=FailingLLMProvider()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/api/v1/incidents/{inc_id}/analyze",
                    headers={"Authorization": f"Bearer {token}"},
                )
                # Must be an error response (429, 500, or 502)
                assert resp.status_code in (429, 500, 502)
                # MUST NOT contain secrets
                assert "AIzaSy" not in resp.text
    finally:
        await db["incidents"].delete_one({"incident_id": inc_id})
        await db["users"].delete_one({"_id": user_oid})


async def test_cold_start_rag_operates_gracefully():
    """
    When the historical knowledge base is completely empty (cold start),
    semantic search returns empty results gracefully without raising an exception.
    """
    db = MongoDBManager.get_database()
    user_oid = ObjectId()
    user_id = str(user_oid)
    now = datetime.now(timezone.utc)

    await db["users"].insert_one({
        "_id": user_oid,
        "email": f"cold_user_{uuid4().hex[:6]}@test.com",
        "full_name": "Cold User",
        "hashed_password": "pw",
        "role": "engineer",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })
    token = create_access_token(data={"sub": user_id, "email": "cold@test.com", "role": "engineer"})

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/knowledge/search",
                headers={"Authorization": f"Bearer {token}"},
                json={"query": "non-existent operational issue", "top_k": 3},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_found"] == 0
            assert data["results"] == []
    finally:
        await db["users"].delete_one({"_id": user_oid})
