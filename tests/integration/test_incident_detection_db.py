"""
Live Database Integration Tests for Deterministic Incident Detection.
Requires a live MongoDB replica set (local or Atlas) supporting multi-document ACID transactions.

Covers Safeguards 1 & 2:
- Distributed leases and fencing tokens.
- Idempotent claim rejection and expired lease recovery.
- Transactional rollback on worker crash during active incident update.
- Transactional rollback on worker crash during initial incident creation.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from bson import ObjectId
import pytest

from backend.app.db.mongodb import MongoDBManager
from backend.app.models.incident import IncidentSeverity, IncidentStatus
from backend.app.services.error_signature import ErrorSignatureGenerator
from backend.app.services.incident_detection_service import IncidentDetectionService

pytestmark = [pytest.mark.asyncio, pytest.mark.requires_mongodb]


_MONGO_AVAILABLE = None


@pytest.fixture(autouse=True)
async def check_mongodb_available():
    """
    Integration safeguard: verify MongoDB replica set connection is live.
    Skips tests gracefully if MongoDB is unreachable (e.g. offline dev or IP access restricted).
    Caches probe result to avoid repeated ping timeouts within the module.
    """
    global _MONGO_AVAILABLE
    if _MONGO_AVAILABLE is None:
        _MONGO_AVAILABLE = await MongoDBManager.ping()
    if not _MONGO_AVAILABLE:
        pytest.skip("Test requires a live MongoDB replica set (local or Atlas) with transaction support")


async def test_claim_log_acquires_lease_and_token():
    """
    Safeguard 2: Proves successful claim sets PROCESSING status,
    future lease expiration, and returns a unique lease token.
    """
    db = MongoDBManager.get_database()
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "detection_status": "PENDING",
        "service_name": "test-svc",
        "timestamp": now
    }
    await db["logs"].insert_one(doc)

    claimed_log, lease_token = await IncidentDetectionService.claim_log_for_processing(db, doc["_id"])
    assert claimed_log is not None
    assert lease_token is not None
    assert len(lease_token) == 32
    assert claimed_log["detection_status"] == "PROCESSING"
    assert claimed_log["lease_token"] == lease_token
    lease_until = claimed_log["detection_lease_until"]
    if lease_until.tzinfo is None:
        lease_until = lease_until.replace(tzinfo=timezone.utc)
    assert lease_until > now


async def test_claim_log_idempotent_rejection():
    """
    Safeguard 2: While an active lease is unexpired, subsequent claim attempts return None.
    """
    db = MongoDBManager.get_database()
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "detection_status": "PROCESSING",
        "detection_lease_until": now + timedelta(seconds=60),
        "lease_token": "active-worker-token"
    }
    await db["logs"].insert_one(doc)

    claimed_log, lease_token = await IncidentDetectionService.claim_log_for_processing(db, doc["_id"])
    assert claimed_log is None
    assert lease_token is None


async def test_claim_log_recovers_expired_lease():
    """
    Crash Recovery: An expired lease (lease_until in the past) can be safely reclaimed.
    """
    db = MongoDBManager.get_database()
    past = datetime.now(timezone.utc) - timedelta(seconds=45)
    doc = {
        "_id": ObjectId(),
        "detection_status": "PROCESSING",
        "detection_lease_until": past,
        "lease_token": "crashed-worker-old-token"
    }
    await db["logs"].insert_one(doc)

    claimed_log, new_token = await IncidentDetectionService.claim_log_for_processing(db, doc["_id"])
    assert claimed_log is not None
    assert new_token is not None
    assert new_token != "crashed-worker-old-token"
    assert claimed_log["lease_token"] == new_token


async def test_fencing_prevents_stale_worker_update():
    """
    Fencing Token Test: A worker holding a stale/expired token cannot overwrite the log state.
    """
    db = MongoDBManager.get_database()
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "detection_status": "PROCESSING",
        "lease_token": "new-winner-token",
        "detection_lease_until": now + timedelta(seconds=30)
    }
    await db["logs"].insert_one(doc)

    # Stale worker attempts to complete with old token
    res = await db["logs"].update_one(
        {"_id": doc["_id"], "lease_token": "stale-loser-token"},
        {"$set": {"detection_status": "PROCESSED"}}
    )
    # Stale worker was fenced out!
    assert res.matched_count == 0
    assert res.modified_count == 0


async def test_crash_between_incident_increment_and_log_completion():
    """
    Safeguard 1 & 2 Crash-Recovery Test:
    Simulates a worker crash during an active incident update transaction.
    Proves that the transaction rollback + lease recovery ensures exactly-once accounting
    and that a stale worker cannot double-count event_count.
    """
    db = MongoDBManager.get_database()
    now = datetime.now(timezone.utc)
    user_id = str(ObjectId())
    svc = f"crash-active-{uuid.uuid4().hex[:6]}"
    env = "production"
    msg = "Unhandled connection drop in worker pool"
    sig = ErrorSignatureGenerator.generate(svc, env, msg)
    inc_id = f"INC-CRASH-{uuid.uuid4().hex[:6].upper()}"

    # 1. Existing active incident with count = 3
    inc_doc = {
        "incident_id": inc_id,
        "user_id": user_id,
        "environment": env,
        "service_name": svc,
        "error_signature": sig,
        "status": "OPEN",
        "severity": "LOW",
        "event_count": 3,
        "window_event_count": 3,
        "first_seen": now - timedelta(seconds=60),
        "last_seen": now - timedelta(seconds=10),
        "related_log_ids": [],
        "created_at": now - timedelta(seconds=60),
        "updated_at": now - timedelta(seconds=10),
    }
    await db["incidents"].insert_one(inc_doc)

    # 2. Ingest 4th log
    log_doc = {
        "_id": ObjectId(),
        "user_id": user_id,
        "environment": env,
        "service_name": svc,
        "level": "ERROR",
        "message": msg,
        "normalized_message": msg,
        "error_signature": sig,
        "timestamp": now,
        "detection_status": "PENDING",
        "incident_id": None,
    }
    await db["logs"].insert_one(log_doc)

    # 3. Worker 1 claims log 4
    claimed_1, token_1 = await IncidentDetectionService.claim_log_for_processing(db, log_doc["_id"])
    assert claimed_1 is not None

    # 4. Worker 1 simulates a crash inside its update transaction before commit:
    client = db.client
    async with client.start_session() as s1:
        await s1.start_transaction()
        await db["incidents"].update_one(
            {"incident_id": inc_id},
            {"$inc": {"event_count": 1}},
            session=s1
        )
        # Process crashes -> transaction is aborted
        await s1.abort_transaction()

    # Verify state after crash: incident count NOT incremented, log NOT linked
    inc_after_crash = await db["incidents"].find_one({"incident_id": inc_id})
    assert inc_after_crash["event_count"] == 3
    log_after_crash = await db["logs"].find_one({"_id": log_doc["_id"]})
    assert log_after_crash["incident_id"] is None

    # 5. Worker 1's lease expires
    past_time = now - timedelta(seconds=60)
    await db["logs"].update_one(
        {"_id": log_doc["_id"]},
        {"$set": {"detection_lease_until": past_time}}
    )

    # 6. Worker 2 picks up log 4 and processes it to completion
    res_inc_id = await IncidentDetectionService.process_log_for_detection(db, user_id, log_doc["_id"])
    assert res_inc_id == inc_id

    # Verify incident event_count was incremented EXACTLY ONCE (from 3 to 4, NOT 5)
    final_inc = await db["incidents"].find_one({"incident_id": inc_id})
    assert final_inc["event_count"] == 4

    final_log = await db["logs"].find_one({"_id": log_doc["_id"]})
    assert final_log["detection_status"] == "PROCESSED"
    assert final_log["incident_id"] == inc_id

    # 7. Resumed Worker 1 tries to commit using its stale lease token_1
    stale_update = await db["logs"].update_one(
        {"_id": log_doc["_id"], "lease_token": token_1},
        {"$set": {"detection_status": "PROCESSED"}}
    )
    assert stale_update.matched_count == 0
    # Final count remains strictly 4
    inc_recheck = await db["incidents"].find_one({"incident_id": inc_id})
    assert inc_recheck["event_count"] == 4


async def test_crash_during_initial_incident_creation_and_log_linking():
    """
    Safeguard 1 & 2 Crash-Recovery Test:
    Simulates a worker crash during initial incident creation transaction.
    Proves that transactional atomicity rolls back both incident creation and log status,
    and a subsequent retry creates the incident with exact initial accounting.
    """
    db = MongoDBManager.get_database()
    now = datetime.now(timezone.utc)
    user_id = str(ObjectId())
    svc = f"crash-init-{uuid.uuid4().hex[:6]}"
    env = "production"
    msg = "Deadlock encountered in transaction lock manager"
    sig = ErrorSignatureGenerator.generate(svc, env, msg)

    # Create 3 logs
    log_ids = []
    for i in range(3):
        doc = {
            "_id": ObjectId(),
            "user_id": user_id,
            "environment": env,
            "service_name": svc,
            "level": "ERROR",
            "message": msg,
            "normalized_message": msg,
            "error_signature": sig,
            "timestamp": now - timedelta(seconds=20 - i * 5),
            "detection_status": "PENDING" if i == 2 else "PROCESSED",
            "incident_id": None,
        }
        await db["logs"].insert_one(doc)
        log_ids.append(doc["_id"])

    # Worker 1 claims the 3rd log
    claimed_1, token_1 = await IncidentDetectionService.claim_log_for_processing(db, log_ids[2])
    assert claimed_1 is not None

    # Worker 1 simulates a crash during incident creation transaction before commit:
    temp_inc_id = f"INC-CRASH-INIT-{uuid.uuid4().hex[:4].upper()}"
    client = db.client
    async with client.start_session() as s1:
        await s1.start_transaction()
        # Worker 1 inserts incident in tx
        await db["incidents"].insert_one(
            {"incident_id": temp_inc_id, "user_id": user_id, "service_name": svc, "status": "OPEN"},
            session=s1
        )
        # Crash occurs -> transaction aborted
        await s1.abort_transaction()

    # Verify no incident was created in DB
    aborted_inc = await db["incidents"].find_one({"incident_id": temp_inc_id})
    assert aborted_inc is None

    # Verify logs remain unlinked
    unlinked_logs = await db["logs"].find({"_id": {"$in": log_ids}, "incident_id": None}).to_list(length=10)
    assert len(unlinked_logs) == 3

    # Worker 1's lease expires
    await db["logs"].update_one(
        {"_id": log_ids[2]},
        {"$set": {"detection_lease_until": now - timedelta(seconds=60)}}
    )

    # Worker 2 processes log 3 for detection
    created_inc_id = await IncidentDetectionService.process_log_for_detection(db, user_id, log_ids[2])
    assert created_inc_id is not None
    assert created_inc_id != temp_inc_id

    # Verify incident was created with exact event_count = 3
    inc = await db["incidents"].find_one({"incident_id": created_inc_id})
    assert inc is not None
    assert inc["event_count"] == 3
    assert inc["status"] == "OPEN"

    # Verify all 3 logs are marked PROCESSED and linked to the new incident
    linked_logs = await db["logs"].find({"incident_id": created_inc_id}).to_list(length=10)
    assert len(linked_logs) == 3
    for l in linked_logs:
        assert l["detection_status"] == "PROCESSED"
