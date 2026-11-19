from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.models.user import UserInDB, UserRole

router = APIRouter(prefix="/analytics", tags=["Analytics & KPIs"])


class AnalyticsOverviewResponse(BaseModel):
    total_incidents: int
    open_incidents: int
    acknowledged_incidents: int
    resolved_incidents: int
    critical_incidents: int
    high_incidents: int
    medium_incidents: int
    low_incidents: int
    resolution_rate_pct: float
    mtta_minutes: Optional[float] = None
    mttr_minutes: Optional[float] = None
    by_severity: Dict[str, int]
    by_service: Dict[str, int]
    by_status: Dict[str, int]
    by_environment: Dict[str, int]
    daily_trends: List[Dict[str, Any]]
    recurring_patterns: List[Dict[str, Any]]


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve tenant-isolated incident analytics, KPIs, and metrics"
)
async def get_analytics_overview(
    days: int = Query(30, ge=1, le=365, description="Historical lookback window in days"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncDatabase = Depends(get_db),
) -> AnalyticsOverviewResponse:
    """
    Computes real incident telemetry KPIs, mean-time-to-acknowledge (MTTA),
    mean-time-to-resolve (MTTR), resolution rates, and trends.
    Guarantees tenant isolation: non-admins only see metrics for their own tenant.
    """
    inc_col = db["incidents"]
    query: Dict[str, Any] = {}
    if current_user.role != UserRole.ADMIN:
        query["user_id"] = current_user.id

    cursor = inc_col.find(query)
    incidents = await cursor.to_list(length=10000)

    total = len(incidents)
    by_status: Dict[str, int] = {"OPEN": 0, "ACKNOWLEDGED": 0, "RESOLVED": 0}
    by_severity: Dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    by_service: Dict[str, int] = {}
    by_env: Dict[str, int] = {}
    recurring_signatures: Dict[str, Dict[str, Any]] = {}

    mtta_seconds_list: List[float] = []
    mttr_seconds_list: List[float] = []

    # Map daily trends for the requested lookback window
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    daily_map: Dict[str, int] = {}
    for d in range(days + 1):
        dt_key = (cutoff + timedelta(days=d)).strftime("%Y-%m-%d")
        daily_map[dt_key] = 0

    for inc in incidents:
        # Status
        st = inc.get("status", "OPEN")
        by_status[st] = by_status.get(st, 0) + 1

        # Severity
        sev = inc.get("severity", "LOW")
        by_severity[sev] = by_severity.get(sev, 0) + 1

        # Service
        svc = inc.get("service_name", "unknown")
        by_service[svc] = by_service.get(svc, 0) + 1

        # Environment
        env = inc.get("environment", "production")
        by_env[env] = by_env.get(env, 0) + 1

        # Signatures
        sig = inc.get("error_signature", "unknown")
        if sig not in recurring_signatures:
            recurring_signatures[sig] = {
                "error_signature": sig,
                "title": inc.get("title", ""),
                "service_name": svc,
                "count": 0,
                "severity": sev,
            }
        recurring_signatures[sig]["count"] += inc.get("event_count", 1)

        # Dates & MTTA / MTTR calculation
        first_seen = inc.get("first_seen") or inc.get("created_at")
        ack_at = inc.get("acknowledged_at")
        res_at = inc.get("resolved_at")

        if first_seen and ack_at and ack_at >= first_seen:
            mtta_seconds_list.append((ack_at - first_seen).total_seconds())

        if first_seen and res_at and res_at >= first_seen:
            mttr_seconds_list.append((res_at - first_seen).total_seconds())

        # Daily trend
        c_at = inc.get("created_at") or first_seen
        if c_at and isinstance(c_at, datetime):
            c_key = c_at.strftime("%Y-%m-%d")
            if c_key in daily_map:
                daily_map[c_key] += 1

    resolved_count = by_status.get("RESOLVED", 0)
    resolution_rate = round((resolved_count / total * 100.0), 2) if total > 0 else 0.0

    avg_mtta_min = round((sum(mtta_seconds_list) / len(mtta_seconds_list)) / 60.0, 2) if mtta_seconds_list else None
    avg_mttr_min = round((sum(mttr_seconds_list) / len(mttr_seconds_list)) / 60.0, 2) if mttr_seconds_list else None

    daily_trends = [{"date": k, "count": v} for k, v in sorted(daily_map.items())]
    sorted_patterns = sorted(recurring_signatures.values(), key=lambda x: x["count"], reverse=True)[:10]

    return AnalyticsOverviewResponse(
        total_incidents=total,
        open_incidents=by_status.get("OPEN", 0),
        acknowledged_incidents=by_status.get("ACKNOWLEDGED", 0),
        resolved_incidents=resolved_count,
        critical_incidents=by_severity.get("CRITICAL", 0),
        high_incidents=by_severity.get("HIGH", 0),
        medium_incidents=by_severity.get("MEDIUM", 0),
        low_incidents=by_severity.get("LOW", 0),
        resolution_rate_pct=resolution_rate,
        mtta_minutes=avg_mtta_min,
        mttr_minutes=avg_mttr_min,
        by_severity=by_severity,
        by_service=by_service,
        by_status=by_status,
        by_environment=by_env,
        daily_trends=daily_trends,
        recurring_patterns=sorted_patterns,
    )
