from typing import Callable
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from pymongo.asynchronous.database import AsyncDatabase
from backend.app.config import Settings, get_settings
from backend.app.core.exceptions import AuthenticationError, AuthorizationError
from backend.app.core.security import decode_access_token
from backend.app.db.mongodb import get_database
from backend.app.models.user import UserInDB, UserRole

settings = get_settings()

# OAuth2 password bearer scheme for extracting Authorization header
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False
)


async def get_db() -> AsyncDatabase:
    """
    Dependency returning an asynchronous MongoDB database instance.
    """
    return await get_database()


def get_app_settings() -> Settings:
    """
    Dependency returning the cached application settings.
    """
    return get_settings()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncDatabase = Depends(get_db)
) -> UserInDB:
    """
    Validates the JWT bearer token, extracts the user ID ('sub'),
    and queries MongoDB to return the authenticated UserInDB object.
    """
    if not token:
        raise AuthenticationError("Authentication token is missing. Please provide a Bearer token.")

    payload = decode_access_token(token)
    user_id: str = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload: missing subject ('sub').")

    from backend.app.services.auth_service import AuthService
    user = await AuthService.get_user_by_id(db, user_id)
    if not user:
        raise AuthenticationError("Authenticated user account not found in database.")

    if not user.is_active:
        raise AuthorizationError("Your user account has been deactivated.")

    return user


def require_role(*allowed_roles: UserRole) -> Callable:
    """
    Role-Based Access Control (RBAC) dependency factory.
    Enforces that the authenticated user possesses one of the allowed roles.
    """
    async def role_checker(
        current_user: UserInDB = Depends(get_current_user)
    ) -> UserInDB:
        if current_user.role not in allowed_roles:
            role_names = [role.value for role in allowed_roles]
            raise AuthorizationError(
                f"Access forbidden: User role '{current_user.role.value}' is not authorized. "
                f"Required role(s): {role_names}."
            )
        return current_user

    return role_checker
