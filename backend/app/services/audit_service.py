from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.core.logging import get_logger
from backend.app.models.audit import AuditAction, AuditLogEntryInDB
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.audit import AuditLogResponse, PaginatedAuditLogResponse

logger = get_logger("services.audit")


class AuditService:
    """
    Centralized service for recording and retrieving incident activity history and audit trails.
    Guarantees strict tenant isolation.
    """

    @classmethod
    def generate_audit_id(cls) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rand = uuid4().hex[:6].upper()
        return f"AUD-{ts}-{rand}"

    @classmethod
    async def record_event(
        cls,
        db: AsyncDatabase,
        incident_id: str,
        user_id: str,
        actor: UserInDB,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntryInDB:
        """
        Appends an immutable audit log entry for an incident event.
        """
        audit_col = db["audit_logs"]
        now = datetime.now(timezone.utc)
        audit_id = cls.generate_audit_id()

        entry = AuditLogEntryInDB(
            audit_id=audit_id,
            incident_id=incident_id,
            user_id=user_id,
            actor_id=actor.id,
            actor_email=actor.email,
            action=action,
            details=details or {},
            timestamp=now,
        )

        doc = entry.model_dump(by_alias=True, exclude_none=True)
        await audit_col.insert_one(doc)
        logger.info(f"Audit event '{action}' recorded for incident '{incident_id}' by '{actor.email}'.")
        return entry

    @classmethod
    async def get_incident_history(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedAuditLogResponse:
        """
        Retrieves the chronological audit history for a specific incident.
        Enforces tenant isolation: non-admins can only see their own incidents' audit logs.
        """
        # First verify incident exists and user is authorized
        inc_col = db["incidents"]
        inc_doc = await inc_col.find_one({"incident_id": incident_id})
        if not inc_doc:
            raise ResourceNotFoundError(f"Incident '{incident_id}' not found.")

        if user.role != UserRole.ADMIN and inc_doc.get("user_id") != user.id:
            raise ResourceNotFoundError(f"Incident '{incident_id}' not found.")

        audit_col = db["audit_logs"]
        query = {"incident_id": incident_id}
        if user.role != UserRole.ADMIN:
            query["user_id"] = user.id

        total = await audit_col.count_documents(query)
        cursor = audit_col.find(query).sort("timestamp", -1).skip(offset).limit(limit)
        docs = await cursor.to_list(length=limit)

        items: List[AuditLogResponse] = []
        for d in docs:
            d["id"] = str(d["_id"])
            items.append(AuditLogResponse.model_validate(d))

        return PaginatedAuditLogResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )
