from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from backend.app.models.user import UserRole


class UserRegisterRequest(BaseModel):
    """
    Schema for new user registration requests.
    Role is strictly omitted; all publicly registered users receive the 'engineer' role.
    Extra fields (e.g. attempting to pass 'role') are forbidden to prevent privilege escalation.
    """
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters and maximum 72 UTF-8 bytes."
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full name of the DevOps engineer or user."
    )

    @field_validator("password")
    @classmethod
    def validate_password_byte_length(cls, v: str) -> str:
        """
        Validates password byte length against bcrypt's 72-byte limit.
        Multibyte characters (e.g., emojis or UTF-8 non-ASCII) count as multiple bytes.
        """
        byte_length = len(v.encode("utf-8"))
        if byte_length < 8:
            raise ValueError("Password must be at least 8 bytes.")
        if byte_length > 72:
            raise ValueError(
                f"Password exceeds bcrypt maximum of 72 bytes ({byte_length} bytes received). "
                "Please shorten your password."
            )
        return v


class UserLoginRequest(BaseModel):
    """
    Schema for user login credentials.
    """
    email: EmailStr
    password: str = Field(..., min_length=1)

    @field_validator("password")
    @classmethod
    def validate_password_byte_length(cls, v: str) -> str:
        byte_length = len(v.encode("utf-8"))
        if byte_length > 72:
            raise ValueError(
                f"Password exceeds bcrypt maximum of 72 bytes ({byte_length} bytes received)."
            )
        return v


class TokenResponse(BaseModel):
    """
    Schema for successful JWT authentication token response.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    role: UserRole


class UserResponse(BaseModel):
    """
    Public user representation.
    Explicitly omits hashed_password to prevent credential leakage.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
