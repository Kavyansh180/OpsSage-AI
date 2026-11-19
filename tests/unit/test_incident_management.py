from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
import pytest
from fastapi import status

from backend.app.core.exceptions import AppException, ResourceNotFoundError
from backend.app.models.audit import AuditAction
from backend.app.models.incident import IncidentSeverity, IncidentStatus
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.incident import (
    IncidentAssignRequest,
    IncidentResolutionRequest,
    IncidentSeverityUpdateRequest,
    IncidentVerifyResolutionRequest,
    InvestigationNoteCreate,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.incident_management_service import IncidentManagementService


@pytest.fixture
def mock_db():
    db = MagicMock()
    db["incidents"] = MagicMock()
    db["audit_logs"] = MagicMock()
    db["knowledge_base"] = MagicMock()
    return db


@pytest.fixture
def engineer_user():
    return UserInDB(
        id="eng-123",
        email="engineer@example.com",
        full_name="Lead Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def viewer_user():
    return UserInDB(
        id="viewer-123",
        email="viewer@example.com",
        full_name="Readonly Viewer",
        hashed_password="pw",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def other_tenant_user():
    return UserInDB(
        id="tenant-other",
        email="other@example.com",
        full_name="Other Tenant",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_incident_doc():
    return {
        "_id": ObjectId(),
        "incident_id": "INC-20261119-A1B2C3",
        "user_id": "eng-123",
        "service_name": "checkout-service",
        "environment": "production",
        "severity": "HIGH",
        "status": "OPEN",
        "error_signature": "sig-abc-123",
        "title": "Stripe API timeout",
        "first_seen": datetime.now(timezone.utc),
        "last_seen": datetime.now(timezone.utc),
        "window_event_count": 10,
        "event_count": 10,
        "related_log_ids": [],
        "investigation_notes": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_viewer_forbidden_on_lifecycle_modifications(mock_db, viewer_user, sample_incident_doc):
    """Viewers are strictly prohibited from modifying incident state."""
    mock_db["incidents"].find_one = AsyncMock(return_value=sample_incident_doc)

    with pytest.raises(AppException) as exc_info:
        await IncidentManagementService.acknowledge_incident(mock_db, viewer_user, "INC-20261119-A1B2C3")
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    with pytest.raises(AppException) as exc_info:
        await IncidentManagementService.assign_incident(
            mock_db, viewer_user, "INC-20261119-A1B2C3", IncidentAssignRequest(assigned_to="someone")
        )
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    with pytest.raises(AppException) as exc_info:
        await IncidentManagementService.update_severity(
            mock_db, viewer_user, "INC-20261119-A1B2C3", IncidentSeverityUpdateRequest(severity=IncidentSeverity.CRITICAL)
        )
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    with pytest.raises(AppException) as exc_info:
        await IncidentManagementService.add_investigation_note(
            mock_db, viewer_user, "INC-20261119-A1B2C3", InvestigationNoteCreate(note="some note")
        )
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    with pytest.raises(AppException) as exc_info:
        await IncidentManagementService.record_resolution(
            mock_db,
            viewer_user,
            "INC-20261119-A1B2C3",
            IncidentResolutionRequest(confirmed_root_cause="cause", confirmed_resolution="fix"),
        )
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_tenant_isolation_on_modifications(mock_db, other_tenant_user, sample_incident_doc):
    """Users cannot modify or view incidents belonging to another tenant."""
    # Belongs to eng-123; other_tenant_user has id tenant-other
    mock_db["incidents"].find_one = AsyncMock(return_value=sample_incident_doc)

    with pytest.raises(ResourceNotFoundError):
        await IncidentManagementService.assign_incident(
            mock_db, other_tenant_user, "INC-20261119-A1B2C3", IncidentAssignRequest(assigned_to="other@example.com")
        )

    with pytest.raises(ResourceNotFoundError):
        await IncidentManagementService.add_investigation_note(
            mock_db, other_tenant_user, "INC-20261119-A1B2C3", InvestigationNoteCreate(note="cross-tenant note")
        )

    with pytest.raises(ResourceNotFoundError):
        await IncidentManagementService.record_resolution(
            mock_db,
            other_tenant_user,
            "INC-20261119-A1B2C3",
            IncidentResolutionRequest(confirmed_root_cause="cause", confirmed_resolution="fix"),
        )


@pytest.mark.asyncio
async def test_assign_incident_updates_record_and_audits(mock_db, engineer_user, sample_incident_doc):
    """Assigning an incident updates assigned_to, timestamps, and writes an audit event."""
    mock_db["incidents"].find_one = AsyncMock(return_value=sample_incident_doc)
    mock_db["incidents"].update_one = AsyncMock()
    mock_db["audit_logs"].insert_one = AsyncMock()

    res = await IncidentManagementService.assign_incident(
        mock_db, engineer_user, "INC-20261119-A1B2C3", IncidentAssignRequest(assigned_to="dev@example.com")
    )
    assert res is not None

    # Check update_one was called with assignment
    update_call = mock_db["incidents"].update_one.call_args[0]
    assert update_call[0] == {"incident_id": "INC-20261119-A1B2C3"}
    assert update_call[1]["$set"]["assigned_to"] == "dev@example.com"
    assert update_call[1]["$set"]["assigned_by"] == engineer_user.id

    # Check audit log was written
    audit_call = mock_db["audit_logs"].insert_one.call_args[0][0]
    assert audit_call["incident_id"] == "INC-20261119-A1B2C3"
    assert audit_call["action"] == AuditAction.ASSIGNED
    assert audit_call["actor_email"] == engineer_user.email


@pytest.mark.asyncio
async def test_update_severity_modifies_severity_and_audits(mock_db, engineer_user, sample_incident_doc):
    """Updating severity modifies severity enum and writes audit event."""
    mock_db["incidents"].find_one = AsyncMock(return_value=sample_incident_doc)
    mock_db["incidents"].update_one = AsyncMock()
    mock_db["audit_logs"].insert_one = AsyncMock()

    res = await IncidentManagementService.update_severity(
        mock_db, engineer_user, "INC-20261119-A1B2C3", IncidentSeverityUpdateRequest(severity=IncidentSeverity.CRITICAL)
    )
    assert res is not None

    update_call = mock_db["incidents"].update_one.call_args[0]
    assert update_call[1]["$set"]["severity"] == "CRITICAL"

    audit_call = mock_db["audit_logs"].insert_one.call_args[0][0]
    assert audit_call["action"] == AuditAction.SEVERITY_UPDATED
    assert audit_call["details"]["new_severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_add_investigation_note_appends_note_and_audits(mock_db, engineer_user, sample_incident_doc):
    """Adding an investigation note pushes a note document and creates an audit record."""
    mock_db["incidents"].find_one = AsyncMock(return_value=sample_incident_doc)
    mock_db["incidents"].update_one = AsyncMock()
    mock_db["audit_logs"].insert_one = AsyncMock()

    res = await IncidentManagementService.add_investigation_note(
        mock_db, engineer_user, "INC-20261119-A1B2C3", InvestigationNoteCreate(note="Checked database connection pools.")
    )
    assert res is not None

    update_call = mock_db["incidents"].update_one.call_args[0]
    pushed_note = update_call[1]["$push"]["investigation_notes"]
    assert "NOTE-" in pushed_note["note_id"]
    assert pushed_note["note"] == "Checked database connection pools."
    assert pushed_note["user_email"] == engineer_user.email

    audit_call = mock_db["audit_logs"].insert_one.call_args[0][0]
    assert audit_call["action"] == AuditAction.NOTE_ADDED


@pytest.mark.asyncio
async def test_record_resolution_separates_ai_hypothesis_from_verified_resolution(mock_db, engineer_user, sample_incident_doc):
    """
    Recording resolution updates the incident with verified fields,
    transitions status to RESOLVED, and invokes KnowledgeIndexer with force_reindex=True.
    """
    mock_db["incidents"].find_one = AsyncMock(return_value=sample_incident_doc)
    mock_db["incidents"].update_one = AsyncMock()
    mock_db["audit_logs"].insert_one = AsyncMock()

    with patch("backend.app.services.incident_management_service.KnowledgeIndexer") as MockIndexer:
        mock_indexer_inst = MagicMock()
        mock_indexer_inst.index_incident = AsyncMock(return_value={"knowledge_id": "KB-123", "has_verified_resolution": True})
        MockIndexer.return_value = mock_indexer_inst

        req = IncidentResolutionRequest(
            confirmed_root_cause="Redis connection pool starvation under spike load",
            confirmed_resolution="Increased max connections from 20 to 100 and added keepalive",
            resolution_actions=["Updated redis.conf", "Restarted checkout workers"],
            is_verified=True,
            rca_analysis_id="RCA-20261119-123456",
        )

        res = await IncidentManagementService.record_resolution(
            mock_db, engineer_user, "INC-20261119-A1B2C3", req
        )
        assert res is not None

        # Verify incident update
        update_call = mock_db["incidents"].update_one.call_args_list[0][0]
        set_fields = update_call[1]["$set"]
        assert set_fields["status"] == IncidentStatus.RESOLVED.value
        assert set_fields["confirmed_root_cause"] == "Redis connection pool starvation under spike load"
        assert set_fields["has_verified_resolution"] is True
        assert set_fields["verified_by"] == engineer_user.id
        assert set_fields["rca_analysis_id"] == "RCA-20261119-123456"

        # Verify KnowledgeIndexer was called with force_reindex=True
        mock_indexer_inst.index_incident.assert_called_once_with(
            incident_id="INC-20261119-A1B2C3",
            user=engineer_user,
            force_reindex=True,
        )


@pytest.mark.asyncio
async def test_knowledge_sync_failure_is_resilient(mock_db, engineer_user, sample_incident_doc):
    """
    If Knowledge Base indexing fails, record_resolution logs the error,
    sets knowledge_synced: False, and does NOT crash the resolution response.
    """
    mock_db["incidents"].find_one = AsyncMock(return_value=sample_incident_doc)
    mock_db["incidents"].update_one = AsyncMock()
    mock_db["audit_logs"].insert_one = AsyncMock()

    with patch("backend.app.services.incident_management_service.KnowledgeIndexer") as MockIndexer:
        mock_indexer_inst = MagicMock()
        mock_indexer_inst.index_incident = AsyncMock(side_effect=RuntimeError("Atlas vector index unreachable"))
        MockIndexer.return_value = mock_indexer_inst

        req = IncidentResolutionRequest(
            confirmed_root_cause="Bad config",
            confirmed_resolution="Fixed config",
            is_verified=True,
        )

        res = await IncidentManagementService.record_resolution(
            mock_db, engineer_user, "INC-20261119-A1B2C3", req
        )
        assert res is not None

        # Verify KNOWLEDGE_SYNC_FAILED was audited
        audit_actions = [call[0][0]["action"] for call in mock_db["audit_logs"].insert_one.call_args_list]
        assert AuditAction.KNOWLEDGE_SYNC_FAILED in audit_actions


@pytest.mark.asyncio
async def test_verify_resolution_endpoint_updates_and_syncs_kb(mock_db, engineer_user, sample_incident_doc):
    """
    verify_resolution explicitly flips has_verified_resolution to True
    and triggers knowledge synchronization.
    """
    sample_incident_doc["confirmed_resolution"] = "Preliminary fix"
    sample_incident_doc["has_verified_resolution"] = False
    mock_db["incidents"].find_one = AsyncMock(return_value=sample_incident_doc)
    mock_db["incidents"].update_one = AsyncMock()
    mock_db["audit_logs"].insert_one = AsyncMock()

    with patch("backend.app.services.incident_management_service.KnowledgeIndexer") as MockIndexer:
        mock_indexer_inst = MagicMock()
        mock_indexer_inst.index_incident = AsyncMock(return_value={"knowledge_id": "KB-123", "has_verified_resolution": True})
        MockIndexer.return_value = mock_indexer_inst

        res = await IncidentManagementService.verify_resolution(
            mock_db,
            engineer_user,
            "INC-20261119-A1B2C3",
            IncidentVerifyResolutionRequest(is_verified=True, verification_notes="Tested under load test"),
        )
        assert res is not None

        update_call = mock_db["incidents"].update_one.call_args_list[0][0]
        assert update_call[1]["$set"]["has_verified_resolution"] is True
        assert update_call[1]["$set"]["verified_by"] == engineer_user.id
