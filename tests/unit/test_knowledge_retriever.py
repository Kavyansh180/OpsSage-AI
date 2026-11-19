from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from pymongo.errors import OperationFailure

from backend.app.config import Settings
from backend.app.models.user import UserInDB, UserRole
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.knowledge_retriever import KnowledgeRetrievalService


class DummyEncoder:
    def encode(self, texts, **kwargs):
        if isinstance(texts, str):
            return [1.0] + [0.0] * 383
        return [[1.0] + [0.0] * 383 for _ in texts]


@pytest.fixture(autouse=True)
def mock_embedding():
    EmbeddingService.set_mock_model(DummyEncoder())
    yield
    EmbeddingService.reset_model()


@pytest.fixture
def test_user():
    return UserInDB(
        id="user-123",
        email="eng@example.com",
        full_name="Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_admin():
    return UserInDB(
        id="admin-999",
        email="admin@example.com",
        full_name="Admin",
        hashed_password="pw",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_cosine_similarity_math():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert pytest.approx(KnowledgeRetrievalService._cosine_similarity(v1, v2), 0.001) == 1.0
    assert pytest.approx(KnowledgeRetrievalService._cosine_similarity(v1, v3), 0.001) == 0.0


def test_build_query_text_sanitizes_credentials():
    service = KnowledgeRetrievalService(db=MagicMock())
    incident = {
        "service_name": "billing",
        "environment": "production",
        "title": "Auth failure on https://user:Secret123@api.billing.internal",
    }
    logs = [
        {"message": "Bearer abc1234567890def connection timed out"}
    ]
    query = service.build_query_text(incident, logs)
    assert "Secret123" not in query
    assert "abc1234567890def" not in query
    assert "Service: billing" in query
    assert "Environment: production" in query


@pytest.mark.asyncio
async def test_search_atlas_vector_search_pipeline(test_user):
    mock_db = MagicMock()
    mock_kb = MagicMock()

    # Return sample vector search candidate
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[
        {
            "knowledge_id": "KB-001",
            "source_incident_id": "INC-HIST-1",
            "score": 0.88,
            "service_name": "billing",
            "environment": "production",
            "title": "Stripe timeout",
            "has_verified_resolution": True,
            "confirmed_resolution": "Increased HTTP client timeout to 30s",
        },
        {
            "knowledge_id": "KB-002",
            "source_incident_id": "INC-HIST-2",
            "score": 0.50,  # Below min_similarity cutoff of 0.65
            "service_name": "billing",
            "environment": "production",
            "title": "Unrelated issue",
        },
    ])
    mock_kb.aggregate = AsyncMock(return_value=mock_cursor)
    mock_db.__getitem__.return_value = mock_kb

    service = KnowledgeRetrievalService(
        db=mock_db,
        settings=Settings(RAG_MIN_SIMILARITY=0.65, RAG_TOP_K=3),
    )

    results = await service._search_atlas_vector_search(
        query_vector=[1.0] + [0.0] * 383,
        user=test_user,
        top_k=3,
        min_similarity=0.65,
    )

    # KB-002 with score 0.50 must be filtered out by min_similarity
    assert len(results) == 1
    assert results[0]["knowledge_id"] == "KB-001"

    # Verify $vectorSearch stage in aggregation pipeline
    pipeline = mock_kb.aggregate.call_args[0][0]
    vs_stage = pipeline[0]["$vectorSearch"]
    assert vs_stage["index"] == "vector_index_knowledge_base"
    assert vs_stage["path"] == "embedding"
    assert vs_stage["filter"]["user_id"] == test_user.id


@pytest.mark.asyncio
async def test_retrieve_similar_incidents_excludes_current_incident(test_user):
    mock_db = MagicMock()
    mock_kb = MagicMock()

    current_inc_id = "INC-CURRENT-100"

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[
        {
            "knowledge_id": "KB-CURRENT",
            "source_incident_id": current_inc_id,  # SAME as current incident
            "score": 0.99,
            "title": "Self incident",
        },
        {
            "knowledge_id": "KB-HIST",
            "source_incident_id": "INC-HIST-500",  # Prior incident
            "score": 0.85,
            "title": "Prior database crash",
            "service_name": "db-service",
            "environment": "production",
            "has_verified_resolution": False,
        },
    ])
    mock_kb.aggregate = AsyncMock(return_value=mock_cursor)
    mock_db.__getitem__.return_value = mock_kb

    service = KnowledgeRetrievalService(db=mock_db)
    result = await service.retrieve_similar_incidents(
        incident={"incident_id": current_inc_id, "service_name": "db-service", "title": "Crash"},
        user=test_user,
    )

    assert result.status == "SUCCESS"
    assert len(result.similar_incidents) == 1
    assert result.similar_incidents[0].source_incident_id == "INC-HIST-500"
    assert result.similar_incidents[0].source_incident_id != current_inc_id


@pytest.mark.asyncio
async def test_retrieve_similar_incidents_handles_vector_search_failure(test_user):
    mock_db = MagicMock()
    mock_kb = MagicMock()

    # Simulate missing index OperationFailure
    mock_kb.aggregate.side_effect = OperationFailure("Index vector_index_knowledge_base not found")
    mock_db.__getitem__.return_value = mock_kb

    service = KnowledgeRetrievalService(db=mock_db, allow_in_memory_fallback=False)
    result = await service.retrieve_similar_incidents(
        incident={"incident_id": "INC-001", "service_name": "svc", "title": "Err"},
        user=test_user,
    )

    assert result.status == "UNAVAILABLE"
    assert "unavailable" in result.error_message.lower()
    assert len(result.similar_incidents) == 0
