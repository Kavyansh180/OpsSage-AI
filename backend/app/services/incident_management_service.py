from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from bson import ObjectId
from fastapi import status
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.exceptions import AppException, ResourceNotFoundError
from backend.app.core.logging import get_logger
from backend.app.models.audit import AuditAction
from backend.app.models.incident import IncidentSeverity, IncidentStatus, InvestigationNote
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.incident import (
    IncidentAssignRequest,
    IncidentResolutionRequest,
    IncidentResponse,
    IncidentSeverityUpdateRequest,
    IncidentVerifyResolutionRequest,
    InvestigationNoteCreate,
    InvestigationNoteResponse,
)
from backend.app.services.audit_service import AuditService
from backend.app.services.incident_detection_service import IncidentDetectionService
from backend.app.services.knowledge_indexer import KnowledgeIndexer

logger = get_logger("services.incident_management")


class IncidentManagementService:
    """
    Orchestrates the engineer-facing incident workflow:
    - Assignment and ownership management.
    - Lifecycle state transitions (OPEN, ACKNOWLEDGED, RESOLVED).
    - Severity and priority adjustments.
    - Investigation notes logging.
    - Structured resolution recording with confirmed root causes.
    - Separation of human-verified resolutions from AI hypotheses.
    - Knowledge Base synchronization and embedding updates.
    - Immutable audit trail recording.
    """

    @classmethod
    async def get_incident(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
    ) -> IncidentResponse:
        """
        Retrieves an incident by identifier, enforcing multi-tenant isolation.
        """
        return await IncidentDetectionService.get_incident_by_id(db, user, incident_id)

    @classmethod
    async def acknowledge_incident(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
    ) -> IncidentResponse:
        """
        Acknowledges an incident and appends an audit trail entry.
        """
        if user.role == UserRole.VIEWER:
            raise AppException("Viewers are not authorized to acknowledge incidents.", status_code=status.HTTP_403_FORBIDDEN)

        resp = await IncidentDetectionService.acknowledge_incident(db, user, incident_id)

        await AuditService.record_event(
            db=db,
            incident_id=resp.incident_id,
            user_id=resp.user_id,
            actor=user,
            action=AuditAction.ACKNOWLEDGED,
            details={"previous_status": IncidentStatus.OPEN.value, "new_status": IncidentStatus.ACKNOWLEDGED.value},
        )
        return resp

    @classmethod
    async def assign_incident(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
        payload: IncidentAssignRequest,
    ) -> IncidentResponse:
        """
        Assigns an incident to an engineer.
        Restricted to Admin and Engineer roles. Viewers are forbidden (403).
        """
        if user.role == UserRole.VIEWER:
            raise AppException("Viewers are not authorized to assign incidents.", status_code=status.HTTP_403_FORBIDDEN)

        incident = await cls.get_incident(db, user, incident_id)
        now = datetime.now(timezone.utc)

        await db["incidents"].update_one(
            {"incident_id": incident.incident_id},
            {
                "$set": {
                    "assigned_to": payload.assigned_to,
                    "assigned_at": now,
                    "assigned_by": user.id,
                    "updated_at": now,
                }
            },
        )

        await AuditService.record_event(
            db=db,
            incident_id=incident.incident_id,
            user_id=incident.user_id,
            actor=user,
            action=AuditAction.ASSIGNED,
            details={"assigned_to": payload.assigned_to, "assigned_by": user.email},
        )
        return await cls.get_incident(db, user, incident.incident_id)

    @classmethod
    async def update_severity(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
        payload: IncidentSeverityUpdateRequest,
    ) -> IncidentResponse:
        """
        Updates the priority/severity of an incident.
        Restricted to Admin and Engineer roles. Viewers are forbidden (403).
        """
        if user.role == UserRole.VIEWER:
            raise AppException("Viewers are not authorized to update incident severity.", status_code=status.HTTP_403_FORBIDDEN)

        incident = await cls.get_incident(db, user, incident_id)
        now = datetime.now(timezone.utc)

        await db["incidents"].update_one(
            {"incident_id": incident.incident_id},
            {
                "$set": {
                    "severity": payload.severity.value,
                    "updated_at": now,
                }
            },
        )

        await AuditService.record_event(
            db=db,
            incident_id=incident.incident_id,
            user_id=incident.user_id,
            actor=user,
            action=AuditAction.SEVERITY_UPDATED,
            details={"old_severity": incident.severity.value, "new_severity": payload.severity.value},
        )
        return await cls.get_incident(db, user, incident.incident_id)

    @classmethod
    async def add_investigation_note(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
        payload: InvestigationNoteCreate,
    ) -> IncidentResponse:
        """
        Appends an investigation note to an incident.
        Restricted to Admin and Engineer roles. Viewers are forbidden (403).
        """
        if user.role == UserRole.VIEWER:
            raise AppException("Viewers are not authorized to add investigation notes.", status_code=status.HTTP_403_FORBIDDEN)

        incident = await cls.get_incident(db, user, incident_id)
        now = datetime.now(timezone.utc)
        note_id = f"NOTE-{uuid4().hex[:8].upper()}"

        note_doc = {
            "note_id": note_id,
            "user_id": user.id,
            "user_email": user.email,
            "note": payload.note.strip(),
            "created_at": now,
        }

        await db["incidents"].update_one(
            {"incident_id": incident.incident_id},
            {
                "$push": {"investigation_notes": note_doc},
                "$set": {"updated_at": now},
            },
        )

        await AuditService.record_event(
            db=db,
            incident_id=incident.incident_id,
            user_id=incident.user_id,
            actor=user,
            action=AuditAction.NOTE_ADDED,
            details={"note_id": note_id, "note_snippet": payload.note[:100]},
        )
        return await cls.get_incident(db, user, incident.incident_id)

    @classmethod
    async def record_resolution(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
        payload: IncidentResolutionRequest,
    ) -> IncidentResponse:
        """
        Records structured root-cause findings and resolution actions,
        transitions status to RESOLVED, and synchronizes to Knowledge Base.
        """
        if user.role == UserRole.VIEWER:
            raise AppException("Viewers are not authorized to record resolutions.", status_code=status.HTTP_403_FORBIDDEN)

        incident = await cls.get_incident(db, user, incident_id)
        now = datetime.now(timezone.utc)

        update_fields: Dict[str, Any] = {
            "status": IncidentStatus.RESOLVED.value,
            "confirmed_root_cause": payload.confirmed_root_cause.strip(),
            "confirmed_resolution": payload.confirmed_resolution.strip(),
            "resolution_actions": payload.resolution_actions or [],
            "has_verified_resolution": payload.is_verified,
            "resolved_at": now,
            "resolved_by": user.id,
            "updated_at": now,
        }

        if payload.rca_analysis_id:
            update_fields["rca_analysis_id"] = payload.rca_analysis_id

        if payload.is_verified:
            update_fields["verified_at"] = now
            update_fields["verified_by"] = user.id

        await db["incidents"].update_one(
            {"incident_id": incident.incident_id},
            {"$set": update_fields},
        )

        if payload.notes:
            await cls.add_investigation_note(
                db, user, incident.incident_id, InvestigationNoteCreate(note=f"[Resolution Note]: {payload.notes}")
            )

        await AuditService.record_event(
            db=db,
            incident_id=incident.incident_id,
            user_id=incident.user_id,
            actor=user,
            action=AuditAction.RESOLUTION_RECORDED,
            details={
                "confirmed_root_cause": payload.confirmed_root_cause,
                "is_verified": payload.is_verified,
                "resolution_actions_count": len(payload.resolution_actions or []),
            },
        )

        # Knowledge Base feedback integration (Module 6.4)
        await cls.sync_knowledge_base(db, user, incident.incident_id)

        return await cls.get_incident(db, user, incident.incident_id)

    @classmethod
    async def verify_resolution(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
        payload: IncidentVerifyResolutionRequest,
    ) -> IncidentResponse:
        """
        Explicitly marks an incident's resolution as human engineer verified,
        distinguishing verified resolutions from unverified AI hypotheses.
        """
        if user.role == UserRole.VIEWER:
            raise AppException("Viewers are not authorized to verify resolutions.", status_code=status.HTTP_403_FORBIDDEN)

        incident = await cls.get_incident(db, user, incident_id)
        now = datetime.now(timezone.utc)

        update_fields: Dict[str, Any] = {
            "has_verified_resolution": payload.is_verified,
            "updated_at": now,
        }
        if payload.is_verified:
            update_fields["verified_at"] = now
            update_fields["verified_by"] = user.id

        await db["incidents"].update_one(
            {"incident_id": incident.incident_id},
            {"$set": update_fields},
        )

        if payload.verification_notes:
            await cls.add_investigation_note(
                db, user, incident.incident_id, InvestigationNoteCreate(note=f"[Verification]: {payload.verification_notes}")
            )

        await AuditService.record_event(
            db=db,
            incident_id=incident.incident_id,
            user_id=incident.user_id,
            actor=user,
            action=AuditAction.RESOLUTION_VERIFIED,
            details={"is_verified": payload.is_verified, "verified_by": user.email},
        )

        # Re-index to update Knowledge Base with verified resolution status & fresh embedding
        await cls.sync_knowledge_base(db, user, incident.incident_id)

        return await cls.get_incident(db, user, incident.incident_id)

    @classmethod
    async def sync_knowledge_base(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str,
    ) -> bool:
        """
        Synchronizes the incident's confirmed resolution into the historical Knowledge Base.
        Regenerates embeddings with verified resolution evidence.
        Catches errors gracefully so knowledge sync failure does not break incident operations.
        """
        indexer = KnowledgeIndexer(db=db)
        try:
            doc = await indexer.index_incident(
                incident_id=incident_id,
                user=user,
                force_reindex=True,
            )
            now = datetime.now(timezone.utc)
            await db["incidents"].update_one(
                {"incident_id": incident_id},
                {"$set": {"knowledge_synced": True, "knowledge_synced_at": now}},
            )
            await AuditService.record_event(
                db=db,
                incident_id=incident_id,
                user_id=doc.get("user_id", user.id),
                actor=user,
                action=AuditAction.KNOWLEDGE_SYNCED,
                details={"knowledge_id": doc.get("knowledge_id"), "has_verified_resolution": doc.get("has_verified_resolution")},
            )
            return True
        except Exception as exc:
            logger.error(f"Failed to synchronize incident '{incident_id}' to Knowledge Base: {exc}")
            now = datetime.now(timezone.utc)
            await db["incidents"].update_one(
                {"incident_id": incident_id},
                {"$set": {"knowledge_synced": False}},
            )
            await AuditService.record_event(
                db=db,
                incident_id=incident_id,
                user_id=user.id,
                actor=user,
                action=AuditAction.KNOWLEDGE_SYNC_FAILED,
                details={"error": str(exc)},
            )
            return False
