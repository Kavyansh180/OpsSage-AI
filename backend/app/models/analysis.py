from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConfidenceLevel(str, Enum):
    """
    Confidence assessment level for the generated root-cause analysis.
    """
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @classmethod
    def from_string(cls, val: Optional[str]) -> "ConfidenceLevel":
        if not val:
            return cls.LOW
        clean = val.strip().upper()
        if "HIGH" in clean:
            return cls.HIGH
        elif "MED" in clean:
            return cls.MEDIUM
        return cls.LOW


class AnalysisInDB(BaseModel):
    """
    Internal model representing a root-cause analysis document stored in MongoDB.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: Optional[str] = Field(default=None, alias="_id")
    analysis_id: str = Field(description="Unique human-readable identifier (e.g. RCA-20261118-A1B2C3)")
    incident_id: str = Field(description="Target incident identifier")
    user_id: str = Field(description="Owner tenant / user ID")
    probable_root_cause: str = Field(description="Core technical hypothesis of the root cause")
    explanation: str = Field(description="Detailed narrative explaining the mechanism of failure")
    supporting_evidence: List[str] = Field(default_factory=list, description="Grounding evidence citing specific logs or fields")
    contributing_factors: List[str] = Field(default_factory=list, description="Secondary or environmental factors")
    confidence_level: ConfidenceLevel = Field(default=ConfidenceLevel.LOW, description="Model confidence level")
    recommended_actions: List[str] = Field(default_factory=list, description="Ordered actionable remediation steps")
    limitations: List[str] = Field(default_factory=list, description="Known caveats or missing evidence")
    provider: str = Field(description="LLM provider name (e.g. gemini, openai)")
    model: str = Field(description="Model identifier (e.g. gemini-3.5-flash-lite)")
    evidence_log_count: int = Field(default=0, description="Number of logs supplied as evidence")
    redacted_secrets_count: int = Field(default=0, description="Count of detected secrets redacted prior to LLM call")
    raw_llm_response: Optional[str] = Field(default=None, description="Raw JSON string response from LLM provider")
    rag_status: str = Field(default="DISABLED", description="Status of historical RAG retrieval: SUCCESS, EMPTY, UNAVAILABLE, DISABLED")
    similar_incidents: List[Dict[str, Any]] = Field(default_factory=list, description="References to similar historical incidents retrieved via RAG")
    created_at: datetime = Field(description="Timestamp when analysis was generated and saved")
