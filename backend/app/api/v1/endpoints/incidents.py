from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.dependencies import get_current_user, get_db, require_role
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.incident import IncidentResponse, PaginatedIncidentResponse
from backend.app.services.incident_detection_service import IncidentDetectionService

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
    return await IncidentDetectionService.acknowledge_incident(
        db=db,
        user=current_user,
        incident_id=incident_id
    )


@router.patch(
    "/{incident_id}/resolve",
    response_model=IncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve an incident"
)
async def resolve_incident(
    incident_id: str,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> IncidentResponse:
    """
    Transitions incident from OPEN/ACKNOWLEDGED -> RESOLVED.
    Permanently freezes the historical record; future occurrences trigger a fresh incident.
    Restricted to Admin and Engineer roles. Viewers are forbidden (403).
    """
    return await IncidentDetectionService.resolve_incident(
        db=db,
        user=current_user,
        incident_id=incident_id
    )
