"""Pydantic I/O schemas for request validation and response serialization."""
from backend.app.schemas.analysis import (
    AnalysisResponse,
    PaginatedAnalysisResponse,
    RCARequest,
    StructuredRCAResponse,
)
from backend.app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from backend.app.schemas.audit import (
    AuditLogResponse,
    PaginatedAuditLogResponse,
)
from backend.app.schemas.incident import (
    IncidentAssignRequest,
    IncidentResolutionRequest,
    IncidentResponse,
    IncidentSeverityUpdateRequest,
    IncidentVerifyResolutionRequest,
    InvestigationNoteCreate,
    InvestigationNoteResponse,
    PaginatedIncidentResponse,
)
from backend.app.schemas.knowledge import (
    KnowledgeDocumentResponse,
    KnowledgeIndexRequest,
    KnowledgeIndexResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    SimilarIncidentReference,
)
from backend.app.schemas.log import (
    BatchItemError,
    BatchLogIngestRequest,
    BatchLogIngestResponse,
    LogIngestRequest,
    LogResponse,
    PaginatedLogResponse,
)

__all__ = [
    "AnalysisResponse",
    "AuditLogResponse",
    "BatchItemError",
    "BatchLogIngestRequest",
    "BatchLogIngestResponse",
    "IncidentAssignRequest",
    "IncidentResolutionRequest",
    "IncidentResponse",
    "IncidentSeverityUpdateRequest",
    "IncidentVerifyResolutionRequest",
    "InvestigationNoteCreate",
    "InvestigationNoteResponse",
    "KnowledgeDocumentResponse",
    "KnowledgeIndexRequest",
    "KnowledgeIndexResponse",
    "KnowledgeSearchRequest",
    "KnowledgeSearchResponse",
    "LogIngestRequest",
    "LogResponse",
    "PaginatedAnalysisResponse",
    "PaginatedAuditLogResponse",
    "PaginatedIncidentResponse",
    "PaginatedLogResponse",
    "RCARequest",
    "SimilarIncidentReference",
    "StructuredRCAResponse",
    "TokenResponse",
    "UserLoginRequest",
    "UserRegisterRequest",
    "UserResponse",
]
