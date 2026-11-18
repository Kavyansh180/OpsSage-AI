from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, model_validator
from backend.app.models.incident import IncidentSeverity, IncidentStatus


class IncidentResponse(BaseModel):
    """
    Public representation of an operational incident.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str
    incident_id: str
    user_id: str
    environment: str
    service_name: str
    error_signature: str
    title: str
    severity: IncidentSeverity
    status: IncidentStatus
    first_seen: datetime
    last_seen: datetime
    window_event_count: int
    event_count: int
    related_log_ids: List[str]
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

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


class PaginatedIncidentResponse(BaseModel):
    """
    Paginated incident query results.
    """
    items: List[IncidentResponse]
    total: int
    limit: int
    offset: int
