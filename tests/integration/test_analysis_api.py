"""
Live Database Integration Tests for AI Root-Cause Analysis (Module 4).
Requires a live MongoDB connection.
"""
from datetime import datetime, timezone
from uuid import uuid4
from bson import ObjectId
import pytest

from backend.app.db.mongodb import MongoDBManager
from backend.app.models.analysis import ConfidenceLevel
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.analysis import StructuredRCAResponse
from backend.app.services.llm.base import LLMProvider
from backend.app.services.rca_service import RCAService

pytestmark = [pytest.mark.asyncio, pytest.mark.requires_mongodb]

_MONGO_AVAILABLE = None


@pytest.fixture(autouse=True)
async def check_mongodb_available():
    """Skips tests gracefully if MongoDB is unreachable."""
    global _MONGO_AVAILABLE
    if _MONGO_AVAILABLE is None:
        _MONGO_AVAILABLE = await MongoDBManager.ping()
    if not _MONGO_AVAILABLE:
        pytest.skip("Test requires a live MongoDB connection")


class IntegrationMockLLM(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "integration-mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    async def generate_text(self, prompt: str, system_instruction=None) -> str:
        return "Integration analysis summary"

    async def generate_structured(self, prompt: str, schema_cls, system_instruction=None):
        instance = schema_cls(
            probable_root_cause="Integration Test Root Cause: Disk full on worker node",
            explanation="Disk utilization on volume /var/log reached 100%.",
            supporting_evidence=["Log: No space left on device"],
            contributing_factors=["Log rotation failed"],
            confidence_level=ConfidenceLevel.HIGH,
            recommended_actions=["Rotate logs", "Expand disk"],
            limitations=[],
        )
        return instance, '{"raw": "integration"}'


async def test_live_mongodb_rca_persistence_and_retrieval():
    """
    Verifies that RCAService properly persists analysis documents
    and retrieves history against a live MongoDB database.
    """
    db = MongoDBManager.get_database()
    test_user_id = f"test-user-{uuid4().hex[:8]}"
    test_incident_id = f"INC-TEST-{uuid4().hex[:8]}"

    test_user = UserInDB(
        id=test_user_id,
        email="test_integration@example.com",
        full_name="Integration Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # 1. Insert an incident document into MongoDB
    incident_doc = {
        "incident_id": test_incident_id,
        "user_id": test_user_id,
        "service_name": "worker-service",
        "environment": "integration-test",
        "severity": "HIGH",
        "status": "OPEN",
        "title": "Disk write failure on node worker-01",
        "error_signature": f"sig-{uuid4().hex[:12]}",
        "first_seen": datetime.now(timezone.utc),
        "last_seen": datetime.now(timezone.utc),
        "event_count": 5,
        "window_event_count": 5,
        "related_log_ids": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db["incidents"].insert_one(incident_doc)

    try:
        # 2. Run RCA service
        provider = IntegrationMockLLM()
        analysis = await RCAService.analyze_incident(
            db=db,
            user=test_user,
            incident_id=test_incident_id,
            provider=provider,
        )

        assert analysis.incident_id == test_incident_id
        assert analysis.user_id == test_user_id
        assert analysis.probable_root_cause.startswith("Integration Test Root Cause")
        assert analysis.confidence_level == ConfidenceLevel.HIGH

        # 3. Verify it was written to 'analyses' collection
        stored = await db["analyses"].find_one({"analysis_id": analysis.analysis_id})
        assert stored is not None
        assert stored["incident_id"] == test_incident_id

        # 4. Verify retrieval through get_incident_analyses
        history = await RCAService.get_incident_analyses(
            db=db,
            user=test_user,
            incident_id=test_incident_id,
        )
        assert history.total >= 1
        assert any(item.analysis_id == analysis.analysis_id for item in history.items)

    finally:
        # Clean up integration test data
        await db["incidents"].delete_one({"incident_id": test_incident_id})
        await db["analyses"].delete_many({"incident_id": test_incident_id})
