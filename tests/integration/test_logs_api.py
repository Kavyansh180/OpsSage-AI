import uuid
from datetime import datetime, timezone
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
    return {"email": email, "token": token, "user_id": user_id, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.mark.asyncio
async def test_single_log_ingestion_success(async_client: AsyncClient):
    """
    Test ingesting a single structured log and retrieving it.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)

    payload = {
        "service_name": "payment-gateway",
        "environment": "production",
        "level": "ERROR",
        "message": "Connection timeout for user 12345 to host 10.0.0.5",
        "request_id": "req-9872",
        "trace_id": "trace-101",
        "metadata": {"retry_count": 3}
    }

    response = await async_client.post("/api/v1/logs/ingest", json=payload, headers=user["headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["service_name"] == "payment-gateway"
    assert data["level"] == "ERROR"
    assert data["message"] == payload["message"]
    assert "user <ID>" in data["normalized_message"]
    assert "<IP>" in data["normalized_message"]
    assert data["user_id"] == user["user_id"]
    assert data["request_id"] == "req-9872"
    assert "id" in data

    # Retrieve by ID
    log_id = data["id"]
    get_resp = await async_client.get(f"/api/v1/logs/{log_id}", headers=user["headers"])
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == log_id


@pytest.mark.asyncio
async def test_single_raw_unstructured_log_ingestion(async_client: AsyncClient):
    """
    Test ingesting an unstructured log string parsed via regex.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)

    raw_line = "2026-11-02 10:30:00 ERROR auth-service - Invalid JWT signature for user 99881"
    payload = {"raw_log": raw_line}

    response = await async_client.post("/api/v1/logs/ingest", json=payload, headers=user["headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["service_name"] == "auth-service"
    assert data["level"] == "ERROR"
    assert "Invalid JWT signature" in data["message"]
    assert "user <ID>" in data["normalized_message"]


@pytest.mark.asyncio
async def test_batch_log_ingestion_with_partial_failures(async_client: AsyncClient):
    """
    Test batch ingestion with partial failures:
    - Valid items succeed.
    - Malformed item (empty message) is caught and reported in errors list.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)

    batch_payload = {
        "logs": [
            {
                "service_name": "checkout-service",
                "level": "INFO",
                "message": "Order 101 created successfully"
            },
            {
                # Valid JSON string in raw_log
                "raw_log": '{"service": "inventory-service", "level": "WARN", "message": "Low stock alert for item 443"}'
            },
            {
                # Malformed entry: missing message and raw_log
                "service_name": "faulty-service",
                "level": "DEBUG",
                "message": "   "  # Empty string
            }
        ]
    }

    response = await async_client.post("/api/v1/logs/ingest/batch", json=batch_payload, headers=user["headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["total_received"] == 3
    assert data["successful_count"] == 2
    assert data["failed_count"] == 1
    assert len(data["inserted_ids"]) == 2
    assert len(data["errors"]) == 1
    assert data["errors"][0]["index"] == 2
    assert "empty message" in data["errors"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_batch_ingestion_limits(async_client: AsyncClient):
    """
    Test batch limits:
    - Empty batch -> 422
    - Oversized batch (> 500 records) -> 413
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)

    # 1. Empty batch
    empty_resp = await async_client.post("/api/v1/logs/ingest/batch", json={"logs": []}, headers=user["headers"])
    assert empty_resp.status_code == 422

    # 2. Oversized batch (501 items)
    oversized = [{"message": f"Log message {i}", "service_name": "test"} for i in range(501)]
    oversized_resp = await async_client.post("/api/v1/logs/ingest/batch", json={"logs": oversized}, headers=user["headers"])
    assert oversized_resp.status_code == 413
    assert "exceeds the maximum allowed limit" in oversized_resp.json()["message"]


@pytest.mark.asyncio
async def test_log_filtering_and_pagination(async_client: AsyncClient):
    """
    Test log queries with service_name filter, level filter, and pagination.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)

    # Ingest 4 logs
    logs = [
        {"service_name": "svc-a", "level": "INFO", "message": "Service A message 1"},
        {"service_name": "svc-a", "level": "ERROR", "message": "Service A error 2"},
        {"service_name": "svc-b", "level": "ERROR", "message": "Service B error 3"},
        {"service_name": "svc-b", "level": "DEBUG", "message": "Service B debug 4"},
    ]
    await async_client.post("/api/v1/logs/ingest/batch", json={"logs": logs}, headers=user["headers"])

    # 1. Query svc-a only
    resp_svc_a = await async_client.get("/api/v1/logs?service_name=svc-a", headers=user["headers"])
    assert resp_svc_a.status_code == 200
    data_svc_a = resp_svc_a.json()
    assert data_svc_a["total"] == 2
    assert all(item["service_name"] == "svc-a" for item in data_svc_a["items"])

    # 2. Query ERROR level only
    resp_error = await async_client.get("/api/v1/logs?level=ERROR", headers=user["headers"])
    assert resp_error.status_code == 200
    data_error = resp_error.json()
    assert data_error["total"] == 2
    assert all(item["level"] == "ERROR" for item in data_error["items"])

    # 3. Test pagination: limit=2, offset=0
    resp_page = await async_client.get("/api/v1/logs?limit=2&offset=0", headers=user["headers"])
    assert resp_page.status_code == 200
    data_page = resp_page.json()
    assert len(data_page["items"]) == 2
    assert data_page["total"] >= 4


@pytest.mark.asyncio
async def test_multi_tenant_authorization_isolation(async_client: AsyncClient):
    """
    Test multi-tenant log isolation:
    - User 1 ingests a log.
    - User 2 (engineer) cannot query or see User 1's log (returns 404).
    - Admin can view User 1's log.
    """
    user1 = await create_user_and_token(async_client, UserRole.ENGINEER)
    user2 = await create_user_and_token(async_client, UserRole.ENGINEER)
    admin = await create_user_and_token(async_client, UserRole.ADMIN)

    # User 1 ingests log
    ingest_resp = await async_client.post("/api/v1/logs/ingest", json={
        "service_name": "user1-private-service",
        "message": "Sensitive private transaction data"
    }, headers=user1["headers"])
    log_id = ingest_resp.json()["id"]

    # User 2 tries to fetch User 1's log directly by ID -> 404
    u2_get = await async_client.get(f"/api/v1/logs/{log_id}", headers=user2["headers"])
    assert u2_get.status_code == 404

    # User 2 lists logs -> must NOT see User 1's service
    u2_list = await async_client.get("/api/v1/logs", headers=user2["headers"])
    assert u2_list.status_code == 200
    assert not any(item["id"] == log_id for item in u2_list.json()["items"])

    # Admin CAN view User 1's log by ID -> 200
    admin_get = await async_client.get(f"/api/v1/logs/{log_id}", headers=admin["headers"])
    assert admin_get.status_code == 200
    assert admin_get.json()["id"] == log_id


@pytest.mark.asyncio
async def test_viewer_role_write_restriction(async_client: AsyncClient):
    """
    SECURITY TEST: Viewer accounts are read-only.
    Viewer attempting to ingest single or batch logs must receive 403 Forbidden.
    """
    viewer = await create_user_and_token(async_client, UserRole.VIEWER)

    # Single ingest -> 403
    single_resp = await async_client.post("/api/v1/logs/ingest", json={
        "service_name": "test-service",
        "message": "Viewer attempting log write"
    }, headers=viewer["headers"])
    assert single_resp.status_code == 403

    # Batch ingest -> 403
    batch_resp = await async_client.post("/api/v1/logs/ingest/batch", json={
        "logs": [{"message": "Viewer batch write"}]
    }, headers=viewer["headers"])
    assert batch_resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_requests_blocked(async_client: AsyncClient):
    """
    Verify all log endpoints require authentication.
    """
    assert (await async_client.get("/api/v1/logs")).status_code == 401
    assert (await async_client.get("/api/v1/logs/6ae84bfb788d0cf5262eca51")).status_code == 401
    assert (await async_client.post("/api/v1/logs/ingest", json={"message": "test"})).status_code == 401
    assert (await async_client.post("/api/v1/logs/ingest/batch", json={"logs": []})).status_code == 401


@pytest.mark.asyncio
async def test_batch_ingestion_database_partial_failure(async_client: AsyncClient, monkeypatch):
    """
    Test batch persistence error handling when PyMongo raises BulkWriteError:
    - 4 items submitted:
      0: Valid log
      1: Pre-validation error (empty message)
      2: Valid log (simulated DB failure via BulkWriteError)
      3: Valid log
    - Verifies accurate reporting: 2 succeeded, 2 failed.
    - Preserves exact original batch item indices (1 and 2) in error response.
    - Accurately reports inserted_ids (2 IDs).
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)

    from pymongo.asynchronous.collection import AsyncCollection
    from pymongo.errors import BulkWriteError

    async def mock_insert_many(self, docs, ordered=False):
        # docs[0] succeeds, docs[1] fails (which corresponds to batch item 2), docs[2] succeeds
        raise BulkWriteError({
            "writeErrors": [
                {
                    "index": 1,
                    "code": 11000,
                    "errmsg": "E11000 duplicate key error collection: opssage_ai.logs index: _id_ dup key",
                    "op": docs[1]
                }
            ],
            "nInserted": 2,
            "nUpserted": 0,
            "nMatched": 0,
            "nModified": 0,
            "nRemoved": 0,
            "upserted": []
        })

    monkeypatch.setattr(AsyncCollection, "insert_many", mock_insert_many)

    batch_payload = {
        "logs": [
            {"service_name": "svc-1", "level": "INFO", "message": "Valid log 0"},
            {"service_name": "svc-2", "level": "INFO", "message": "   "},
            {"service_name": "svc-3", "level": "ERROR", "message": "Valid log 2 (DB failure)"},
            {"service_name": "svc-4", "level": "WARN", "message": "Valid log 3"}
        ]
    }

    response = await async_client.post("/api/v1/logs/ingest/batch", json=batch_payload, headers=user["headers"])
    assert response.status_code == 200
    data = response.json()

    assert data["total_received"] == 4
    assert data["successful_count"] == 2
    assert data["failed_count"] == 2
    assert len(data["inserted_ids"]) == 2
    assert len(data["errors"]) == 2

    # Check that error indices accurately match original batch positions
    err_indices = [e["index"] for e in data["errors"]]
    assert err_indices == [1, 2]

    # Error 0 is pre-validation (batch item 1)
    assert "empty message" in data["errors"][0]["reason"].lower()
    # Error 1 is DB failure (batch item 2)
    assert "database insertion failed" in data["errors"][1]["reason"].lower()
    assert "duplicate key" in data["errors"][1]["reason"].lower()


