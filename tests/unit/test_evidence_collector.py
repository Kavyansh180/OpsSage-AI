from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest

from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.models.user import UserInDB, UserRole
from backend.app.services.evidence_collector import EvidenceCollector


@pytest.fixture
def test_engineer():
    return UserInDB(
        id="user-123",
        email="engineer@example.com",
        full_name="Test Engineer",
        hashed_password="hashedpassword",
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
        full_name="Test Admin",
        hashed_password="hashedpassword",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_evidence_collector_incident_not_found(test_engineer):
    mock_db = MagicMock()
    mock_incidents = MagicMock()
    mock_incidents.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.return_value = mock_incidents

    collector = EvidenceCollector(mock_db)
    with pytest.raises(ResourceNotFoundError):
        await collector.collect_evidence("INC-NONEXISTENT", test_engineer)


@pytest.mark.asyncio
async def test_evidence_collector_tenant_isolation(test_engineer):
    mock_db = MagicMock()
    mock_incidents = MagicMock()
    # Incident belongs to "other-user", but caller is "user-123"
    mock_incidents.find_one = AsyncMock(return_value={
        "incident_id": "INC-001",
        "user_id": "other-user",
        "title": "Error",
    })
    mock_db.__getitem__.side_effect = lambda name: mock_incidents if name == "incidents" else MagicMock()

    collector = EvidenceCollector(mock_db)
    with pytest.raises(ResourceNotFoundError):
        await collector.collect_evidence("INC-001", test_engineer)


@pytest.mark.asyncio
async def test_evidence_collector_admin_cross_tenant_access(test_admin):
    mock_db = MagicMock()
    mock_incidents = MagicMock()
    mock_logs = MagicMock()

    log_oid = ObjectId()
    mock_incidents.find_one = AsyncMock(return_value={
        "incident_id": "INC-001",
        "user_id": "tenant-xyz",
        "service_name": "checkout",
        "environment": "production",
        "title": "Database connection timeout",
        "related_log_ids": [str(log_oid)],
    })

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[
        {
            "_id": log_oid,
            "user_id": "tenant-xyz",
            "service_name": "checkout",
            "environment": "production",
            "level": "ERROR",
            "message": "Connection to postgresql://user:pass123@db:5432/app failed",
            "normalized_message": "Connection failed",
            "timestamp": datetime(2026, 11, 18, 10, 0, 0, tzinfo=timezone.utc),
        }
    ])
    mock_logs.find.return_value = mock_cursor

    mock_db.__getitem__.side_effect = lambda name: mock_incidents if name == "incidents" else mock_logs

    collector = EvidenceCollector(mock_db)
    bundle = await collector.collect_evidence("INC-001", test_admin)

    assert bundle.evidence_log_count == 1
    assert bundle.redacted_secrets_count >= 1
    # Check that secrets in the log were redacted
    assert "pass123" not in bundle.logs[0]["message"]
    assert "[REDACTED_USER]:[REDACTED_PASSWORD]@db:5432/app" in bundle.logs[0]["message"]


@pytest.mark.asyncio
async def test_evidence_collector_chronological_sorting_and_truncation(test_engineer):
    mock_db = MagicMock()
    mock_incidents = MagicMock()
    mock_logs = MagicMock()

    oids = [ObjectId() for _ in range(5)]
    mock_incidents.find_one = AsyncMock(return_value={
        "incident_id": "INC-002",
        "user_id": "user-123",
        "service_name": "api",
        "environment": "prod",
        "title": "Crash",
        "related_log_ids": [str(oid) for oid in oids],
    })

    # Return logs out of order
    unordered_logs = [
        {
            "_id": oids[0],
            "timestamp": datetime(2026, 11, 18, 10, 5, 0),
            "message": "Log 3 (newest)",
            "level": "ERROR",
        },
        {
            "_id": oids[1],
            "timestamp": datetime(2026, 11, 18, 10, 1, 0),
            "message": "Log 1 (oldest)",
            "level": "INFO",
        },
        {
            "_id": oids[2],
            "timestamp": datetime(2026, 11, 18, 10, 3, 0),
            "message": "Log 2 (middle)",
            "level": "WARN",
        },
    ]

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=unordered_logs)
    mock_logs.find.return_value = mock_cursor
    mock_db.__getitem__.side_effect = lambda name: mock_incidents if name == "incidents" else mock_logs

    collector = EvidenceCollector(mock_db)
    bundle = await collector.collect_evidence("INC-002", test_engineer, max_evidence_logs=2)

    # Must be truncated to 2 and ordered chronologically
    assert bundle.evidence_log_count == 2
    assert "Log 2" in bundle.logs[0]["message"]
    assert "Log 3" in bundle.logs[1]["message"]
