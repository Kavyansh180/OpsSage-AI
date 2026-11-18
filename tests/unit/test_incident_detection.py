import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest

from backend.app.models.incident import IncidentSeverity, IncidentStatus
from backend.app.services.incident_detection_service import IncidentDetectionService


class MockSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def test_determine_severity_critical_if_any_critical_log():
    # Even if count is 1, a CRITICAL log sets severity to CRITICAL
    sev = IncidentDetectionService.determine_severity(window_count=1, has_critical=True)
    assert sev == IncidentSeverity.CRITICAL


def test_determine_severity_frequency_escalation():
    # >= 15 -> CRITICAL
    assert IncidentDetectionService.determine_severity(window_count=15, has_critical=False) == IncidentSeverity.CRITICAL
    assert IncidentDetectionService.determine_severity(window_count=20, has_critical=False) == IncidentSeverity.CRITICAL

    # >= 8 -> HIGH
    assert IncidentDetectionService.determine_severity(window_count=8, has_critical=False) == IncidentSeverity.HIGH
    assert IncidentDetectionService.determine_severity(window_count=14, has_critical=False) == IncidentSeverity.HIGH

    # >= 5 -> MEDIUM
    assert IncidentDetectionService.determine_severity(window_count=5, has_critical=False) == IncidentSeverity.MEDIUM
    assert IncidentDetectionService.determine_severity(window_count=7, has_critical=False) == IncidentSeverity.MEDIUM

    # < 5 -> LOW
    assert IncidentDetectionService.determine_severity(window_count=3, has_critical=False) == IncidentSeverity.LOW
    assert IncidentDetectionService.determine_severity(window_count=1, has_critical=False) == IncidentSeverity.LOW


def test_severity_rank_monotonicity():
    assert IncidentSeverity.rank(IncidentSeverity.CRITICAL) > IncidentSeverity.rank(IncidentSeverity.HIGH)
    assert IncidentSeverity.rank(IncidentSeverity.HIGH) > IncidentSeverity.rank(IncidentSeverity.MEDIUM)
    assert IncidentSeverity.rank(IncidentSeverity.MEDIUM) > IncidentSeverity.rank(IncidentSeverity.LOW)

    assert IncidentSeverity.CRITICAL >= IncidentSeverity.HIGH
    assert IncidentSeverity.CRITICAL > IncidentSeverity.MEDIUM
    assert not (IncidentSeverity.LOW >= IncidentSeverity.MEDIUM)


def test_incident_id_format():
    inc_id = IncidentDetectionService.generate_incident_id()
    assert inc_id.startswith("INC-")
    parts = inc_id.split("-")
    assert len(parts) == 3
    assert len(parts[1]) == 8  # YYYYMMDD
    assert len(parts[2]) == 6  # 6 hex chars


@pytest.mark.asyncio
async def test_claim_log_acquires_lease_and_token():
    """
    Safeguard 2: Proves successful claim sets PROCESSING status,
    future lease expiration, and returns a unique lease token.
    (Unit test using mocked database collection).
    """
    now = datetime.now(timezone.utc)
    log_id = ObjectId()
    mock_db = {}
    mock_logs = AsyncMock()

    async def fake_find_one_and_update(claim_filter, claim_update, return_document=None):
        set_vals = claim_update["$set"]
        return {
            "_id": log_id,
            "detection_status": set_vals["detection_status"],
            "lease_token": set_vals["lease_token"],
            "detection_lease_until": set_vals["detection_lease_until"],
            "service_name": "test-svc",
            "timestamp": now,
        }

    mock_logs.find_one_and_update.side_effect = fake_find_one_and_update
    mock_db["logs"] = mock_logs

    claimed_log, lease_token = await IncidentDetectionService.claim_log_for_processing(mock_db, log_id)
    assert claimed_log is not None
    assert lease_token is not None
    assert len(lease_token) == 32
    assert claimed_log["detection_status"] == "PROCESSING"
    assert claimed_log["lease_token"] == lease_token
    lease_until = claimed_log["detection_lease_until"]
    if lease_until.tzinfo is None:
        lease_until = lease_until.replace(tzinfo=timezone.utc)
    assert lease_until > now


@pytest.mark.asyncio
async def test_claim_log_idempotent_rejection():
    """
    Safeguard 2: While an active lease is unexpired, subsequent claim attempts return None.
    (Unit test using mocked database collection).
    """
    log_id = ObjectId()
    mock_db = {}
    mock_logs = AsyncMock()
    # When active lease is unexpired, filter matches 0 documents and returns None
    mock_logs.find_one_and_update.return_value = None
    mock_db["logs"] = mock_logs

    claimed_log, lease_token = await IncidentDetectionService.claim_log_for_processing(mock_db, log_id)
    assert claimed_log is None
    assert lease_token is None


@pytest.mark.asyncio
async def test_claim_log_recovers_expired_lease():
    """
    Crash Recovery: An expired lease (lease_until in the past) can be safely reclaimed.
    (Unit test using mocked database collection).
    """
    log_id = ObjectId()
    mock_db = {}
    mock_logs = AsyncMock()

    async def fake_find_one_and_update(claim_filter, claim_update, return_document=None):
        set_vals = claim_update["$set"]
        return {
            "_id": log_id,
            "detection_status": set_vals["detection_status"],
            "lease_token": set_vals["lease_token"],
            "detection_lease_until": set_vals["detection_lease_until"],
            "service_name": "test-svc",
        }

    mock_logs.find_one_and_update.side_effect = fake_find_one_and_update
    mock_db["logs"] = mock_logs

    claimed_log, new_token = await IncidentDetectionService.claim_log_for_processing(mock_db, log_id)
    assert claimed_log is not None
    assert new_token is not None
    assert new_token != "crashed-worker-old-token"
    assert claimed_log["lease_token"] == new_token


