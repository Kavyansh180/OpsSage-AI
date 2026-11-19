from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.main import app
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.knowledge import KnowledgeIndexResponse, KnowledgeSearchResponse


@pytest.fixture
def mock_engineer():
    return UserInDB(
        id="user-eng",
        email="eng@example.com",
        full_name="DevOps Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_viewer():
    return UserInDB(
        id="user-view",
        email="viewer@example.com",
        full_name="Viewer User",
        hashed_password="pw",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_search_knowledge_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/api/v1/knowledge/search", json={"query": "database error"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_index_historical_incidents_viewer_forbidden(mock_viewer):
    app.dependency_overrides[get_current_user] = lambda: mock_viewer
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/v1/knowledge/index",
                json={"limit": 10},
                headers={"Authorization": "Bearer mock-token"},
            )
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_index_historical_incidents_engineer_success(mock_engineer):
    app.dependency_overrides[get_current_user] = lambda: mock_engineer
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    sample_index_resp = KnowledgeIndexResponse(
        total_eligible=5,
        indexed_count=3,
        skipped_count=2,
        failed_count=0,
        indexed_knowledge_ids=["KB-1", "KB-2", "KB-3"],
        errors=[],
    )

    try:
        with patch("backend.app.services.knowledge_indexer.KnowledgeIndexer.index_incidents_batch", new_callable=AsyncMock) as mock_batch:
            mock_batch.return_value = sample_index_resp

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    "/api/v1/knowledge/index",
                    json={"limit": 5},
                    headers={"Authorization": "Bearer mock-token"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["indexed_count"] == 3
                assert data["skipped_count"] == 2
                assert len(data["indexed_knowledge_ids"]) == 3
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_knowledge_document_omits_raw_embedding(mock_engineer):
    app.dependency_overrides[get_current_user] = lambda: mock_engineer

    mock_db = MagicMock()
    mock_kb = MagicMock()

    # Document stored in MongoDB contains the 384d embedding
    mock_kb.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "knowledge_id": "KB-TEST-001",
        "source_incident_id": "INC-001",
        "user_id": mock_engineer.id,
        "service_name": "payments",
        "environment": "production",
        "error_signature": "sig-001",
        "title": "Payment crash",
        "diagnostic_summary": "HTTP 500",
        "has_verified_resolution": False,
        "confirmed_resolution": None,
        "embedding": [0.123] * 384,  # RAW VECTOR
        "source_metadata": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    mock_db.__getitem__.return_value = mock_kb
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(
                "/api/v1/knowledge/KB-TEST-001",
                headers={"Authorization": "Bearer mock-token"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["knowledge_id"] == "KB-TEST-001"
            assert data["title"] == "Payment crash"
            # CRITICAL CHECK: Raw embedding vector MUST NOT be exposed in API response
            assert "embedding" not in data
    finally:
        app.dependency_overrides.clear()
