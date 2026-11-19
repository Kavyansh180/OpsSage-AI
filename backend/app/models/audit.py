from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditAction:
    CREATED = "CREATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ASSIGNED = "ASSIGNED"
    SEVERITY_UPDATED = "SEVERITY_UPDATED"
    NOTE_ADDED = "NOTE_ADDED"
    RESOLUTION_RECORDED = "RESOLUTION_RECORDED"
    RESOLUTION_VERIFIED = "RESOLUTION_VERIFIED"
    KNOWLEDGE_SYNCED = "KNOWLEDGE_SYNCED"
    KNOWLEDGE_SYNC_FAILED = "KNOWLEDGE_SYNC_FAILED"


class AuditLogEntryInDB(BaseModel):
    """
    Persistent audit log record capturing an action on an incident.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: Optional[str] = Field(default=None, alias="_id")
    audit_id: str = Field(description="Unique audit event identifier (e.g. AUD-...)")
    incident_id: str = Field(description="Incident identifier")
    user_id: str = Field(description="Tenant user identifier")
    actor_id: str = Field(description="User ID of the actor performing the action")
    actor_email: str = Field(description="Email address of the actor")
    action: str = Field(description="Action performed (e.g. ASSIGNED, RESOLUTION_RECORDED)")
    details: Dict[str, Any] = Field(default_factory=dict, description="Action-specific metadata")
    timestamp: datetime = Field(description="UTC timestamp of the action")
