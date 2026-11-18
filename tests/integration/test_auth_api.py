import uuid
from datetime import timedelta
import pytest
from bson import ObjectId
from httpx import AsyncClient
from backend.app.core.security import create_access_token
from backend.app.db.mongodb import MongoDBManager
from backend.app.models.user import UserRole
from backend.app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_user_registration_and_login_flow(async_client: AsyncClient):
    """
    Test standard user registration, duplicate rejection, and login flow.
    """
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"engineer_{unique_suffix}@company.com"
    password = "DevOpsTestPassword123!"

    # 1. Register new user
    register_payload = {
        "email": email,
        "password": password,
        "full_name": "Test DevOps Engineer"
    }
    reg_response = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert reg_response.status_code == 201
    user_data = reg_response.json()
    assert user_data["email"] == email
    assert user_data["full_name"] == "Test DevOps Engineer"
    assert user_data["role"] == "engineer"
    assert "id" in user_data
    # CRITICAL: hashed_password must never be returned in response!
    assert "hashed_password" not in user_data

    # 2. Duplicate registration attempt should be rejected with 409 Conflict
    dup_response = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert dup_response.status_code == 409
    assert dup_response.json()["success"] is False

    # 3. Successful Login
    login_payload = {
        "email": email,
        "password": password
    }
    login_response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["role"] == "engineer"
    token = token_data["access_token"]

    # 4. Access /me protected endpoint with valid Bearer token
    headers = {"Authorization": f"Bearer {token}"}
    me_response = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == email
    assert me_data["role"] == "engineer"
    assert "hashed_password" not in me_data


@pytest.mark.asyncio
async def test_registration_privilege_escalation_blocked(async_client: AsyncClient):
    """
    SECURITY TEST: An attacker attempting to register with {"role": "admin"}
    must be rejected by Pydantic extra='forbid' validation (422 Unprocessable Entity).
    """
    unique_suffix = uuid.uuid4().hex[:8]
    escalation_payload = {
        "email": f"hacker_{unique_suffix}@company.com",
        "password": "HackerPassword123!",
        "full_name": "Privilege Escalator",
        "role": "admin"  # Attempting to grant self admin role
    }

    response = await async_client.post("/api/v1/auth/register", json=escalation_payload)
    assert response.status_code == 422
    # Verify rejection mentions extra forbidden field
    assert "extra_forbidden" in str(response.json()) or "role" in str(response.json())


@pytest.mark.asyncio
async def test_password_validation_multibyte_limits(async_client: AsyncClient):
    """
    Test bcrypt password limits:
    - Less than 8 characters -> 422
    - Multibyte characters exceeding 72 bytes -> 422
    - Multibyte characters exactly within 72 bytes -> 201 Created
    """
    unique_suffix = uuid.uuid4().hex[:8]

    # 1. Less than 8 characters
    short_pw_resp = await async_client.post("/api/v1/auth/register", json={
        "email": f"short_{unique_suffix}@company.com",
        "password": "short",
        "full_name": "Short Password User"
    })
    assert short_pw_resp.status_code == 422

    # 2. 19 emojis: 19 * 4 bytes = 76 bytes (> 72-byte limit) -> Rejected
    long_mb_resp = await async_client.post("/api/v1/auth/register", json={
        "email": f"long_mb_{unique_suffix}@company.com",
        "password": "🔒" * 19,
        "full_name": "Long Multibyte User"
    })
    assert long_mb_resp.status_code == 422
    assert "72 bytes" in str(long_mb_resp.json())

    # 3. 18 emojis: 18 * 4 bytes = 72 bytes (<= 72-byte limit) -> Allowed
    valid_mb_resp = await async_client.post("/api/v1/auth/register", json={
        "email": f"valid_mb_{unique_suffix}@company.com",
        "password": "🔒" * 18,
        "full_name": "Valid Multibyte User"
    })
    assert valid_mb_resp.status_code == 201


