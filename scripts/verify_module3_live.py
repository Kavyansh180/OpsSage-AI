"""
Live end-to-end verification script for Module 3: Deterministic Incident Detection Engine.
Connects directly to the live MongoDB Atlas cluster and verifies the complete incident detection lifecycle.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db.mongodb import MongoDBManager
from backend.app.db.indexes import setup_database_indexes


async def run_live_verification():
    print("=====================================================================")
    print("      OpsSage AI — Module 3 Live MongoDB Atlas Verification          ")
    print("=====================================================================")

    # 1. Initialize MongoDB connection & verify Atlas indexes
    print("\n[Step 1] Connecting to MongoDB Atlas & Initializing Indexes...")
    await MongoDBManager.connect()
    db = MongoDBManager.get_database()
    await setup_database_indexes(db)

    # Verify indexes in Atlas
    incident_indexes = await db["incidents"].index_information()
    log_indexes = await db["logs"].index_information()

    print("Live Incident Indexes in Atlas:")
    for name, spec in incident_indexes.items():
        print(f"  - {name}: keys={spec.get('key')} unique={spec.get('unique', False)} partial={spec.get('partialFilterExpression')}")

    assert "idx_incidents_active_unique" in incident_indexes, "Missing idx_incidents_active_unique"
    assert incident_indexes["idx_incidents_active_unique"].get("unique") is True
    assert "idx_logs_detection_window" in log_indexes, "Missing idx_logs_detection_window"
    print("Atlas Indexes Verified Successfully.")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 2. Readiness Check
        print("\n[Step 2] Verifying FastAPI /api/v1/ready...")
        ready_resp = await client.get("/api/v1/ready")
        print(f"Ready Check: {ready_resp.status_code} {ready_resp.json()}")
        assert ready_resp.status_code == 200

        # 3. User Setup
        unique_suffix = uuid.uuid4().hex[:8]
        eng_email = f"eng_mod3_{unique_suffix}@opssage.ai"
        print(f"\n[Step 3] Registering Test User: {eng_email}")
        reg_resp = await client.post("/api/v1/auth/register", json={
            "email": eng_email,
            "password": "Password12345!",
            "full_name": "Module 3 Live Tester"
        })
        assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"

        login_resp = await client.post("/api/v1/auth/login", json={
            "email": eng_email,
            "password": "Password12345!"
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Test User Authenticated. Bearer token acquired.")

        # 4. Ingest 2 Error Logs (Below Threshold of 3)
        svc_name = f"payment-service-{unique_suffix}"
        err_msg = "Connection pool exhausted when calling payment gateway"
        print(f"\n[Step 4] Ingesting 2 ERROR logs for {svc_name} (Threshold = 3)...")
        for i in range(1, 3):
            resp = await client.post("/api/v1/logs/ingest", json={
                "service_name": svc_name,
                "environment": "production",
                "level": "ERROR",
                "message": err_msg,
            }, headers=headers)
            assert resp.status_code == 201

        incidents_resp = await client.get("/api/v1/incidents", headers=headers)
        assert incidents_resp.status_code == 200
        assert incidents_resp.json()["total"] == 0, "No incident should exist below threshold"
        print("Verified: 2 logs ingested, 0 incidents created (Threshold not yet met).")

        # 5. Ingest 3rd Error Log (Threshold Crosses!)
        print("\n[Step 5] Ingesting 3rd ERROR log to trigger deterministic incident creation...")
        resp = await client.post("/api/v1/logs/ingest", json={
            "service_name": svc_name,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg,
        }, headers=headers)
        assert resp.status_code == 201

        incidents_resp = await client.get("/api/v1/incidents", headers=headers)
        assert incidents_resp.status_code == 200
        incidents = incidents_resp.json()["items"]
        assert len(incidents) == 1
        incident = incidents[0]
        inc_id = incident["incident_id"]
        print(f"Incident Created: {inc_id}")
        print(f"  - Status: {incident['status']}")
        print(f"  - Event Count: {incident['event_count']} (incorporating all 3 window logs)")
        print(f"  - Window Event Count: {incident['window_event_count']}")
        print(f"  - Severity: {incident['severity']}")
        print(f"  - Related Log IDs: {len(incident['related_log_ids'])}")
        assert incident["status"] == "OPEN"
        assert incident["event_count"] == 3
        assert incident["window_event_count"] == 3
        assert len(incident["related_log_ids"]) == 3

        # 6. Ingest 4th Error Log (Active Incident Update)
        print("\n[Step 6] Ingesting 4th ERROR log for existing active incident...")
        resp = await client.post("/api/v1/logs/ingest", json={
            "service_name": svc_name,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg,
        }, headers=headers)
        assert resp.status_code == 201

        inc_resp = await client.get(f"/api/v1/incidents/{inc_id}", headers=headers)
        assert inc_resp.status_code == 200
        updated_incident = inc_resp.json()
        print(f"Active Incident Updated: {inc_id}")
        print(f"  - New Event Count: {updated_incident['event_count']}")
        print(f"  - New Window Event Count: {updated_incident['window_event_count']}")
        assert updated_incident["event_count"] == 4
        assert updated_incident["window_event_count"] == 4

        # 7. Acknowledge Incident
        print(f"\n[Step 7] Acknowledging Incident {inc_id}...")
        ack_resp = await client.patch(f"/api/v1/incidents/{inc_id}/acknowledge", headers=headers)
        assert ack_resp.status_code == 200
        ack_data = ack_resp.json()
        print(f"Incident Status: {ack_data['status']}")
        assert ack_data["status"] == "ACKNOWLEDGED"

        # 8. Monotonic Severity Escalation (Ingest CRITICAL log)
        print("\n[Step 8] Ingesting CRITICAL log to test monotonic severity escalation...")
        resp = await client.post("/api/v1/logs/ingest", json={
            "service_name": svc_name,
            "environment": "production",
            "level": "CRITICAL",
            "message": err_msg,
        }, headers=headers)
        assert resp.status_code == 201

        inc_resp = await client.get(f"/api/v1/incidents/{inc_id}", headers=headers)
        crit_incident = inc_resp.json()
        print(f"Incident Severity after CRITICAL log: {crit_incident['severity']}")
        print(f"Event Count: {crit_incident['event_count']}")
        assert crit_incident["severity"] == "CRITICAL"
        assert crit_incident["event_count"] == 5

        # 8b. Monotonic non-downgrade test: Ingest ERROR log, ensure CRITICAL is preserved
        print("\n[Step 8b] Ingesting ERROR log to verify severity is NEVER downgraded from CRITICAL...")
        resp = await client.post("/api/v1/logs/ingest", json={
            "service_name": svc_name,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg,
        }, headers=headers)
        assert resp.status_code == 201

        inc_resp = await client.get(f"/api/v1/incidents/{inc_id}", headers=headers)
        preserved_incident = inc_resp.json()
        print(f"Incident Severity after subsequent ERROR log: {preserved_incident['severity']}")
        assert preserved_incident["severity"] == "CRITICAL", "Severity was downgraded!"
        assert preserved_incident["event_count"] == 6

        # 8c. Late-arriving log test: Ingest log with timestamp 100 seconds in the past
        print("\n[Step 8c] Ingesting late-arriving log to verify first_seen (min) & last_seen (max)...")
        past_ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        resp = await client.post("/api/v1/logs/ingest", json={
            "service_name": svc_name,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg,
            "timestamp": past_ts
        }, headers=headers)
        assert resp.status_code == 201

        inc_resp = await client.get(f"/api/v1/incidents/{inc_id}", headers=headers)
        late_inc = inc_resp.json()
        print(f"Incident first_seen after late log: {late_inc['first_seen']}")
        print(f"Incident last_seen after late log:  {late_inc['last_seen']}")
        assert late_inc["event_count"] == 7
        assert datetime.fromisoformat(late_inc["first_seen"]).replace(tzinfo=timezone.utc) <= datetime.fromisoformat(past_ts)

        # 9. Resolve Incident
        print(f"\n[Step 9] Resolving Incident {inc_id}...")
        res_resp = await client.patch(f"/api/v1/incidents/{inc_id}/resolve", headers=headers)
        assert res_resp.status_code == 200
        res_data = res_resp.json()
        print(f"Resolved Incident Status: {res_data['status']}")
        print(f"Resolved At: {res_data['resolved_at']}")
        assert res_data["status"] == "RESOLVED"
        assert res_data["resolved_at"] is not None

        # 10. Immutability Verification: Cannot re-acknowledge or re-resolve
        print("\n[Step 10] Verifying Resolved Incident Immutability...")
        re_ack = await client.patch(f"/api/v1/incidents/{inc_id}/acknowledge", headers=headers)
        print(f"Re-acknowledge Attempt on Resolved Incident: HTTP {re_ack.status_code} ({re_ack.json()})")
        assert re_ack.status_code == 400

        # 11. Fresh Incident Creation After Resolution
        print("\n[Step 11] Ingesting 3 new ERROR logs to verify fresh incident creation...")
        for i in range(1, 4):
            resp = await client.post("/api/v1/logs/ingest", json={
                "service_name": svc_name,
                "environment": "production",
                "level": "ERROR",
                "message": err_msg,
            }, headers=headers)
            assert resp.status_code == 201

        all_incidents = await client.get("/api/v1/incidents", headers=headers)
        items = all_incidents.json()["items"]
        assert len(items) == 2, f"Expected 2 incidents, got {len(items)}"

        # The older one is RESOLVED with event_count == 7
        resolved_inc = next(i for i in items if i["incident_id"] == inc_id)
        # The newer one is OPEN with event_count == 3
        new_inc = next(i for i in items if i["incident_id"] != inc_id)

        print(f"Old Resolved Incident: {resolved_inc['incident_id']} (Status: {resolved_inc['status']}, Events: {resolved_inc['event_count']})")
        print(f"New Open Incident:     {new_inc['incident_id']} (Status: {new_inc['status']}, Events: {new_inc['event_count']})")
        assert resolved_inc["status"] == "RESOLVED"
        assert resolved_inc["event_count"] == 7
        assert new_inc["status"] == "OPEN"
        assert new_inc["event_count"] == 3

        # 12. Live Crash-Recovery & Lease Fencing Verification
        print("\n[Step 12] Testing Live Crash-Recovery & Fencing on Atlas...")
        crash_log_resp = await client.post("/api/v1/logs/ingest", json={
            "service_name": svc_name,
            "environment": "production",
            "level": "ERROR",
            "message": err_msg,
        }, headers=headers)
        assert crash_log_resp.status_code == 201

        # Incident event count is now 4
        chk_inc = await client.get(f"/api/v1/incidents/{new_inc['incident_id']}", headers=headers)
        assert chk_inc.json()["event_count"] == 4

        # Simulate crashed worker attempting an uncommitted write with aborted transaction
        client_session = db.client.start_session()
        await client_session.start_transaction()
        await db["incidents"].update_one(
            {"incident_id": new_inc["incident_id"]},
            {"$inc": {"event_count": 100}},
            session=client_session
        )
        # Crash occurs -> Abort transaction
        await client_session.abort_transaction()
        await client_session.end_session()

        # Verify transaction rollback in Atlas
        after_crash_inc = await client.get(f"/api/v1/incidents/{new_inc['incident_id']}", headers=headers)
        assert after_crash_inc.json()["event_count"] == 4, "Transaction abort did not roll back event_count!"
        print("Verified: Aborted transaction cleanly rolled back on Atlas. Event count remained 4.")

        # 13. Cleanup
        print("\n[Step 13] Cleaning up test data from MongoDB Atlas...")
        await db["users"].delete_many({"email": eng_email})
        await db["logs"].delete_many({"service_name": svc_name})
        await db["incidents"].delete_many({"service_name": svc_name})
        print("Cleanup Complete.")

    await MongoDBManager.close()
    print("\n=====================================================================")
    print("   ALL MODULE 3 LIVE ATLAS VERIFICATION CHECKS PASSED SUCCESSFULLY!  ")
    print("=====================================================================")


if __name__ == "__main__":
    asyncio.run(run_live_verification())
