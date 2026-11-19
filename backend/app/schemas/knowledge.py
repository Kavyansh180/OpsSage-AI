from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.app.models.knowledge import HistoricalAnalysisSummary


class SimilarIncidentReference(BaseModel):
    """
    Structured summary of a similar historical incident retrieved via RAG.
    Included in RCA responses and search results.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    knowledge_id: str
    source_incident_id: str
    similarity_score: float = Field(
        description="Cosine similarity score (0.0 to 1.0) against the query"
    )
    service_name: str
    environment: str
    title: str
    has_verified_resolution: bool = Field(
        default=False,
        description="True if an engineer manually confirmed and verified the resolution"
    )
    confirmed_resolution: Optional[str] = Field(
        default=None,
        description="Engineer-confirmed resolution, if present"
    )
    probable_root_cause: Optional[str] = Field(
        default=None,
        description="Historical AI hypothesis (untrusted supporting context)"
    )


class KnowledgeDocumentResponse(BaseModel):
    """
    Public representation of a stored knowledge base record.
    The raw 384-dimensional embedding vector is strictly omitted for security and efficiency.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str
    knowledge_id: str
    source_incident_id: str
    user_id: str
    service_name: str
    environment: str
    error_signature: str
    title: str
    description: Optional[str] = None
    diagnostic_summary: str
    historical_analysis: Optional[HistoricalAnalysisSummary] = None
    confirmed_resolution: Optional[str] = None
    has_verified_resolution: bool
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

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


class KnowledgeSearchRequest(BaseModel):
    """
    Query parameters for semantic incident search.
    Supports searching by freeform text, or by an existing incident ID.
    """
    query: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Freeform search query or error description"
    )
    incident_id: Optional[str] = Field(
        default=None,
        description="Target incident ID to find historical precedents for"
    )
    service_name: Optional[str] = Field(
        default=None,
        description="Optional filter by service name"
    )
    environment: Optional[str] = Field(
        default=None,
        description="Optional filter by environment"
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Maximum similar precedents to return"
    )
    min_similarity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity cutoff"
    )

    @model_validator(mode="after")
    def validate_query_or_incident_id(self) -> "KnowledgeSearchRequest":
        if not self.query and not self.incident_id:
            raise ValueError("Either 'query' or 'incident_id' must be provided.")
        return self


class KnowledgeSearchResponse(BaseModel):
    """
    Response returned by semantic similarity search.
    """
    query_text: str
    total_found: int
    results: List[SimilarIncidentReference]


class KnowledgeIndexRequest(BaseModel):
    """
    Batch indexing request parameters.
    """
    limit: int = Field(default=50, ge=1, le=500, description="Max historical incidents to index")
    service_name: Optional[str] = Field(default=None, description="Optional service filter")
    environment: Optional[str] = Field(default=None, description="Optional environment filter")
    force_reindex: bool = Field(default=False, description="Re-generate embeddings even if already indexed")


class KnowledgeIndexResponse(BaseModel):
    """
    Summary returned by knowledge base indexing operations.
    """
    total_eligible: int
    indexed_count: int
    skipped_count: int
    failed_count: int
    indexed_knowledge_ids: List[str]
    errors: List[Dict[str, Any]] = Field(default_factory=list)
