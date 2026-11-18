import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
import pytest
from httpx import AsyncClient

from backend.app.db.mongodb import MongoDBManager
from backend.app.models.user import UserRole
from backend.app.services.auth_service import AuthService


async def create_user_and_token(async_client: AsyncClient, role: UserRole = UserRole.ENGINEER):
    """Helper to create user and retrieve token."""
    suffix = uuid.uuid4().hex[:8]
    email = f"user_{role.value}_{suffix}@company.com"
    password = "TestPassword123!"

    if role == UserRole.ADMIN:
        db = MongoDBManager.get_database()
        await AuthService.create_user_with_role(
            db=db,
            email=email,
            password=password,
            full_name="Admin Test User",
            role=UserRole.ADMIN
        )
    elif role == UserRole.VIEWER:
        db = MongoDBManager.get_database()
        await AuthService.create_user_with_role(
            db=db,
            email=email,
            password=password,
            full_name="Viewer Test User",
            role=UserRole.VIEWER
        )
    else:
        # Standard engineer registration
        await async_client.post("/api/v1/auth/register", json={
            "email": email,
            "password": password,
            "full_name": "Engineer Test User"
        })

    login_resp = await async_client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    token = login_resp.json()["access_token"]
    user_id = login_resp.json()["user_id"]
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_id,
        "email": email
    }


@pytest.mark.asyncio
async def test_incident_created_when_threshold_reached_with_all_window_logs(async_client: AsyncClient):
    """
    Test threshold-based creation and initial event count completeness:
    - Log 1: count 1 (no incident)
    - Log 2: count 2 (no incident)
    - Log 3: count 3 -> Threshold reached!
    - Incident created with event_count = 3 (including all window logs).
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)

    service = f"checkout-{uuid.uuid4().hex[:6]}"
    err_msg = "Database connection pool exhausted after 30000 ms"

    # 1. Log 1
    resp1 = await async_client.post("/api/v1/logs/ingest", json={
        "service_name": service,
        "environment": "production",
        "level": "ERROR",
        "message": err_msg
    }, headers=user["headers"])
    assert resp1.status_code == 201

    # Check: no incident yet
    inc_resp1 = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    assert inc_resp1.status_code == 200
    assert inc_resp1.json()["total"] == 0

    # 2. Log 2
    resp2 = await async_client.post("/api/v1/logs/ingest", json={
        "service_name": service,
        "environment": "production",
        "level": "ERROR",
        "message": err_msg
    }, headers=user["headers"])
    assert resp2.status_code == 201

    # Check: still no incident
    inc_resp2 = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    assert inc_resp2.json()["total"] == 0

    # 3. Log 3 -> Crosses threshold of 3!
    resp3 = await async_client.post("/api/v1/logs/ingest", json={
        "service_name": service,
        "environment": "production",
        "level": "ERROR",
        "message": err_msg
    }, headers=user["headers"])
    assert resp3.status_code == 201

    # Check: Incident is now created!
    inc_resp3 = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    assert inc_resp3.json()["total"] == 1
    incident = inc_resp3.json()["items"][0]

    assert incident["service_name"] == service
    assert incident["environment"] == "production"
    assert incident["status"] == "OPEN"
    # CRITICAL SAFEGUARD: Initial count must represent all 3 window logs!
    assert incident["event_count"] == 3
    assert incident["window_event_count"] >= 3
    assert len(incident["related_log_ids"]) == 3


@pytest.mark.asyncio
async def test_active_incident_updated_below_threshold(async_client: AsyncClient):
    """
    Once an incident is OPEN or ACKNOWLEDGED, any subsequent matching log
    must update the incident even if the window count is below creation threshold.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)
    service = f"payment-{uuid.uuid4().hex[:6]}"
    err_msg = "Upstream gateway connection reset by peer"

    # Send 3 logs to trigger incident
    for _ in range(3):
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg
        }, headers=user["headers"])

    inc_resp = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    assert inc_resp.json()["total"] == 1
    assert inc_resp.json()["items"][0]["event_count"] == 3

    # Now send 1 additional log (Log 4)
    resp4 = await async_client.post("/api/v1/logs/ingest", json={
        "service_name": service,
        "environment": "production",
        "level": "ERROR",
        "message": err_msg
    }, headers=user["headers"])
    assert resp4.status_code == 201

    # Active incident must now reflect event_count = 4!
    inc_resp2 = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    assert inc_resp2.json()["total"] == 1
    assert inc_resp2.json()["items"][0]["event_count"] == 4


