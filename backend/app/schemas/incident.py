from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.app.models.incident import IncidentSeverity, IncidentStatus, InvestigationNote


class InvestigationNoteCreate(BaseModel):
    """Payload to add an investigation note to an incident."""
    note: str = Field(min_length=1, max_length=5000, description="Investigation note content")


class InvestigationNoteResponse(BaseModel):
    """Representation of an investigation note."""
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    note_id: str
    user_id: str
    user_email: str
    note: str
    created_at: datetime


class IncidentAssignRequest(BaseModel):
    """Payload to assign an incident to an engineer."""
    assigned_to: str = Field(min_length=1, max_length=255, description="Engineer user_id or email")


class IncidentSeverityUpdateRequest(BaseModel):
    """Payload to update an incident's priority/severity."""
    severity: IncidentSeverity = Field(description="New severity level")


class IncidentResolutionRequest(BaseModel):
    """Payload to record resolution details and optionally mark as resolved."""
    confirmed_root_cause: str = Field(min_length=1, max_length=2000, description="Diagnosed root cause")
    confirmed_resolution: str = Field(min_length=1, max_length=5000, description="Detailed resolution description")
    resolution_actions: Optional[List[str]] = Field(default_factory=list, description="Action items taken to resolve")
    is_verified: bool = Field(default=True, description="Whether resolution is verified by an engineer")
    rca_analysis_id: Optional[str] = Field(default=None, description="Reference to RCA analysis ID if applicable")
    notes: Optional[str] = Field(default=None, description="Optional extra resolution notes")


class IncidentVerifyResolutionRequest(BaseModel):
    """Payload to verify an existing resolution."""
    is_verified: bool = Field(default=True, description="Whether confirmed resolution is verified")
    verification_notes: Optional[str] = Field(default=None, description="Verification remarks")


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
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[str] = None
    investigation_notes: List[InvestigationNoteResponse] = Field(default_factory=list)
    confirmed_root_cause: Optional[str] = None
    confirmed_resolution: Optional[str] = None
    resolution_actions: List[str] = Field(default_factory=list)
    has_verified_resolution: bool = False
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    rca_analysis_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    knowledge_synced: bool = False
    knowledge_synced_at: Optional[datetime] = None

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
