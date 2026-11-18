from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from fastapi import status
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError
from backend.app.config import get_settings
from backend.app.core.exceptions import AppException, AuthenticationError, AuthorizationError
from backend.app.core.logging import get_logger
from backend.app.core.security import create_access_token, get_password_hash, verify_password
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.auth import TokenResponse, UserLoginRequest, UserRegisterRequest, UserResponse

logger = get_logger("services.auth")
settings = get_settings()


class AuthService:
    """
    Handles user registration, authentication, token generation, and account lookup.
    """

    @staticmethod
    async def register_user(db: AsyncDatabase, user_in: UserRegisterRequest) -> UserResponse:
        """
        Public user registration.
        SECURITY: All publicly registered users strictly receive the 'engineer' role.
        Handles both pre-check and atomic DuplicateKeyError race conditions.
        """
        normalized_email = user_in.email.lower().strip()

        # 1. Pre-check if user already exists
        existing_user = await db["users"].find_one({"email": normalized_email})
        if existing_user:
            logger.warning(f"Registration attempt with duplicate email: {normalized_email}")
            raise AppException(
                message="A user with this email address already exists.",
                status_code=status.HTTP_409_CONFLICT,
                details={"email": normalized_email}
            )

        # 2. Hash plaintext password
        hashed_password = get_password_hash(user_in.password)

        now = datetime.now(timezone.utc)
        user_doc = {
            "email": normalized_email,
            "hashed_password": hashed_password,
            "full_name": user_in.full_name.strip(),
            # SECURITY: Hardcoded role assignment prevents privilege escalation
            "role": UserRole.ENGINEER.value,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        # 3. Insert into MongoDB with atomic race-condition protection
        try:
            result = await db["users"].insert_one(user_doc)
        except DuplicateKeyError:
            logger.warning(f"Concurrent duplicate registration attempt for email: {normalized_email}")
            raise AppException(
                message="A user with this email address already exists.",
                status_code=status.HTTP_409_CONFLICT,
                details={"email": normalized_email}
            )

        logger.info(f"User registered successfully: {normalized_email} with role 'engineer'")

        return UserResponse(
            id=str(result.inserted_id),
            email=normalized_email,
            full_name=user_doc["full_name"],
            role=UserRole.ENGINEER,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    async def create_user_with_role(
        db: AsyncDatabase,
        email: str,
        password: str,
        full_name: str,
        role: UserRole
    ) -> UserResponse:
        """
        Privileged user creation for administrative scripts (e.g. CLI admin setup).
        NOT exposed via any public or unauthenticated API endpoint.
        """
        normalized_email = email.lower().strip()

        existing_user = await db["users"].find_one({"email": normalized_email})
        if existing_user:
            raise AppException(
                message=f"User with email '{normalized_email}' already exists.",
                status_code=status.HTTP_409_CONFLICT
            )

        hashed_password = get_password_hash(password)
        now = datetime.now(timezone.utc)
        user_doc = {
            "email": normalized_email,
            "hashed_password": hashed_password,
            "full_name": full_name.strip(),
            "role": role.value,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = await db["users"].insert_one(user_doc)
        except DuplicateKeyError:
            raise AppException(
                message=f"User with email '{normalized_email}' already exists.",
                status_code=status.HTTP_409_CONFLICT
            )

        logger.info(f"Privileged user created: {normalized_email} with role '{role.value}'")
        return UserResponse(
            id=str(result.inserted_id),
            email=normalized_email,
            full_name=user_doc["full_name"],
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    async def authenticate_user(db: AsyncDatabase, credentials: UserLoginRequest) -> UserInDB:
        """
        Authenticates a user by email and password.
        Returns the UserInDB model if valid, or raises an AuthenticationError.
        """
        normalized_email = credentials.email.lower().strip()

        user_doc = await db["users"].find_one({"email": normalized_email})
        if not user_doc:
            logger.warning(f"Failed login attempt: email '{normalized_email}' not found.")
            raise AuthenticationError("Invalid email or password.")

        if not verify_password(credentials.password, user_doc["hashed_password"]):
            logger.warning(f"Failed login attempt: invalid password for '{normalized_email}'.")
            raise AuthenticationError("Invalid email or password.")

        if not user_doc.get("is_active", True):
            logger.warning(f"Login denied: account '{normalized_email}' is deactivated.")
            raise AuthorizationError("Your user account has been deactivated. Please contact an administrator.")

        user_doc["_id"] = str(user_doc["_id"])
        return UserInDB(**user_doc)

    @staticmethod
    def create_token_response(user: UserInDB) -> TokenResponse:
        """
        Generates a signed JWT access token for an authenticated user.
        """
        expires_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        payload = {
            "sub": user.id,
            "email": user.email,
            "role": user.role.value,
        }
        token = create_access_token(data=payload)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=expires_seconds,
            user_id=user.id,
            role=user.role,
        )

    @staticmethod
    async def get_user_by_id(db: AsyncDatabase, user_id: str) -> Optional[UserInDB]:
        """
        Retrieves a user by their MongoDB ObjectId string.
        """
        if not ObjectId.is_valid(user_id):
            return None

        user_doc = await db["users"].find_one({"_id": ObjectId(user_id)})
        if not user_doc:
            return None

        user_doc["_id"] = str(user_doc["_id"])
        return UserInDB(**user_doc)
