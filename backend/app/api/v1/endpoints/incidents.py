from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.dependencies import get_current_user, get_db, require_role
from backend.app.models.incident import IncidentStatus
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.audit import PaginatedAuditLogResponse
from backend.app.schemas.incident import (
    IncidentAssignRequest,
    IncidentResolutionRequest,
    IncidentResponse,
    IncidentSeverityUpdateRequest,
    IncidentVerifyResolutionRequest,
    InvestigationNoteCreate,
    PaginatedIncidentResponse,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.incident_detection_service import IncidentDetectionService
from backend.app.services.incident_management_service import IncidentManagementService

router = APIRouter(tags=["Incident Detection & Management"])


@router.get(
    "",
    response_model=PaginatedIncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="List incidents with filtering and pagination"
)
async def list_incidents(
    environment: Optional[str] = Query(None, description="Filter by environment (e.g. production, staging)"),
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    status: Optional[str] = Query(None, description="Filter by status (OPEN, ACKNOWLEDGED, RESOLVED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"),
    start_time: Optional[datetime] = Query(None, description="Filter incidents last seen on or after UTC datetime"),
    end_time: Optional[datetime] = Query(None, description="Filter incidents last seen on or before UTC datetime"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Records to skip"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> PaginatedIncidentResponse:
    """
    Retrieves operational incidents.
    Admins can view incidents across all users; engineers and viewers view their own incidents.
    """
    return await IncidentDetectionService.get_incidents(
        db=db,
        user=current_user,
        environment=environment,
        service_name=service_name,
        status_filter=status,
        severity=severity,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a specific incident by ID"
)
async def get_incident(
    incident_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> IncidentResponse:
    """
    Retrieves a single incident by incident_id (e.g. INC-20261102-A1B2C3) or MongoDB ObjectId.
    Enforces tenant isolation: returns 404 if not found or belongs to another user.
    """
    return await IncidentDetectionService.get_incident_by_id(
        db=db,
        user=current_user,
        incident_id=incident_id
    )


@router.patch(
    "/{incident_id}/acknowledge",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Acknowledge an open incident"
)
async def acknowledge_incident(
    incident_id: str,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> IncidentResponse:
    """
    Transitions incident from OPEN -> ACKNOWLEDGED.
    Restricted to Admin and Engineer roles. Viewers are forbidden (403).
    """
    return await IncidentManagementService.acknowledge_incident(
        db=db,
        user=current_user,
        incident_id=incident_id
    )


@router.patch(
    "/{incident_id}/assign",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign an incident to an engineer"
)
async def assign_incident(
    incident_id: str,
    payload: IncidentAssignRequest,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> IncidentResponse:
    """
    Assigns ownership of an incident to a designated engineer.
    Restricted to Admin and Engineer roles. Viewers are forbidden (403).
    """
    return await IncidentManagementService.assign_incident(
        db=db,
        user=current_user,
        incident_id=incident_id,
        payload=payload,
    )


@router.patch(
    "/{incident_id}/severity",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update incident severity"
)
async def update_incident_severity(
    incident_id: str,
    payload: IncidentSeverityUpdateRequest,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> IncidentResponse:
    """
    Updates the priority/severity rating of an incident.
    Restricted to Admin and Engineer roles. Viewers are forbidden (403).
    """
    return await IncidentManagementService.update_severity(
        db=db,
        user=current_user,
        incident_id=incident_id,
        payload=payload,
    )


@router.post(
    "/{incident_id}/notes",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an investigation note"
)
async def add_investigation_note(
    incident_id: str,
    payload: InvestigationNoteCreate,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> IncidentResponse:
    """
    Logs an investigation note against the incident.
    Restricted to Admin and Engineer roles. Viewers are forbidden (403).
    """
    return await IncidentManagementService.add_investigation_note(
        db=db,
        user=current_user,
        incident_id=incident_id,
        payload=payload,
    )


@router.post(
    "/{incident_id}/resolution",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Record structured incident resolution"
)
@router.post(
    "/{incident_id}/resolve",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve incident with structured root cause"
)
async def record_incident_resolution(
    incident_id: str,
    payload: IncidentResolutionRequest,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> IncidentResponse:
    """
    Records confirmed root-cause findings, resolution actions, and transitions incident to RESOLVED.
    Synchronizes resolution into the historical Knowledge Base.
    Restricted to Admin and Engineer roles. Viewers are forbidden (403).
    """
    return await IncidentManagementService.record_resolution(
        db=db,
        user=current_user,
        incident_id=incident_id,
        payload=payload,
    )


@router.patch(
    "/{incident_id}/resolve",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve an incident (simple transition)"
)
async def resolve_incident_simple(
    incident_id: str,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> IncidentResponse:
    """
    Transitions incident from OPEN/ACKNOWLEDGED -> RESOLVED.
    Restricted to Admin and Engineer roles. Viewers are forbidden (403).
    """
    resp = await IncidentDetectionService.resolve_incident(
        db=db,
        user=current_user,
        incident_id=incident_id
    )
    await AuditService.record_event(
        db=db,
        incident_id=resp.incident_id,
        user_id=resp.user_id,
        actor=current_user,
        action="RESOLVED",
        details={"status": IncidentStatus.RESOLVED.value},
    )
    return resp


@router.post(
    "/{incident_id}/verify-resolution",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify an incident resolution"
)
async def verify_incident_resolution(
    incident_id: str,
    payload: IncidentVerifyResolutionRequest,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> IncidentResponse:
    """
    Explicitly marks an incident's resolution as verified by an authorized human engineer.
    Triggers Knowledge Base re-indexing with verified status and embedding updates.
    Restricted to Admin and Engineer roles. Viewers are forbidden (403).
    """
    return await IncidentManagementService.verify_resolution(
        db=db,
        user=current_user,
        incident_id=incident_id,
        payload=payload,
    )


@router.get(
    "/{incident_id}/history",
    response_model=PaginatedAuditLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve incident audit trail and activity history"
)
@router.get(
    "/{incident_id}/audit",
    response_model=PaginatedAuditLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve incident audit log"
)
async def get_incident_history(
    incident_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> PaginatedAuditLogResponse:
    """
    Retrieves chronological activity history for an incident.
    Enforces tenant isolation: non-admins only see history for incidents they own.
    """
    return await AuditService.get_incident_history(
        db=db,
        user=current_user,
        incident_id=incident_id,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{incident_id}/sync-knowledge",
    status_code=status.HTTP_200_OK,
    summary="Synchronize incident to Knowledge Base"
)
async def sync_incident_to_knowledge(
    incident_id: str,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> dict:
    """
    Manually triggers re-indexing of an incident into the historical Knowledge Base.
    Restricted to Admin and Engineer roles. Viewers are forbidden (403).
    """
    success = await IncidentManagementService.sync_knowledge_base(
        db=db,
        user=current_user,
        incident_id=incident_id,
    )
    return {"incident_id": incident_id, "synced": success}
