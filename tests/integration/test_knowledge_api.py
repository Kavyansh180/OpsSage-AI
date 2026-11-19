"""
Live Database Integration Tests for Historical Incident Knowledge Base & RAG (Module 5).
Requires a live MongoDB connection.
"""
from datetime import datetime, timezone
from uuid import uuid4
from bson import ObjectId
import pytest

from backend.app.config import get_settings
from backend.app.db.mongodb import MongoDBManager
from backend.app.models.user import UserInDB, UserRole
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.knowledge_indexer import KnowledgeIndexer
from backend.app.services.knowledge_retriever import KnowledgeRetrievalService

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


async def test_live_mongodb_knowledge_indexing_and_retrieval():
    """
    Verifies end-to-end indexing into MongoDB Atlas 'knowledge_base' collection,
    checking idempotency, document structure, and retrieval against live MongoDB.
    """
    db = MongoDBManager.get_database()
    test_user_id = f"test-rag-user-{uuid4().hex[:8]}"
    test_inc_id = f"INC-RAG-{uuid4().hex[:8]}"

    test_user = UserInDB(
        id=test_user_id,
        email="integration_rag@example.com",
        full_name="RAG Integration Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # 1. Insert incident into live MongoDB
    incident_doc = {
        "incident_id": test_inc_id,
        "user_id": test_user_id,
        "service_name": "inventory-service",
        "environment": "integration-env",
        "severity": "HIGH",
        "status": "RESOLVED",
        "title": "Inventory Redis connection timeout under load",
        "error_signature": f"sig-{uuid4().hex[:12]}",
        "confirmed_resolution": "Increased Redis client connection pool size from 10 to 50",
        "first_seen": datetime.now(timezone.utc),
        "last_seen": datetime.now(timezone.utc),
        "event_count": 8,
        "window_event_count": 8,
        "related_log_ids": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db["incidents"].insert_one(incident_doc)

    try:
        # 2. Index the incident using KnowledgeIndexer
        indexer = KnowledgeIndexer(db=db)
        doc = await indexer.index_incident(
            incident_id=test_inc_id,
            user=test_user,
        )

        assert doc is not None
        assert doc["source_incident_id"] == test_inc_id
        assert doc["user_id"] == test_user_id
        assert doc["has_verified_resolution"] is True
        assert "Increased Redis client connection" in doc["confirmed_resolution"]
        assert len(doc["embedding"]) == 384

        # 3. Verify idempotent re-index does not create duplicate document
        reindex_doc = await indexer.index_incident(
            incident_id=test_inc_id,
            user=test_user,
            force_reindex=False,
        )
        assert reindex_doc["knowledge_id"] == doc["knowledge_id"]

        count = await db["knowledge_base"].count_documents({
            "user_id": test_user_id,
            "source_incident_id": test_inc_id,
        })
        assert count == 1

        # 4. Search and retrieve using KnowledgeRetrievalService (with in-memory fallback enabled for tests)
        retriever = KnowledgeRetrievalService(db=db, allow_in_memory_fallback=True)
        retrieval_res = await retriever.retrieve_similar_incidents(
            incident={"incident_id": "INC-DIFFERENT-999", "service_name": "inventory-service", "title": "Redis timeout"},
            user=test_user,
            min_similarity=0.50,
        )

        assert retrieval_res.status == "SUCCESS"
        assert len(retrieval_res.similar_incidents) >= 1
        matched = next((s for s in retrieval_res.similar_incidents if s.source_incident_id == test_inc_id), None)
        assert matched is not None
        assert matched.has_verified_resolution is True
        assert matched.confirmed_resolution is not None

    finally:
        # Clean up integration test data
        await db["incidents"].delete_one({"incident_id": test_inc_id})
        await db["knowledge_base"].delete_many({"user_id": test_user_id})


async def test_live_mongodb_atlas_vector_search_pure_and_tenant_isolation():
    """
    Explicitly tests pure MongoDB Atlas $vectorSearch (allow_in_memory_fallback=False)
    and verifies strict multi-tenant isolation in the native Atlas vector aggregation.
    """
    db = MongoDBManager.get_database()
    import asyncio

    tenant_a_id = f"tenant-a-{uuid4().hex[:8]}"
    tenant_b_id = f"tenant-b-{uuid4().hex[:8]}"
    inc_a_id = f"INC-ATLAS-{uuid4().hex[:8]}"

    user_a = UserInDB(
        id=tenant_a_id,
        email="tenant_a@example.com",
        full_name="Tenant A Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    user_b = UserInDB(
        id=tenant_b_id,
        email="tenant_b@example.com",
        full_name="Tenant B Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    incident_a = {
        "incident_id": inc_a_id,
        "user_id": tenant_a_id,
        "service_name": "billing-service",
        "environment": "production",
        "severity": "CRITICAL",
        "status": "RESOLVED",
        "title": "Billing gateway timeout during end of month run",
        "error_signature": f"sig-{uuid4().hex[:12]}",
        "confirmed_resolution": "Scaled worker replicas from 2 to 10",
        "first_seen": datetime.now(timezone.utc),
        "last_seen": datetime.now(timezone.utc),
        "event_count": 10,
        "window_event_count": 10,
        "related_log_ids": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db["incidents"].insert_one(incident_a)

    try:
        indexer = KnowledgeIndexer(db=db)
        await indexer.index_incident(incident_id=inc_a_id, user=user_a)

        # Pure Atlas Vector Search: fallback strictly disallowed
        retriever_pure = KnowledgeRetrievalService(db=db, allow_in_memory_fallback=False)

        # 1. Tenant A retrieves similar incident (poll for Atlas Search index eventual consistency)
        res_a = None
        for _ in range(5):
            await asyncio.sleep(2)
            res_a = await retriever_pure.retrieve_similar_incidents(
                incident={"incident_id": "INC-NEW-001", "service_name": "billing-service", "title": "Billing gateway timeout"},
                user=user_a,
                min_similarity=0.40,
            )
            if res_a.status == "SUCCESS":
                break

        assert res_a is not None
        assert res_a.status == "SUCCESS"
        assert res_a.retrieval_method == "ATLAS_VECTOR_SEARCH"
        assert len(res_a.similar_incidents) >= 1
        assert res_a.similar_incidents[0].source_incident_id == inc_a_id

        # 2. Tenant B attempts retrieval with the exact same query
        res_b = await retriever_pure.retrieve_similar_incidents(
            incident={"incident_id": "INC-NEW-002", "service_name": "billing-service", "title": "Billing gateway timeout"},
            user=user_b,
            min_similarity=0.40,
        )
        # Multi-tenant isolation: Tenant B MUST NOT see Tenant A's incident
        assert res_b.status == "EMPTY"
        assert len(res_b.similar_incidents) == 0

    finally:
        await db["incidents"].delete_one({"incident_id": inc_a_id})
        await db["knowledge_base"].delete_many({"user_id": {"$in": [tenant_a_id, tenant_b_id]}})

