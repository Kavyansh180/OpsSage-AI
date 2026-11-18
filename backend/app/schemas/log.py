from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.app.models.log import LogLevel


class LogIngestRequest(BaseModel):
    """
    Schema for ingesting a single log record.
    Supports structured fields, unstructured raw_log, or a combination.
    """
    service_name: Optional[str] = Field(None, max_length=100, description="Service or application name")
    environment: str = Field("production", max_length=50, description="Runtime environment (dev/staging/production)")
    level: Optional[str] = Field(None, max_length=20, description="Severity (DEBUG, INFO, WARN, ERROR, CRITICAL)")
    message: Optional[str] = Field(None, description="Log message text")
    timestamp: Optional[datetime] = Field(None, description="Log event timestamp in UTC")
    source: Optional[str] = Field(None, max_length=150, description="Log source (file, container, logger name)")
    host: Optional[str] = Field(None, max_length=100, description="Host or node identifier")
    request_id: Optional[str] = Field(None, max_length=100, description="HTTP request or correlation ID")
    trace_id: Optional[str] = Field(None, max_length=100, description="Distributed trace ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured metadata")
    raw_log: Optional[str] = Field(None, description="Original unparsed log string line")

    @model_validator(mode="after")
    def validate_message_or_raw_log(self) -> "LogIngestRequest":
        """
        Ensures that at least one of message or raw_log is provided and non-empty.
        """
        has_message = bool(self.message and self.message.strip())
        has_raw_log = bool(self.raw_log and self.raw_log.strip())
        if not has_message and not has_raw_log:
            raise ValueError("Either 'message' or 'raw_log' must be provided and cannot be an empty message.")
        return self


class BatchLogIngestRequest(BaseModel):
    """
    Schema for batch log ingestion.
    Accepts a list of log records up to maximum batch limit.
    Per-record validation is deferred to the ingestion service to ensure partial failure isolation.
    """
    logs: List[Any] = Field(
        ...,
        min_length=1,
        description="List of log records to ingest (up to maximum batch limit)."
    )


class BatchItemError(BaseModel):
    """
    Reports parsing or persistence error for an individual log item in a batch.
    """
    index: int
    reason: str
    raw_snippet: Optional[str] = None


class BatchLogIngestResponse(BaseModel):
    """
    Summary response for batch log ingestion.
    """
    total_received: int
    successful_count: int
    failed_count: int
    inserted_ids: List[str]
    errors: List[BatchItemError] = Field(default_factory=list)


class LogResponse(BaseModel):
    """
    Public representation of a stored structured log entry.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str

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
    user_id: str
    service_name: str
    environment: str
    level: LogLevel
    message: str
    normalized_message: str
    timestamp: datetime
    ingested_at: datetime
    source: Optional[str] = None
    host: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_log: Optional[str] = None


class PaginatedLogResponse(BaseModel):
    """
    Paginated log query results.
    """
    items: List[LogResponse]
    total: int
    limit: int
    offset: int
