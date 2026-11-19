"""
Live Database Integration Tests for Incident Management & Knowledge Feedback (Module 6).
Requires a live MongoDB Atlas connection.
"""
from datetime import datetime, timezone
from uuid import uuid4
from bson import ObjectId
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.config import get_settings
from backend.app.core.security import create_access_token
from backend.app.db.mongodb import MongoDBManager
from backend.app.main import app
from backend.app.models.incident import IncidentSeverity, IncidentStatus
from backend.app.models.user import UserInDB, UserRole
from backend.app.services.embedding_service import EmbeddingService

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


class IntegrationMockEncoder:
    """Provides deterministic 384-dimensional unit vectors for fast live integration tests."""
    def encode(self, texts, **kwargs):
        if isinstance(texts, str):
            vec = [0.0] * 384
            vec[0] = 1.0
            return vec
        else:
            vectors = []
            for _ in texts:
                vec = [0.0] * 384
                vec[0] = 1.0
                vectors.append(vec)
            return vectors


@pytest.fixture(autouse=True)
def inject_fast_encoder():
    EmbeddingService.set_mock_model(IntegrationMockEncoder())
    yield
    EmbeddingService.reset_model()


async def test_live_incident_management_workflow_and_kb_feedback():
    """
    Tests the complete Module 6 engineer lifecycle against live MongoDB:
    1. Incident creation -> OPEN.
    2. Acknowledge -> ACKNOWLEDGED.
    3. Assign to engineer.
    4. Update severity.
    5. Add investigation notes.
    6. Record structured resolution -> RESOLVED + auto-sync to knowledge_base.
    7. Verify resolution verification endpoint.
    8. Retrieve audit trail and verify all events recorded.
    9. Multi-tenant isolation checks.
    """
    db = MongoDBManager.get_database()
    settings = get_settings()

    tenant_oid = ObjectId()
    viewer_oid = ObjectId()
    other_tenant_oid = ObjectId()

    tenant_id = str(tenant_oid)
    other_tenant_id = str(other_tenant_oid)
    viewer_id = str(viewer_oid)
    inc_id = f"INC-M6-{uuid4().hex[:8]}"

    engineer_user = UserInDB(
        id=tenant_id,
        email=f"eng_{uuid4().hex[:6]}@example.com",
        full_name="Lead Ops Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    viewer_user = UserInDB(
        id=viewer_id,
        email=f"view_{uuid4().hex[:6]}@example.com",
        full_name="Readonly Auditor",
        hashed_password="pw",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    other_engineer_user = UserInDB(
        id=other_tenant_id,
        email=f"other_{uuid4().hex[:6]}@example.com",
        full_name="Other Tenant Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Insert test users into DB
    now = datetime.now(timezone.utc)
    await db["users"].insert_many([
        {"_id": tenant_oid, "email": engineer_user.email, "full_name": engineer_user.full_name, "hashed_password": "pw", "role": "engineer", "is_active": True, "created_at": now, "updated_at": now},
        {"_id": viewer_oid, "email": viewer_user.email, "full_name": viewer_user.full_name, "hashed_password": "pw", "role": "viewer", "is_active": True, "created_at": now, "updated_at": now},
        {"_id": other_tenant_oid, "email": other_engineer_user.email, "full_name": other_engineer_user.full_name, "hashed_password": "pw", "role": "engineer", "is_active": True, "created_at": now, "updated_at": now},
    ])

    # Insert initial incident
    incident_doc = {
        "incident_id": inc_id,
        "user_id": tenant_id,
        "service_name": "order-processor",
        "environment": "production",
        "severity": "HIGH",
        "status": "OPEN",
        "title": "Kafka partition consumer offset lag spike",
        "error_signature": f"sig-{uuid4().hex[:12]}",
        "first_seen": datetime.now(timezone.utc),
        "last_seen": datetime.now(timezone.utc),
        "event_count": 12,
        "window_event_count": 12,
        "related_log_ids": [],
        "investigation_notes": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db["incidents"].insert_one(incident_doc)

    eng_token = create_access_token(
        data={"sub": engineer_user.id, "email": engineer_user.email, "role": engineer_user.role.value}
    )
    viewer_token = create_access_token(
        data={"sub": viewer_user.id, "email": viewer_user.email, "role": viewer_user.role.value}
    )
    other_token = create_access_token(
        data={"sub": other_engineer_user.id, "email": other_engineer_user.email, "role": other_engineer_user.role.value}
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Acknowledge incident
        ack_res = await client.patch(
            f"/api/v1/incidents/{inc_id}/acknowledge",
            headers={"Authorization": f"Bearer {eng_token}"},
        )
        assert ack_res.status_code == 200, ack_res.text
        data = ack_res.json()
        assert data["status"] == "ACKNOWLEDGED"
        assert data["acknowledged_by"] == tenant_id

        # 2. Viewer cannot assign (403 Forbidden)
        forbidden_assign = await client.patch(
            f"/api/v1/incidents/{inc_id}/assign",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"assigned_to": "engineer@example.com"},
        )
        assert forbidden_assign.status_code == 403

        # 3. Engineer assigns to colleague
        assign_res = await client.patch(
            f"/api/v1/incidents/{inc_id}/assign",
            headers={"Authorization": f"Bearer {eng_token}"},
            json={"assigned_to": "oncall-dev@example.com"},
        )
        assert assign_res.status_code == 200, assign_res.text
        assert assign_res.json()["assigned_to"] == "oncall-dev@example.com"

        # 4. Update severity to CRITICAL
        sev_res = await client.patch(
            f"/api/v1/incidents/{inc_id}/severity",
            headers={"Authorization": f"Bearer {eng_token}"},
            json={"severity": "CRITICAL"},
        )
        assert sev_res.status_code == 200, sev_res.text
        assert sev_res.json()["severity"] == "CRITICAL"

        # 5. Add investigation notes
        note_res = await client.post(
            f"/api/v1/incidents/{inc_id}/notes",
            headers={"Authorization": f"Bearer {eng_token}"},
            json={"note": "Identified consumer rebalance loop caused by heartbeat timeout"},
        )
        assert note_res.status_code == 201, note_res.text
        assert len(note_res.json()["investigation_notes"]) == 1
        assert "heartbeat timeout" in note_res.json()["investigation_notes"][0]["note"]

        # 6. Record structured resolution and verify Knowledge Base synchronization
        res_payload = {
            "confirmed_root_cause": "Consumer heartbeat timeout was too low (3000ms) during heavy GC pauses",
            "confirmed_resolution": "Increased max.poll.interval.ms to 300000 and session.timeout.ms to 45000",
            "resolution_actions": [
                "Updated consumer configuration in helm values",
                "Triggered rolling deployment of order-processor",
                "Verified consumer lag dropped to zero"
            ],
            "is_verified": True,
            "notes": "Post-incident review scheduled with platform team",
        }
        resolve_res = await client.post(
            f"/api/v1/incidents/{inc_id}/resolution",
            headers={"Authorization": f"Bearer {eng_token}"},
            json=res_payload,
        )
        assert resolve_res.status_code == 200, resolve_res.text
        resolved_data = resolve_res.json()
        assert resolved_data["status"] == "RESOLVED"
        assert resolved_data["has_verified_resolution"] is True
        assert resolved_data["confirmed_root_cause"] == res_payload["confirmed_root_cause"]
        assert resolved_data["knowledge_synced"] is True

        # 7. Check that Knowledge Base collection has the indexed document
        kb_doc = await db["knowledge_base"].find_one({
            "user_id": tenant_id,
            "source_incident_id": inc_id,
        })
        assert kb_doc is not None
        assert kb_doc["has_verified_resolution"] is True
        assert kb_doc["confirmed_resolution"] == res_payload["confirmed_resolution"]
        assert kb_doc["confirmed_root_cause"] == res_payload["confirmed_root_cause"]
        assert len(kb_doc["resolution_actions"]) == 3
        assert len(kb_doc["embedding"]) == 384

        # 8. Retrieve audit trail
        history_res = await client.get(
            f"/api/v1/incidents/{inc_id}/history",
            headers={"Authorization": f"Bearer {eng_token}"},
        )
        assert history_res.status_code == 200, history_res.text
        history_data = history_res.json()
        assert history_data["total"] >= 5
        actions = [item["action"] for item in history_data["items"]]
        assert "ACKNOWLEDGED" in actions
        assert "ASSIGNED" in actions
        assert "SEVERITY_UPDATED" in actions
        assert "NOTE_ADDED" in actions
        assert "RESOLUTION_RECORDED" in actions
        assert "KNOWLEDGE_SYNCED" in actions

        # 9. Cross-tenant isolation verification: other tenant cannot read history or modify incident
        other_history = await client.get(
            f"/api/v1/incidents/{inc_id}/history",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert other_history.status_code == 404

        other_note = await client.post(
            f"/api/v1/incidents/{inc_id}/notes",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"note": "Illegal note"},
        )
        assert other_note.status_code == 404

    # Cleanup
    await db["incidents"].delete_one({"incident_id": inc_id})
    await db["knowledge_base"].delete_many({"user_id": tenant_id})
    await db["audit_logs"].delete_many({"incident_id": inc_id})
    await db["users"].delete_many({"_id": {"$in": [tenant_oid, viewer_oid, other_tenant_oid]}})