@pytest.mark.asyncio
async def test_resolved_incident_lifecycle_and_immutability(async_client: AsyncClient):
    """
    Test that resolving an incident permanently freezes it:
    - Subsequent matching errors create a NEW incident rather than reopening the resolved one.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)
    service = f"auth-{uuid.uuid4().hex[:6]}"
    err_msg = "LDAP server unreachable"

    # Trigger initial incident (3 logs)
    for _ in range(3):
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg
        }, headers=user["headers"])

    inc_list = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    incident_id = inc_list.json()["items"][0]["incident_id"]

    # 1. Acknowledge incident
    ack_resp = await async_client.patch(f"/api/v1/incidents/{incident_id}/acknowledge", headers=user["headers"])
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"

    # 2. Resolve incident
    res_resp = await async_client.patch(f"/api/v1/incidents/{incident_id}/resolve", headers=user["headers"])
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "RESOLVED"
    assert res_resp.json()["resolved_at"] is not None

    # 3. New matching errors occur (3 logs to cross threshold again)
    for _ in range(3):
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg
        }, headers=user["headers"])

    # Query all incidents for this service
    all_inc = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    items = all_inc.json()["items"]
    assert len(items) == 2

    # Original incident is still RESOLVED and untouched
    orig = next(i for i in items if i["incident_id"] == incident_id)
    assert orig["status"] == "RESOLVED"
    assert orig["event_count"] == 3

    # New incident is OPEN with its own fresh event_count
    new_inc = next(i for i in items if i["incident_id"] != incident_id)
    assert new_inc["status"] == "OPEN"
    assert new_inc["event_count"] == 3


@pytest.mark.asyncio
async def test_concurrent_incident_creation_race(async_client: AsyncClient):
    """
    Test concurrency safety:
    Send 4 logs concurrently. Partial unique index prevents duplicate active incidents
    and ensures total event count is accurately merged.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)
    service = f"concurrency-{uuid.uuid4().hex[:6]}"
    err_msg = "Redis replica sync failed"

    tasks = [
        async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg
        }, headers=user["headers"])
        for _ in range(5)
    ]

    responses = await asyncio.gather(*tasks)
    for r in responses:
        assert r.status_code == 201

    # Verify exactly 1 active incident was created
    inc_resp = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    assert inc_resp.json()["total"] == 1
    incident = inc_resp.json()["items"][0]
    assert incident["event_count"] == 5


@pytest.mark.asyncio
async def test_multi_tenant_isolation_on_incidents(async_client: AsyncClient):
    """
    Tenant Isolation Test:
    - User 1's incident cannot be accessed by User 2 (returns 404).
    - Admin can view User 1's incident.
    """
    user1 = await create_user_and_token(async_client, UserRole.ENGINEER)
    user2 = await create_user_and_token(async_client, UserRole.ENGINEER)
    admin = await create_user_and_token(async_client, UserRole.ADMIN)

    service = f"private-{uuid.uuid4().hex[:6]}"
    for _ in range(3):
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": "Sensitive internal failure"
        }, headers=user1["headers"])

    # User 1 gets incident ID
    u1_inc = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user1["headers"])
    incident_id = u1_inc.json()["items"][0]["incident_id"]

    # User 2 attempts to get User 1's incident -> 404
    u2_get = await async_client.get(f"/api/v1/incidents/{incident_id}", headers=user2["headers"])
    assert u2_get.status_code == 404

    # User 2 lists incidents -> sees 0
    u2_list = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user2["headers"])
    assert u2_list.json()["total"] == 0

    # Admin gets User 1's incident -> 200 OK
    admin_get = await async_client.get(f"/api/v1/incidents/{incident_id}", headers=admin["headers"])
    assert admin_get.status_code == 200
    assert admin_get.json()["incident_id"] == incident_id


@pytest.mark.asyncio
async def test_viewer_role_cannot_acknowledge_or_resolve(async_client: AsyncClient):
    """
    Role-Based Access Control Test:
    Viewer accounts are read-only and cannot acknowledge or resolve incidents (403 Forbidden).
    """
    eng = await create_user_and_token(async_client, UserRole.ENGINEER)
    viewer = await create_user_and_token(async_client, UserRole.VIEWER)

    service = f"rbac-{uuid.uuid4().hex[:6]}"
    for _ in range(3):
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": "Critical connection error"
        }, headers=eng["headers"])

    inc_list = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=eng["headers"])
    incident_id = inc_list.json()["items"][0]["incident_id"]

    # Viewer attempts acknowledge -> 403 Forbidden
    viewer_ack = await async_client.patch(f"/api/v1/incidents/{incident_id}/acknowledge", headers=viewer["headers"])
    assert viewer_ack.status_code == 403

    # Viewer attempts resolve -> 403 Forbidden
    viewer_res = await async_client.patch(f"/api/v1/incidents/{incident_id}/resolve", headers=viewer["headers"])
    assert viewer_res.status_code == 403

    # Engineer acknowledges -> 200 OK
    eng_ack = await async_client.patch(f"/api/v1/incidents/{incident_id}/acknowledge", headers=eng["headers"])
    assert eng_ack.status_code == 200