@pytest.mark.asyncio
async def test_deactivated_user_blocked(async_client: AsyncClient):
    """
    Verify that a deactivated user:
    - Cannot log in (403 Forbidden)
    - Cannot access protected routes even with an active token (403 Forbidden)
    """
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"deactivated_{unique_suffix}@company.com"
    password = "ActivePassword123!"

    # Register and get token while active
    reg = await async_client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Soon Deactivated"
    })
    user_id = reg.json()["id"]

    token = (await async_client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })).json()["access_token"]

    # Deactivate in database directly
    db = MongoDBManager.get_database()
    await db["users"].update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": False}})

    # Attempt to use existing token -> 403 Forbidden
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 403
    assert "deactivated" in me_resp.json()["message"].lower()

    # Attempt new login -> 403 Forbidden
    login_resp = await async_client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login_resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthorized_and_invalid_tokens(async_client: AsyncClient):
    """
    Verify protected endpoint defense against:
    - Missing Authorization header
    - Malformed token
    - Expired token
    """
    # 1. Missing header
    res_missing = await async_client.get("/api/v1/auth/me")
    assert res_missing.status_code == 401

    # 2. Malformed token
    res_malformed = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this.is.notavalidjwt"}
    )
    assert res_malformed.status_code == 401

    # 3. Expired token
    expired_token = create_access_token(
        data={"sub": str(ObjectId())},
        expires_delta=timedelta(seconds=-60)
    )
    res_expired = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert res_expired.status_code == 401
    assert "expired" in res_expired.json()["message"].lower()


@pytest.mark.asyncio
async def test_role_based_access_control(async_client: AsyncClient):
    """
    Test RBAC authorization:
    - Engineer role is forbidden from /admin-only (403)
    - Admin created via privileged AuthService is allowed on /admin-only (200)
    """
    unique_suffix = uuid.uuid4().hex[:8]

    # Create Engineer via public endpoint
    eng_email = f"eng_{unique_suffix}@company.com"
    await async_client.post("/api/v1/auth/register", json={
        "email": eng_email,
        "password": "Password123!",
        "full_name": "Engineer User"
    })
    eng_login = await async_client.post("/api/v1/auth/login", json={
        "email": eng_email,
        "password": "Password123!"
    })
    eng_token = eng_login.json()["access_token"]

    # Provision Admin via privileged AuthService
    db = MongoDBManager.get_database()
    admin_email = f"admin_{unique_suffix}@company.com"
    await AuthService.create_user_with_role(
        db=db,
        email=admin_email,
        password="AdminPassword123!",
        full_name="Admin User",
        role=UserRole.ADMIN
    )
    admin_login = await async_client.post("/api/v1/auth/login", json={
        "email": admin_email,
        "password": "AdminPassword123!"
    })
    admin_token = admin_login.json()["access_token"]

    # 1. Engineer attempting admin route -> 403 Forbidden
    eng_headers = {"Authorization": f"Bearer {eng_token}"}
    eng_admin_attempt = await async_client.get("/api/v1/auth/admin-only", headers=eng_headers)
    assert eng_admin_attempt.status_code == 403
    assert "forbidden" in eng_admin_attempt.json()["message"].lower()

    # 2. Admin attempting admin route -> 200 OK
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_attempt = await async_client.get("/api/v1/auth/admin-only", headers=admin_headers)
    assert admin_attempt.status_code == 200
    assert admin_attempt.json()["status"] == "success"
    assert admin_attempt.json()["admin_email"] == admin_email


@pytest.mark.asyncio
async def test_duplicate_key_error_race_condition():
    """
    Simulate concurrent race condition where find_one returns None,
    but insert_one raises DuplicateKeyError due to concurrent write.
    Asserts that AuthService catches DuplicateKeyError and returns 409 Conflict.
    """
    from unittest.mock import AsyncMock
    from pymongo.errors import DuplicateKeyError
    from backend.app.core.exceptions import AppException
    from backend.app.schemas.auth import UserRegisterRequest

    mock_db = {}
    mock_users_collection = AsyncMock()
    mock_users_collection.find_one.return_value = None
    mock_users_collection.insert_one.side_effect = DuplicateKeyError("E11000 duplicate key error")
    mock_db["users"] = mock_users_collection

    user_req = UserRegisterRequest(
        email="race_condition@company.com",
        password="ValidPassword123!",
        full_name="Race Condition"
    )

    with pytest.raises(AppException) as exc_info:
        await AuthService.register_user(mock_db, user_req)

    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.message.lower()