@pytest.mark.asyncio
async def test_log_storage_semantics_and_timestamp_provenance(async_client: AsyncClient):
    """
    Test storage semantics (avoiding duplicate raw_log) and timestamp provenance.
    """
    user = await create_user_and_token(async_client, UserRole.ENGINEER)

    # 1. Clean structured log: raw_log must be None (no duplicate message storage)
    resp1 = await async_client.post("/api/v1/logs/ingest", json={
        "service_name": "api-gateway",
        "level": "INFO",
        "message": "Gateway route mapped successfully"
    }, headers=user["headers"])
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["message"] == "Gateway route mapped successfully"
    assert data1["raw_log"] is None
    assert data1["metadata"].get("timestamp_inferred") is True

    # 2. Raw unparsed log string: raw_log must preserve the original string line
    raw_line = "2026-11-02 10:30:00 ERROR auth-service - Invalid credential attempt"
    resp2 = await async_client.post("/api/v1/logs/ingest", json={
        "raw_log": raw_line
    }, headers=user["headers"])
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["message"] == "Invalid credential attempt"
    assert data2["raw_log"] == raw_line
    assert data2["metadata"].get("timestamp_inferred") is False
    assert data2["metadata"].get("original_timestamp_raw") == "2026-11-02 10:30:00"

    # 3. Invalid timestamp string: falls back to ingestion time, marks inferred, preserves original string
    raw_invalid_ts = '{"timestamp": "2026-99-99-invalid", "service": "billing", "message": "Invoice created"}'
    resp3 = await async_client.post("/api/v1/logs/ingest", json={
        "raw_log": raw_invalid_ts
    }, headers=user["headers"])
    assert resp3.status_code == 201
    data3 = resp3.json()
    assert data3["metadata"].get("timestamp_inferred") is True
    assert data3["metadata"].get("original_timestamp_raw") == "2026-99-99-invalid"
