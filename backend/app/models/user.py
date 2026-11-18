from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    """
    Role-Based Access Control (RBAC) roles.
    """
    ADMIN = "admin"
    ENGINEER = "engineer"
    VIEWER = "viewer"


class UserInDB(BaseModel):
    """
    Internal model representing a User record stored in MongoDB.
    Includes hashed_password for authentication checks.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str = Field(alias="_id")
    email: str
    hashed_password: str
    full_name: str
    role: UserRole = UserRole.ENGINEER
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
