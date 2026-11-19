from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class IncidentStatus(str, Enum):
    """
    Lifecycle states for an operational incident.
    """
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class IncidentSeverity(str, Enum):
    """
    Deterministic severity levels assigned based on failure evidence.
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def rank(cls, severity: "IncidentSeverity") -> int:
        """
        Numeric ranking for monotonic escalation comparisons.
        """
        ranks = {
            cls.LOW: 1,
            cls.MEDIUM: 2,
            cls.HIGH: 3,
            cls.CRITICAL: 4,
        }
        return ranks.get(severity, 1)

    def __ge__(self, other: "IncidentSeverity") -> bool:
        if not isinstance(other, IncidentSeverity):
            return NotImplemented
        return self.rank(self) >= self.rank(other)

    def __gt__(self, other: "IncidentSeverity") -> bool:
        if not isinstance(other, IncidentSeverity):
            return NotImplemented
        return self.rank(self) > self.rank(other)


class InvestigationNote(BaseModel):
    """
    Engineer note attached to an incident during investigation.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    note_id: str
    user_id: str
    user_email: str
    note: str
    created_at: datetime


class IncidentInDB(BaseModel):
    """
    Internal model representing an incident document stored in MongoDB.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: Optional[str] = Field(default=None, alias="_id")
    incident_id: str = Field(description="Unique human-readable identifier (e.g. INC-20261102-A1B2C3)")
    user_id: str = Field(description="Owner tenant / user ID")
    environment: str = Field(description="Runtime environment (e.g. production, staging, development)")
    service_name: str = Field(description="Application or service name")
    error_signature: str = Field(description="SHA-256 hash derived from (service_name, environment, normalized_message)")
    title: str = Field(description="Representative error message summary")
    severity: IncidentSeverity = Field(default=IncidentSeverity.LOW)
    status: IncidentStatus = Field(default=IncidentStatus.OPEN)
    first_seen: datetime = Field(description="UTC timestamp of the earliest log event in this failure group")
    last_seen: datetime = Field(description="UTC timestamp of the most recent log event in this failure group")
    window_event_count: int = Field(default=1, description="Count of matching events within current sliding window")
    event_count: int = Field(default=1, description="Cumulative total of all distinct events linked to this incident")
    related_log_ids: List[str] = Field(default_factory=list, description="Bounded list of up to 100 recent log ObjectIds")
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[str] = None
    investigation_notes: List[InvestigationNote] = Field(default_factory=list)
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
