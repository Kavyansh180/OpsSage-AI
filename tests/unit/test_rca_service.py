from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest

from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.models.analysis import ConfidenceLevel
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.analysis import AnalysisResponse, StructuredRCAResponse
from backend.app.services.llm.base import LLMProvider
from backend.app.services.rca_service import RCAService


class MockLLMProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "mock_gemini"

    @property
    def model_name(self) -> str:
        return "mock-flash"

    async def generate_text(self, prompt: str, system_instruction=None) -> str:
        return "mock text"

    async def generate_structured(self, prompt: str, schema_cls, system_instruction=None):
        instance = schema_cls(
            probable_root_cause="PostgreSQL connection exhaustion",
            explanation="Concurrent connection count exceeded max_connections = 100.",
            supporting_evidence=["FATAL: remaining connection slots are reserved"],
            contributing_factors=["Connection pooler bypassed"],
            confidence_level=ConfidenceLevel.HIGH,
            recommended_actions=["Configure PgBouncer", "Restart service"],
            limitations=[],
        )
        return instance, '{"raw": "mock"}'


@pytest.fixture
def test_user():
    return UserInDB(
        id="user-1",
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


@pytest.mark.asyncio
async def test_rca_service_analyze_incident_persists_record(test_user):
    mock_db = MagicMock()
    mock_incidents = MagicMock()
    mock_logs = MagicMock()
    mock_analyses = MagicMock()

    mock_incidents.find_one = AsyncMock(return_value={
        "incident_id": "INC-20261118-001",
        "user_id": "user-1",
        "service_name": "checkout-svc",
        "environment": "production",
        "title": "Database connection error",
        "related_log_ids": [],
    })

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_cursor.sort.return_value = mock_cursor
    mock_logs.find.return_value = mock_cursor

    inserted_oid = ObjectId()
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = inserted_oid
    mock_analyses.insert_one = AsyncMock(return_value=mock_insert_result)

    def get_collection(name):
        if name == "incidents":
            return mock_incidents
        elif name == "logs":
            return mock_logs
        elif name == "analyses":
            return mock_analyses
        return MagicMock()

    mock_db.__getitem__.side_effect = get_collection

    mock_provider = MockLLMProvider()

    response = await RCAService.analyze_incident(
        db=mock_db,
        user=test_user,
        incident_id="INC-20261118-001",
        provider=mock_provider,
    )

    assert isinstance(response, AnalysisResponse)
    assert response.analysis_id.startswith("RCA-")
    assert response.incident_id == "INC-20261118-001"
    assert response.user_id == "user-1"
    assert response.probable_root_cause == "PostgreSQL connection exhaustion"
    assert response.confidence_level == ConfidenceLevel.HIGH
    assert response.provider == "mock_gemini"
    assert response.model == "mock-flash"

    # Verify persistence called once on analyses collection
    mock_analyses.insert_one.assert_called_once()
    saved_doc = mock_analyses.insert_one.call_args[0][0]
    assert saved_doc["analysis_id"] == response.analysis_id
    assert saved_doc["incident_id"] == "INC-20261118-001"


@pytest.mark.asyncio
async def test_rca_service_get_incident_analyses_history(test_user):
    mock_db = MagicMock()
    mock_incidents = MagicMock()
    mock_analyses = MagicMock()

    mock_incidents.find_one = AsyncMock(return_value={
        "incident_id": "INC-001",
        "user_id": "user-1",
    })

    mock_analyses.count_documents = AsyncMock(return_value=2)
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=[
        {
            "_id": ObjectId(),
            "analysis_id": "RCA-002",
            "incident_id": "INC-001",
            "user_id": "user-1",
            "probable_root_cause": "Second run diagnosis",
            "explanation": "Explanation",
            "supporting_evidence": [],
            "contributing_factors": [],
            "confidence_level": "HIGH",
            "recommended_actions": [],
            "limitations": [],
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "evidence_log_count": 5,
            "redacted_secrets_count": 0,
            "created_at": datetime(2026, 11, 18, 11, 0, 0, tzinfo=timezone.utc),
        },
        {
            "_id": ObjectId(),
            "analysis_id": "RCA-001",
            "incident_id": "INC-001",
            "user_id": "user-1",
            "probable_root_cause": "First run diagnosis",
            "explanation": "Explanation",
            "supporting_evidence": [],
            "contributing_factors": [],
            "confidence_level": "LOW",
            "recommended_actions": [],
            "limitations": [],
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "evidence_log_count": 2,
            "redacted_secrets_count": 0,
            "created_at": datetime(2026, 11, 18, 10, 0, 0, tzinfo=timezone.utc),
        },
    ])
    mock_analyses.find.return_value = mock_cursor

    mock_db.__getitem__.side_effect = lambda name: mock_incidents if name == "incidents" else mock_analyses

    paginated = await RCAService.get_incident_analyses(
        db=mock_db,
        user=test_user,
        incident_id="INC-001",
        limit=10,
        offset=0,
    )

    assert paginated.total == 2
    assert len(paginated.items) == 2
    assert paginated.items[0].analysis_id == "RCA-002"
    assert paginated.items[1].analysis_id == "RCA-001"


@pytest.mark.asyncio
async def test_rca_service_get_analysis_by_id_tenant_isolation(test_user):
    mock_db = MagicMock()
    mock_analyses = MagicMock()

    # Document belongs to "other-tenant"
    mock_analyses.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "analysis_id": "RCA-SECRET-1",
        "user_id": "other-tenant",
    })
    mock_db.__getitem__.return_value = mock_analyses

    with pytest.raises(ResourceNotFoundError):
        await RCAService.get_analysis_by_id(
            db=mock_db,
            user=test_user,
            analysis_id="RCA-SECRET-1",
        )
