from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest

from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.models.knowledge import HistoricalAnalysisSummary
from backend.app.models.user import UserInDB, UserRole
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.knowledge_indexer import KnowledgeIndexer


class DummyEncoder:
    def encode(self, texts, **kwargs):
        if isinstance(texts, str):
            return [0.1] * 384
        return [[0.1] * 384 for _ in texts]


@pytest.fixture(autouse=True)
def mock_embedding():
    EmbeddingService.set_mock_model(DummyEncoder())
    yield
    EmbeddingService.reset_model()


@pytest.fixture
def test_engineer():
    return UserInDB(
        id="tenant-1",
        email="eng@example.com",
        full_name="Eng",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_admin():
    return UserInDB(
        id="admin-1",
        email="admin@example.com",
        full_name="Admin",
        hashed_password="pw",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_construct_embedding_text_sanitizes_credentials():
    text = KnowledgeIndexer.construct_embedding_text(
        service_name="payment",
        environment="prod",
        title="PostgreSQL connection failed for postgresql://admin:SecretPass123@db:5432/db",
        diagnostic_summary="Authorization failed for Bearer token1234567890abcdef",
        historical_analysis=HistoricalAnalysisSummary(
            probable_root_cause="Bad credentials",
            explanation="Password rotated",
            recommended_actions=["Update secrets"],
            confidence_level="HIGH",
        ),
        confirmed_resolution="Updated vault secret",
    )
    assert "SecretPass123" not in text
    assert "token1234567890abcdef" not in text
    assert "[REDACTED_USER]:[REDACTED_PASSWORD]@db:5432/db" in text
    assert "Verified Resolution: Updated vault secret" in text


@pytest.mark.asyncio
async def test_index_incident_distinguishes_ai_hypothesis_from_confirmed_resolution(test_engineer):
    mock_db = MagicMock()
    mock_incidents = MagicMock()
    mock_analyses = MagicMock()
    mock_kb = MagicMock()
    mock_logs = MagicMock()

    # Incident has NO confirmed resolution
    mock_incidents.find_one = AsyncMock(return_value={
        "incident_id": "INC-001",
        "user_id": test_engineer.id,
        "service_name": "order-service",
        "environment": "production",
        "error_signature": "sig-123",
        "title": "Payment gateway timeout",
        "related_log_ids": [],
    })

    # Historical RCA exists (AI hypothesis)
    mock_analyses.find_one = AsyncMock(return_value={
        "analysis_id": "RCA-001",
        "probable_root_cause": "AI Hypothesis: Upstream rate limit",
        "explanation": "Stripe returned HTTP 429",
        "recommended_actions": ["Implement backoff"],
        "confidence_level": "MEDIUM",
    })

    mock_kb.find_one = AsyncMock(return_value=None)  # Not yet indexed
    mock_kb.find_one_and_update = AsyncMock(return_value={
        "knowledge_id": "KB-NEW-1",
        "source_incident_id": "INC-001",
        "user_id": test_engineer.id,
        "service_name": "order-service",
        "has_verified_resolution": False,
        "confirmed_resolution": None,
        "historical_analysis": {
            "probable_root_cause": "AI Hypothesis: Upstream rate limit",
        },
    })

    mock_db.__getitem__.side_effect = lambda name: {
        "incidents": mock_incidents,
        "analyses": mock_analyses,
        "knowledge_base": mock_kb,
        "logs": mock_logs,
    }.get(name, MagicMock())

    indexer = KnowledgeIndexer(db=mock_db)
    result = await indexer.index_incident("INC-001", test_engineer)

    # CRITICAL CHECK: AI hypothesis is NOT treated as confirmed resolution
    assert result["has_verified_resolution"] is False
    assert result["confirmed_resolution"] is None
    assert result["historical_analysis"]["probable_root_cause"] == "AI Hypothesis: Upstream rate limit"

    # Verify upsert payload
    upsert_args = mock_kb.find_one_and_update.call_args[0]
    set_fields = upsert_args[1]["$set"]
    assert set_fields["has_verified_resolution"] is False
    assert set_fields["confirmed_resolution"] is None
    assert len(set_fields["embedding"]) == 384


@pytest.mark.asyncio
async def test_index_incident_with_verified_engineer_resolution(test_engineer):
    mock_db = MagicMock()
    mock_incidents = MagicMock()
    mock_analyses = MagicMock()
    mock_kb = MagicMock()
    mock_logs = MagicMock()

    mock_incidents.find_one = AsyncMock(return_value={
        "incident_id": "INC-002",
        "user_id": test_engineer.id,
        "service_name": "auth-service",
        "environment": "production",
        "title": "Auth failure",
        "confirmed_resolution": "Flushed stale Redis sessions and rotated JWT signing key",
    })

    mock_analyses.find_one = AsyncMock(return_value=None)
    mock_kb.find_one = AsyncMock(return_value=None)
    mock_kb.find_one_and_update = AsyncMock(return_value={
        "knowledge_id": "KB-002",
        "has_verified_resolution": True,
        "confirmed_resolution": "Flushed stale Redis sessions and rotated JWT signing key",
    })

    mock_db.__getitem__.side_effect = lambda name: {
        "incidents": mock_incidents,
        "analyses": mock_analyses,
        "knowledge_base": mock_kb,
        "logs": mock_logs,
    }.get(name, MagicMock())

    indexer = KnowledgeIndexer(db=mock_db)
    result = await indexer.index_incident("INC-002", test_engineer)

    assert result["has_verified_resolution"] is True
    assert "Flushed stale Redis" in result["confirmed_resolution"]


@pytest.mark.asyncio
async def test_index_incident_tenant_isolation(test_engineer):
    mock_db = MagicMock()
    mock_incidents = MagicMock()
    mock_incidents.find_one = AsyncMock(return_value={
        "incident_id": "INC-OTHER",
        "user_id": "other-tenant",
    })
    mock_db.__getitem__.return_value = mock_incidents

    indexer = KnowledgeIndexer(db=mock_db)
    with pytest.raises(ResourceNotFoundError):
        await indexer.index_incident("INC-OTHER", test_engineer)
