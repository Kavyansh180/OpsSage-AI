from fastapi import APIRouter, Depends, status
from pymongo.asynchronous.database import AsyncDatabase
from backend.app.core.dependencies import get_current_user, get_db, require_role
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from backend.app.services.auth_service import AuthService

router = APIRouter(tags=["Authentication & Users"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
async def register(
    user_in: UserRegisterRequest,
    db: AsyncDatabase = Depends(get_db)
) -> UserResponse:
    """
    Registers a new DevOps engineer, admin, or viewer.
    Hashes the password with bcrypt and stores the record in MongoDB Atlas.
    """
    return await AuthService.register_user(db, user_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive JWT token"
)
async def login(
    credentials: UserLoginRequest,
    db: AsyncDatabase = Depends(get_db)
) -> TokenResponse:
    """
    Authenticates user credentials and issues a signed JWT access token.
    """
    user = await AuthService.authenticate_user(db, credentials)
    return AuthService.create_token_response(user)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get profile of authenticated user"
)
async def get_current_user_profile(
    current_user: UserInDB = Depends(get_current_user)
) -> UserResponse:
    """
    Returns the profile of the currently authenticated user.
    Strictly excludes password hash.
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.get(
    "/admin-only",
    summary="Admin role test endpoint"
)
async def test_admin_rbac(
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN))
) -> dict:
    """
    Verifies that RBAC allows only 'admin' role to access this route.
    """
    return {
        "status": "success",
        "message": "Admin authorization confirmed.",
        "admin_email": current_user.email,
    }
