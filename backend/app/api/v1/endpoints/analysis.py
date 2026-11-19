from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.dependencies import get_current_user, get_db, require_role
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.analysis import (
    AnalysisResponse,
    PaginatedAnalysisResponse,
    RCARequest,
)
from backend.app.services.rca_service import RCAService

router = APIRouter(tags=["AI Root Cause Analysis"])


@router.post(
    "/incidents/{incident_id}/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger AI Root Cause Analysis for an incident",
)
@router.post(
    "/analysis/{incident_id}",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def analyze_incident(
    incident_id: str,
    payload: Optional[RCARequest] = None,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> AnalysisResponse:
    """
    Triggers an AI-powered root-cause investigation for the specified incident.
    Restricted to ADMIN and ENGINEER roles.
    Pulls associated logs, sanitizes credentials, generates grounded analysis via LLM,
    and records the result in the analyses collection.
    """
    return await RCAService.analyze_incident(
        db=db,
        user=current_user,
        incident_id=incident_id,
        request_data=payload,
    )


@router.get(
    "/incidents/{incident_id}/analyses",
    response_model=PaginatedAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get root-cause analysis history for an incident",
)
async def get_incident_analyses(
    incident_id: str,
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Records to skip"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> PaginatedAnalysisResponse:
    """
    Retrieves all historical analyses run for a given incident, ordered newest first.
    Accessible to all authenticated users with tenant access to the incident.
    """
    return await RCAService.get_incident_analyses(
        db=db,
        user=current_user,
        incident_id=incident_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a specific analysis by its analysis ID",
)
@router.get(
    "/analysis/{analysis_id}",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def get_analysis(
    analysis_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> AnalysisResponse:
    """
    Retrieves an individual root-cause analysis record.
    Enforces tenant isolation: users can only view analyses for incidents they own.
    """
    return await RCAService.get_analysis_by_id(
        db=db,
        user=current_user,
        analysis_id=analysis_id,
    )
