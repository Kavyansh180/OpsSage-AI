from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from pymongo.asynchronous.database import AsyncDatabase
from backend.app.core.dependencies import get_current_user, get_db, require_role
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.log import (
    BatchLogIngestRequest,
    BatchLogIngestResponse,
    LogIngestRequest,
    LogResponse,
    PaginatedLogResponse,
)
from backend.app.services.log_ingestion_service import LogIngestionService

router = APIRouter(tags=["Logs & Ingestion"])


@router.post(
    "/ingest",
    response_model=LogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a single log entry"
)
async def ingest_log(
    log_in: LogIngestRequest,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> LogResponse:
    """
    Ingests, parses, normalizes, and stores a single application log.
    Restricted to 'admin' and 'engineer' roles.
    """
    return await LogIngestionService.ingest_single_log(
        db=db,
        user=current_user,
        log_in=log_in
    )


@router.post(
    "/ingest/batch",
    response_model=BatchLogIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a batch of log entries"
)
async def ingest_batch_logs(
    batch_in: BatchLogIngestRequest,
    current_user: UserInDB = Depends(require_role(UserRole.ADMIN, UserRole.ENGINEER)),
    db: AsyncDatabase = Depends(get_db),
) -> BatchLogIngestResponse:
    """
    Ingests up to 500 log entries in a single batch.
    Per-item error isolation: malformed records report errors without aborting valid entries.
    """
    return await LogIngestionService.ingest_batch_logs(
        db=db,
        user=current_user,
        batch_in=batch_in
    )


@router.get(
    "",
    response_model=PaginatedLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve logs with filtering and pagination"
)
async def list_logs(
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    environment: Optional[str] = Query(None, description="Filter by environment"),
    level: Optional[str] = Query(None, description="Filter by severity level (DEBUG, INFO, WARN, ERROR, CRITICAL)"),
    start_time: Optional[datetime] = Query(None, description="Filter logs on or after this UTC timestamp"),
    end_time: Optional[datetime] = Query(None, description="Filter logs on or before this UTC timestamp"),
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Records to skip for pagination"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> PaginatedLogResponse:
    """
    Retrieves stored logs with filtering by service, severity, time range, and pagination.
    Admins can view all logs; non-admins only access their own ingested logs.
    """
    return await LogIngestionService.get_logs(
        db=db,
        user=current_user,
        service_name=service_name,
        environment=environment,
        level=level,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset
    )


@router.get(
    "/{log_id}",
    response_model=LogResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a specific log entry by ID"
)
async def get_log_by_id(
    log_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> LogResponse:
    """
    Retrieves a single log entry by its MongoDB ID.
    Enforces tenant access control: returns 404 if log does not belong to user (unless admin).
    """
    return await LogIngestionService.get_log_by_id(
        db=db,
        user=current_user,
        log_id=log_id
    )
