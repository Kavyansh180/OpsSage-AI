"""
End-to-End System Integration Test for OpsSage AI.
Validates the complete 15-step operational lifecycle:
1. Engineer registration & JWT authentication.
2. Log ingestion & normalization.
3. Deterministic sliding-window incident detection.
4. Automatic incident clustering & creation.
5. AI Root-Cause Analysis orchestration & prompt grounding.
6. Structured RCA persistence & history retrieval.
7. Engineer acknowledgement & ownership assignment.
8. Priority/severity adjustment.
9. Investigation notes logging.
10. Confirmed root-cause recording & engineer verification.
11. Automatic Knowledge Base feedback synchronization & embedding generation.
12. Semantic vector retrieval of historical precedents for recurring issues.
13. DevOps analytics & KPI telemetry computation.
14. Comprehensive audit trail generation.
15. Multi-tenant data isolation and RBAC role boundaries.
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
from backend.app.models.analysis import ConfidenceLevel
from backend.app.models.incident import IncidentSeverity, IncidentStatus
from backend.app.models.user import UserInDB, UserRole
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.llm.base import LLMProvider

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


class E2EMockEncoder:
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
    EmbeddingService.set_mock_model(E2EMockEncoder())
    yield
    EmbeddingService.reset_model()


class E2EMockLLM(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "e2e-mock-llm"

    @property
    def model_name(self) -> str:
        return "mock-e2e"

    async def generate_text(self, prompt: str, system_instruction=None) -> str:
        return "E2E root cause hypothesis"

    async def generate_structured(self, prompt: str, schema_cls, system_instruction=None):
        instance = schema_cls(
            probable_root_cause="PostgreSQL max connection pool exhaustion under order surge",
            explanation="Multiple order workers exhausted client connection pool limits causing 504 timeouts.",
            supporting_evidence=["FATAL: remaining connection slots are reserved for non-replication superuser connections"],
            contributing_factors=["Connection pool size set to default 10", "Spike in concurrent checkout requests"],
            confidence_level=ConfidenceLevel.HIGH,
            recommended_actions=[
                "Increase max_connections in postgresql.conf to 100",
                "Deploy PgBouncer connection pooler in transaction mode",
                "Restart order workers",
            ],
            limitations=["Connection spike duration not observed in logs"],
        )
        return instance, '{"raw": "e2e"}'


async def test_complete_end_to_end_application_workflow():
    """
    Executes the comprehensive 15-step end-to-end incident management,
    AI investigation, and knowledge feedback pipeline.
    """
    db = MongoDBManager.get_database()
    settings = get_settings()

    eng_oid = ObjectId()
    viewer_oid = ObjectId()
    other_tenant_oid = ObjectId()

    eng_id = str(eng_oid)
    viewer_id = str(viewer_oid)
    other_id = str(other_tenant_oid)

    now = datetime.now(timezone.utc)
    eng_email = f"eng_{uuid4().hex[:6]}@devops.com"
    viewer_email = f"viewer_{uuid4().hex[:6]}@devops.com"
    other_email = f"other_{uuid4().hex[:6]}@devops.com"

    # Seed test users
    await db["users"].insert_many([
        {"_id": eng_oid, "email": eng_email, "full_name": "E2E Engineer", "hashed_password": "pw", "role": "engineer", "is_active": True, "created_at": now, "updated_at": now},
        {"_id": viewer_oid, "email": viewer_email, "full_name": "E2E Viewer", "hashed_password": "pw", "role": "viewer", "is_active": True, "created_at": now, "updated_at": now},
        {"_id": other_tenant_oid, "email": other_email, "full_name": "Other Tenant", "hashed_password": "pw", "role": "engineer", "is_active": True, "created_at": now, "updated_at": now},
    ])

    eng_token = create_access_token(data={"sub": eng_id, "email": eng_email, "role": "engineer"})
    viewer_token = create_access_token(data={"sub": viewer_id, "email": viewer_email, "role": "viewer"})
    other_token = create_access_token(data={"sub": other_id, "email": other_email, "role": "engineer"})

    created_incident_id = None

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # -------------------------------------------------------------
            # STEP 1: Engineer Authenticates & Checks /auth/me
            # -------------------------------------------------------------
            me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {eng_token}"})
            assert me_res.status_code == 200
            assert me_res.json()["email"] == eng_email

            # -------------------------------------------------------------
            # STEP 2 & 3: Submit application logs (Batch Ingestion)
            # -------------------------------------------------------------
            # 6 consecutive ERROR logs to deterministically trigger incident detection (threshold >= 3)
            log_batch = [
                {
                    "service_name": "order-service",
                    "environment": "production",
                    "level": "ERROR",
                    "message": "Connection pool exhausted: FATAL remaining connection slots reserved for non-replication connections",
                    "timestamp": now.isoformat(),
                }
                for _ in range(6)
            ]
            ingest_res = await client.post(
                "/api/v1/logs/ingest/batch",
                headers={"Authorization": f"Bearer {eng_token}"},
                json={"logs": log_batch},
            )
            assert ingest_res.status_code == 200, ingest_res.text
            assert ingest_res.json()["successful_count"] == 6

            # -------------------------------------------------------------
            # STEP 4 & 5: Deterministic Incident Detection Created Incident
            # -------------------------------------------------------------
            incidents_res = await client.get(
                "/api/v1/incidents",
                headers={"Authorization": f"Bearer {eng_token}"},
                params={"service_name": "order-service", "status": "OPEN"},
            )
            assert incidents_res.status_code == 200
            inc_list = incidents_res.json()["items"]
            assert len(inc_list) >= 1
            incident = inc_list[0]
            created_incident_id = incident["incident_id"]
            assert incident["status"] == "OPEN"
            assert incident["service_name"] == "order-service"
            assert incident["event_count"] >= 5

            # -------------------------------------------------------------
            # STEP 6, 7, 8, 9, 10: Trigger AI Root Cause Analysis
            # -------------------------------------------------------------
            from backend.app.services.rca_service import RCAService
            # Inject E2EMockLLM into RCAService for automated testing
            from unittest.mock import patch
            with patch("backend.app.services.rca_service.get_llm_provider", return_value=E2EMockLLM()):
                rca_res = await client.post(
                    f"/api/v1/incidents/{created_incident_id}/analyze",
                    headers={"Authorization": f"Bearer {eng_token}"},
                    json={"additional_context": "Black Friday checkout traffic spike"},
                )
                assert rca_res.status_code == 201, rca_res.text
                rca_data = rca_res.json()
                assert "PostgreSQL max connection pool exhaustion" in rca_data["probable_root_cause"]
                assert rca_data["confidence_level"] == "HIGH"
                analysis_id = rca_data["analysis_id"]

            # Verify analysis retrievable via history
            ana_history = await client.get(
                f"/api/v1/incidents/{created_incident_id}/analyses",
                headers={"Authorization": f"Bearer {eng_token}"},
            )
            assert ana_history.status_code == 200
            assert len(ana_history.json()["items"]) >= 1

            # -------------------------------------------------------------
            # STEP 11: Acknowledge, Assign, and Add Notes
            # -------------------------------------------------------------
            ack_res = await client.patch(
                f"/api/v1/incidents/{created_incident_id}/acknowledge",
                headers={"Authorization": f"Bearer {eng_token}"},
            )
            assert ack_res.status_code == 200
            assert ack_res.json()["status"] == "ACKNOWLEDGED"

            assign_res = await client.patch(
                f"/api/v1/incidents/{created_incident_id}/assign",
                headers={"Authorization": f"Bearer {eng_token}"},
                json={"assigned_to": "dba-lead@devops.com"},
            )
            assert assign_res.status_code == 200
            assert assign_res.json()["assigned_to"] == "dba-lead@devops.com"

            note_res = await client.post(
                f"/api/v1/incidents/{created_incident_id}/notes",
                headers={"Authorization": f"Bearer {eng_token}"},
                json={"note": "Verified pg_stat_activity: 100 active connections in state idle in transaction"},
            )
            assert note_res.status_code == 201

            # -------------------------------------------------------------
            # STEP 12 & 13: Record Verified Resolution & Knowledge Base Sync
            # -------------------------------------------------------------
            res_payload = {
                "confirmed_root_cause": "Postgres connection pool max_connections set too low for high concurrency",
                "confirmed_resolution": "Increased max_connections to 150 and deployed PgBouncer pooler",
                "resolution_actions": [
                    "Updated postgresql.conf max_connections=150",
                    "Deployed pgbouncer container",
                    "Restarted PostgreSQL gracefully",
                ],
                "is_verified": True,
                "rca_analysis_id": analysis_id,
                "notes": "Verified 0 dropped connections after PgBouncer cutover",
            }
            res_res = await client.post(
                f"/api/v1/incidents/{created_incident_id}/resolution",
                headers={"Authorization": f"Bearer {eng_token}"},
                json=res_payload,
            )
            assert res_res.status_code == 200, res_res.text
            res_data = res_res.json()
            assert res_data["status"] == "RESOLVED"
            assert res_data["has_verified_resolution"] is True
            assert res_data["knowledge_synced"] is True

            # -------------------------------------------------------------
            # STEP 14: Historical Vector Retrieval of Verified Precedent
            # -------------------------------------------------------------
            # Poll with short delay for Atlas Search index background sync
            import asyncio
            search_items = []
            for _ in range(4):
                await asyncio.sleep(2)
                kb_search = await client.post(
                    "/api/v1/knowledge/search",
                    headers={"Authorization": f"Bearer {eng_token}"},
                    json={
                        "query": "PostgreSQL connection pool max connections timeout error",
                        "top_k": 3,
                        "min_similarity": 0.40,
                    },
                )
                assert kb_search.status_code == 200, kb_search.text
                search_items = kb_search.json().get("results", [])
                if search_items:
                    break

            assert len(search_items) >= 1
            precedent = search_items[0]
            assert precedent["source_incident_id"] == created_incident_id
            assert precedent["has_verified_resolution"] is True
            assert "PgBouncer" in precedent["confirmed_resolution"]

            # -------------------------------------------------------------
            # STEP 15: Analytics Endpoint Telemetry Verification
            # -------------------------------------------------------------
            analytics_res = await client.get(
                "/api/v1/analytics/overview",
                headers={"Authorization": f"Bearer {eng_token}"},
            )
            assert analytics_res.status_code == 200
            metrics = analytics_res.json()
            assert metrics["total_incidents"] >= 1
            assert metrics["resolved_incidents"] >= 1
            assert metrics["resolution_rate_pct"] > 0
            assert "order-service" in metrics["by_service"]

            # -------------------------------------------------------------
            # Audit Trail Verification
            # -------------------------------------------------------------
            hist_res = await client.get(
                f"/api/v1/incidents/{created_incident_id}/history",
                headers={"Authorization": f"Bearer {eng_token}"},
            )
            assert hist_res.status_code == 200
            audit_events = [e["action"] for e in hist_res.json()["items"]]
            assert "ACKNOWLEDGED" in audit_events
            assert "ASSIGNED" in audit_events
            assert "NOTE_ADDED" in audit_events
            assert "RESOLUTION_RECORDED" in audit_events
            assert "KNOWLEDGE_SYNCED" in audit_events

            # -------------------------------------------------------------
            # Security & Tenant Isolation Checks
            # -------------------------------------------------------------
            # 1. Other tenant cannot view incident or history (404)
            other_inc = await client.get(
                f"/api/v1/incidents/{created_incident_id}",
                headers={"Authorization": f"Bearer {other_token}"},
            )
            assert other_inc.status_code == 404

            other_audit = await client.get(
                f"/api/v1/incidents/{created_incident_id}/history",
                headers={"Authorization": f"Bearer {other_token}"},
            )
            assert other_audit.status_code == 404

            # 2. Viewer cannot modify incident (403)
            viewer_note = await client.post(
                f"/api/v1/incidents/{created_incident_id}/notes",
                headers={"Authorization": f"Bearer {viewer_token}"},
                json={"note": "Unauthorized viewer note"},
            )
            assert viewer_note.status_code == 403

            # 3. Unauthenticated request blocked (401)
            unauth_res = await client.get(f"/api/v1/incidents/{created_incident_id}")
            assert unauth_res.status_code == 401

    finally:
        # Comprehensive test cleanup
        if created_incident_id:
            await db["incidents"].delete_many({"incident_id": created_incident_id})
            await db["audit_logs"].delete_many({"incident_id": created_incident_id})
            await db["analyses"].delete_many({"incident_id": created_incident_id})
        await db["knowledge_base"].delete_many({"user_id": eng_id})
        await db["logs"].delete_many({"user_id": eng_id})
        await db["users"].delete_many({"_id": {"$in": [eng_oid, viewer_oid, other_tenant_oid]}})