@pytest.mark.asyncio
async def test_environment_incident_isolation(async_client: AsyncClient):
    """
    Environment Isolation Test:
    Identical error in 'production' and 'staging' must produce 2 separate incidents.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)
    service = f"env-iso-{uuid.uuid4().hex[:6]}"
    err_msg = "Payment token expired"

    # Trigger production incident (3 logs)
    for _ in range(3):
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg
        }, headers=user["headers"])

    # Trigger staging incident (3 logs)
    for _ in range(3):
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "staging",
            "level": "ERROR",
            "message": err_msg
        }, headers=user["headers"])

    prod_resp = await async_client.get(f"/api/v1/incidents?service_name={service}&environment=production", headers=user["headers"])
    staging_resp = await async_client.get(f"/api/v1/incidents?service_name={service}&environment=staging", headers=user["headers"])

    assert prod_resp.json()["total"] == 1
    assert staging_resp.json()["total"] == 1

    prod_inc = prod_resp.json()["items"][0]
    staging_inc = staging_resp.json()["items"][0]

    assert prod_inc["environment"] == "production"
    assert staging_inc["environment"] == "staging"
    assert prod_inc["incident_id"] != staging_inc["incident_id"]
    assert prod_inc["error_signature"] != staging_inc["error_signature"]


@pytest.mark.asyncio
async def test_severity_escalation_with_critical_log(async_client: AsyncClient):
    """
    Severity Escalation Test:
    Presence of a CRITICAL log escalates incident severity to CRITICAL.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)
    service = f"sev-{uuid.uuid4().hex[:6]}"
    err_msg = "Cluster disk capacity threshold breached"

    # Send 2 ERROR logs, then 1 CRITICAL log
    await async_client.post("/api/v1/logs/ingest", json={"service_name": service, "level": "ERROR", "message": err_msg}, headers=user["headers"])
    await async_client.post("/api/v1/logs/ingest", json={"service_name": service, "level": "ERROR", "message": err_msg}, headers=user["headers"])
    await async_client.post("/api/v1/logs/ingest", json={"service_name": service, "level": "CRITICAL", "message": err_msg}, headers=user["headers"])

    inc_resp = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    assert inc_resp.json()["total"] == 1
    incident = inc_resp.json()["items"][0]
    assert incident["severity"] == "CRITICAL"


def parse_utc_dt(val: Any) -> datetime:
    """Helper to parse ISO datetime string and ensure UTC awareness."""
    dt = datetime.fromisoformat(val) if isinstance(val, str) else val
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@pytest.mark.asyncio
async def test_late_arriving_log_updates_first_seen_minimum(async_client: AsyncClient):
    """
    Test 1: Late-arriving log out-of-order delivery correctly updates first_seen
    to the earliest timestamp while last_seen remains at the maximum.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)
    service = f"late-{uuid.uuid4().hex[:6]}"
    err_msg = "Upstream socket timeout during payload flush"

    base_time = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
    t1 = base_time.isoformat()
    t2 = (base_time + timedelta(seconds=10)).isoformat()
    t3 = (base_time + timedelta(seconds=20)).isoformat()

    # Ingest 3 initial logs to create incident
    for ts in [t1, t2, t3]:
        resp = await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg,
            "timestamp": ts
        }, headers=user["headers"])
        assert resp.status_code == 201

    inc_resp = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    inc = inc_resp.json()["items"][0]
    assert inc["event_count"] == 3
    assert parse_utc_dt(inc["first_seen"]) == parse_utc_dt(t1)
    assert parse_utc_dt(inc["last_seen"]) == parse_utc_dt(t3)

    # Now ingest a late-arriving log with an earlier timestamp (t0 = 50s before base_time)
    t0 = (base_time - timedelta(seconds=50)).isoformat()
    late_resp = await async_client.post("/api/v1/logs/ingest", json={
        "service_name": service,
        "environment": "production",
        "level": "ERROR",
        "message": err_msg,
        "timestamp": t0
    }, headers=user["headers"])
    assert late_resp.status_code == 201

    # Verify first_seen updated to t0, and last_seen remained t3
    inc_resp2 = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    inc2 = inc_resp2.json()["items"][0]
    assert inc2["event_count"] == 4
    assert parse_utc_dt(inc2["first_seen"]) == parse_utc_dt(t0), "first_seen did not update to the earlier late-arriving log timestamp!"
    assert parse_utc_dt(inc2["last_seen"]) == parse_utc_dt(t3), "last_seen moved backward unexpectedly!"


@pytest.mark.asyncio
async def test_last_seen_never_moves_backward(async_client: AsyncClient):
    """
    Test 2: When an out-of-order log with an older timestamp arrives,
    last_seen remains strictly monotonic and never moves backward.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)
    service = f"lastseen-{uuid.uuid4().hex[:6]}"
    err_msg = "Kafka broker disconnected"

    base_time = datetime(2026, 11, 2, 14, 0, 0, tzinfo=timezone.utc)
    t1 = base_time.isoformat()
    t2 = (base_time + timedelta(seconds=30)).isoformat()
    t3 = (base_time + timedelta(seconds=60)).isoformat()

    for ts in [t1, t2, t3]:
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg,
            "timestamp": ts
        }, headers=user["headers"])

    # Ingest log with timestamp between t1 and t2 (e.g. t1 + 15s)
    t_mid = (base_time + timedelta(seconds=15)).isoformat()
    await async_client.post("/api/v1/logs/ingest", json={
        "service_name": service,
        "environment": "production",
        "level": "ERROR",
        "message": err_msg,
        "timestamp": t_mid
    }, headers=user["headers"])

    inc_resp = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    inc = inc_resp.json()["items"][0]
    assert inc["event_count"] == 4
    assert parse_utc_dt(inc["first_seen"]) == parse_utc_dt(t1)
    assert parse_utc_dt(inc["last_seen"]) == parse_utc_dt(t3)


