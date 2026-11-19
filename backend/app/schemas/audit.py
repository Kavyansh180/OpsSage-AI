from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuditLogResponse(BaseModel):
    """
    Public response representation of an incident audit trail entry.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str
    audit_id: str
    incident_id: str
    user_id: str
    actor_id: str
    actor_email: str
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime

    @model_validator(mode="before")
    @classmethod
    def map_id_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "id" not in data and "_id" in data:
                data["id"] = str(data["_id"])
            elif "id" in data:
                data["id"] = str(data["id"])
        elif hasattr(data, "_id") and not hasattr(data, "id"):
            setattr(data, "id", str(getattr(data, "_id")))
        return data


class PaginatedAuditLogResponse(BaseModel):
    """
    Paginated audit logs response.
    """
    items: List[AuditLogResponse]
    total: int
    limit: int
    offset: int
