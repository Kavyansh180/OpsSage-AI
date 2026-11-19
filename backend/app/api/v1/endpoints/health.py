from datetime import datetime, timezone
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from backend.app.config import get_settings
from backend.app.db.mongodb import MongoDBManager

router = APIRouter(tags=["Health & Diagnostics"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    timestamp: str


class ReadyResponse(BaseModel):
    status: str
    database: str
    timestamp: str


@router.get("/health", response_model=HealthResponse, summary="Liveness Probe")
async def health_check() -> HealthResponse:
    """
    Liveness probe.
    Returns 200 OK immediately if the FastAPI process is alive and receiving traffic.
    """
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={
        200: {"description": "Service is ready to handle traffic"},
        503: {"description": "Service is not ready (dependency failure)"}
    },
    summary="Readiness Probe"
)
async def readiness_check(response: Response) -> ReadyResponse:
    """
    Readiness probe.
    Verifies downstream dependencies (e.g. MongoDB Atlas).
    Returns 200 when ready, or 503 if MongoDB is unreachable.
    """
    try:
        await MongoDBManager.ensure_database()
        is_db_connected = await MongoDBManager.ping()
    except Exception:
        is_db_connected = False

    if is_db_connected:
        response.status_code = status.HTTP_200_OK
        db_status = "connected"
        overall_status = "ready"
    else:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        db_status = "disconnected"
        overall_status = "unready"

    return ReadyResponse(
        status=overall_status,
        database=db_status,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