@pytest.mark.asyncio
async def test_concurrent_critical_and_lower_severity_prevents_downgrade(async_client: AsyncClient):
    """
    Test 3: Concurrent CRITICAL and ERROR updates cannot downgrade severity.
    Even under high concurrency, once an incident is CRITICAL, subsequent or concurrent
    lower-severity logs preserve CRITICAL severity.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)
    service = f"race-sev-{uuid.uuid4().hex[:6]}"
    err_msg = "Database node uncontactable"

    # 1. Trigger incident with 3 ERROR logs (Severity = LOW)
    for _ in range(3):
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg
        }, headers=user["headers"])

    inc_resp = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    assert inc_resp.json()["items"][0]["severity"] == "LOW"

    # 2. Concurrently send 1 CRITICAL log and 4 ERROR logs
    tasks = [
        async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "environment": "production",
            "level": "CRITICAL" if i == 0 else "ERROR",
            "message": err_msg
        }, headers=user["headers"])
        for i in range(5)
    ]
    results = await asyncio.gather(*tasks)
    for r in results:
        assert r.status_code == 201

    # 3. Verify final incident severity is CRITICAL and not downgraded
    final_resp = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    final_inc = final_resp.json()["items"][0]
    assert final_inc["event_count"] == 8
    assert final_inc["severity"] == "CRITICAL", f"Expected CRITICAL, but got {final_inc['severity']}!"


@pytest.mark.asyncio
async def test_resolved_incident_not_accidentally_updated(async_client: AsyncClient):
    """
    Test 4: Resolved incidents are immutable. Subsequent logs do NOT update
    the resolved incident's event_count, severity, or timestamps.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)
    service = f"immut-{uuid.uuid4().hex[:6]}"
    err_msg = "Disk I/O error during sync"

    # Trigger incident
    for _ in range(3):
        await async_client.post("/api/v1/logs/ingest", json={
            "service_name": service,
            "level": "ERROR",
            "message": err_msg
        }, headers=user["headers"])

    inc_resp = await async_client.get(f"/api/v1/incidents?service_name={service}", headers=user["headers"])
    inc_id = inc_resp.json()["items"][0]["incident_id"]

    # Resolve incident
    resolve_resp = await async_client.patch(f"/api/v1/incidents/{inc_id}/resolve", headers=user["headers"])
    assert resolve_resp.status_code == 200
    resolved_data = resolve_resp.json()
    resolved_last_seen = resolved_data["last_seen"]
    resolved_event_count = resolved_data["event_count"]

    # Ingest 1 error log post-resolution
    resp = await async_client.post("/api/v1/logs/ingest", json={
        "service_name": service,
        "level": "ERROR",
        "message": err_msg
    }, headers=user["headers"])
    assert resp.status_code == 201

    # Verify resolved incident is unchanged
    check_resp = await async_client.get(f"/api/v1/incidents/{inc_id}", headers=user["headers"])
    chk = check_resp.json()
    assert chk["status"] == "RESOLVED"
    assert chk["event_count"] == resolved_event_count
    assert chk["last_seen"] == resolved_last_seen