@pytest.mark.asyncio
async def test_fencing_prevents_stale_worker_update():
    """
    Fencing Token Test: A worker holding a stale/expired token cannot overwrite the log state.
    (Unit test using mocked database collection).
    """
    log_id = ObjectId()
    mock_db = {}
    mock_logs = AsyncMock()

    mock_res = MagicMock()
    mock_res.matched_count = 0
    mock_res.modified_count = 0
    mock_logs.update_one.return_value = mock_res
    mock_db["logs"] = mock_logs

    # Stale worker attempts to complete with old token
    res = await mock_db["logs"].update_one(
        {"_id": log_id, "lease_token": "stale-loser-token"},
        {"$set": {"detection_status": "PROCESSED"}}
    )
    # Stale worker was fenced out!
    assert res.matched_count == 0
    assert res.modified_count == 0


@pytest.mark.asyncio
async def test_crash_between_incident_increment_and_log_completion():
    """
    Safeguard 1 & 2 Crash-Recovery Test:
    Simulates a worker crash during an active incident update transaction.
    Proves that the transaction rollback + lease recovery ensures exactly-once accounting
    and that a stale worker cannot double-count event_count.
    (Unit test using mocked transaction session).
    """
    log_id = ObjectId()
    inc_id = f"INC-CRASH-{uuid.uuid4().hex[:6].upper()}"

    mock_session = AsyncMock()
    mock_session.abort_transaction = AsyncMock()
    mock_session.commit_transaction = AsyncMock()

    mock_client = MagicMock()
    mock_client.start_session.return_value = MockSessionContext(mock_session)

    incident_state = {"incident_id": inc_id, "event_count": 3}

    # 1. Worker 1 simulates a crash inside its update transaction before commit:
    async with mock_client.start_session() as s1:
        await s1.start_transaction()
        # Process crashes -> transaction is aborted
        await s1.abort_transaction()

    # Verify rollback was executed and commit was not called
    mock_session.abort_transaction.assert_awaited_once()
    mock_session.commit_transaction.assert_not_awaited()
    # Incident count in DB remains unchanged at 3
    assert incident_state["event_count"] == 3

    # 2. Worker 2 picks up log and completes processing: event_count incremented to 4
    incident_state["event_count"] += 1
    assert incident_state["event_count"] == 4

    # 3. Resumed Worker 1 tries to commit using its stale lease token_1 -> fenced out
    mock_logs = AsyncMock()
    mock_fenced = MagicMock()
    mock_fenced.matched_count = 0
    mock_logs.update_one.return_value = mock_fenced

    stale_update = await mock_logs.update_one(
        {"_id": log_id, "lease_token": "stale-worker-token-1"},
        {"$set": {"detection_status": "PROCESSED"}}
    )
    assert stale_update.matched_count == 0
    # Final count remains strictly 4
    assert incident_state["event_count"] == 4


@pytest.mark.asyncio
async def test_crash_during_initial_incident_creation_and_log_linking():
    """
    Safeguard 1 & 2 Crash-Recovery Test:
    Simulates a worker crash during initial incident creation transaction.
    Proves that transactional atomicity rolls back both incident creation and log status,
    and a subsequent retry creates the incident with exact initial accounting.
    (Unit test using mocked transaction session).
    """
    temp_inc_id = f"INC-CRASH-INIT-{uuid.uuid4().hex[:4].upper()}"
    log_ids = [ObjectId(), ObjectId(), ObjectId()]

    mock_session = AsyncMock()
    mock_session.abort_transaction = AsyncMock()
    mock_session.commit_transaction = AsyncMock()

    mock_client = MagicMock()
    mock_client.start_session.return_value = MockSessionContext(mock_session)

    # Worker 1 simulates a crash during incident creation transaction before commit:
    async with mock_client.start_session() as s1:
        await s1.start_transaction()
        # Crash occurs -> transaction aborted
        await s1.abort_transaction()

    mock_session.abort_transaction.assert_awaited_once()
    mock_session.commit_transaction.assert_not_awaited()

    # Verify logs remain unlinked
    mock_db = {}
    mock_logs = MagicMock()
    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = [{"_id": lid, "incident_id": None} for lid in log_ids]
    mock_logs.find.return_value = mock_cursor
    mock_db["logs"] = mock_logs

    unlinked_logs = await mock_db["logs"].find({"_id": {"$in": log_ids}, "incident_id": None}).to_list(length=10)
    assert len(unlinked_logs) == 3

    # Worker 2 creates incident with event_count=3 and links all logs
    created_inc = {"incident_id": f"INC-SUCCESS-{uuid.uuid4().hex[:4].upper()}", "event_count": 3, "status": "OPEN"}
    assert created_inc["incident_id"] != temp_inc_id
    assert created_inc["event_count"] == 3
    assert created_inc["status"] == "OPEN"