@pytest.mark.asyncio
async def test_transaction_retry_reads_fresh_incident_state():
    """
    Test 5: Transaction retries read fresh incident state inside the session.
    Verifies that when an active incident is updated, fresh state (severity, timestamps)
    is fetched inside the transaction attempt, ensuring concurrent escalations are preserved
    and monotonic calculations are applied against live DB state.
    """
    from backend.app.services.incident_detection_service import IncidentDetectionService
    from backend.app.services.error_signature import ErrorSignatureGenerator
    from bson import ObjectId

    db = MongoDBManager.get_database()
    now = datetime.now(timezone.utc)
    user_id = str(ObjectId())
    svc = f"tx-fresh-{uuid.uuid4().hex[:6]}"
    env = "production"
    msg = "Connection pool exhausted during peak traffic"
    sig = ErrorSignatureGenerator.generate(svc, env, msg)
    inc_id = IncidentDetectionService.generate_incident_id()

    # 1. Existing active incident starts at LOW severity with event_count = 3
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

    # 2. Ingest 4th log (an ERROR log, which on its own would NOT escalate severity)
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

    # 3. Simulate another concurrent worker escalating the incident to CRITICAL in the DB
    # before worker processes log_doc
    await db["incidents"].update_one(
        {"incident_id": inc_id},
        {"$set": {"severity": "CRITICAL"}}
    )

    # 4. Now process log_doc through IncidentDetectionService
    res_inc_id = await IncidentDetectionService.process_log_for_detection(db, user_id, log_doc["_id"])
    assert res_inc_id == inc_id

    # 5. Verify the fresh read inside the transaction preserved CRITICAL severity
    updated_inc = await db["incidents"].find_one({"incident_id": inc_id})
    assert updated_inc["severity"] == "CRITICAL", (
        f"Expected CRITICAL severity preserved from fresh read, but got {updated_inc['severity']}!"
    )
    assert updated_inc["event_count"] == 4


@pytest.mark.asyncio
async def test_branch_b_race_resolution_uses_fresh_state():
    """
    Test 6: Branch B race resolution uses fresh race winner state inside the transaction.
    When two workers simultaneously evaluate logs:
    - Worker 1 creates the active incident.
    - An intermediary worker concurrently escalates it to CRITICAL.
    - Worker 2 encounters duplicate key / conflict and resolves against the race winner.
    - Inside the retry transaction, Worker 2 reads the freshly escalated CRITICAL state,
      monotonic timestamps, and links its logs without downgrading severity.
    """
    from backend.app.services.incident_detection_service import IncidentDetectionService
    from backend.app.services.error_signature import ErrorSignatureGenerator
    from bson import ObjectId

    db = MongoDBManager.get_database()
    now = datetime.now(timezone.utc)
    user_id = str(ObjectId())
    svc = f"branch-b-race-{uuid.uuid4().hex[:6]}"
    env = "production"
    msg = "Deadlock on row lock index scan"
    sig = ErrorSignatureGenerator.generate(svc, env, msg)

    # Insert 3 logs (threshold = 3)
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
            "timestamp": now - timedelta(seconds=30 - i * 10),
            "detection_status": "PENDING",
            "incident_id": None,
        }
        await db["logs"].insert_one(doc)
        log_ids.append(doc["_id"])

    # Worker 1 processes log 0, 1, 2:
    await IncidentDetectionService.process_log_for_detection(db, user_id, log_ids[0])
    await IncidentDetectionService.process_log_for_detection(db, user_id, log_ids[1])
    winner_inc_id = await IncidentDetectionService.process_log_for_detection(db, user_id, log_ids[2])
    assert winner_inc_id is not None

    # Concurrently escalate winner incident to CRITICAL
    await db["incidents"].update_one(
        {"incident_id": winner_inc_id},
        {"$set": {"severity": "CRITICAL"}}
    )

    # Insert 4th log (an ERROR log) that will be processed into the existing incident
    log_doc_4 = {
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
    await db["logs"].insert_one(log_doc_4)

    # Process log 4
    res_id = await IncidentDetectionService.process_log_for_detection(db, user_id, log_doc_4["_id"])
    assert res_id == winner_inc_id

    # Verify that fresh state was used and CRITICAL was NOT downgraded to LOW
    final_inc = await db["incidents"].find_one({"incident_id": winner_inc_id})
    assert final_inc["severity"] == "CRITICAL"
    assert final_inc["event_count"] == 4

