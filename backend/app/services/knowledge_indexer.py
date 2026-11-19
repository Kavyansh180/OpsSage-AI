from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.config import Settings, get_settings
from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.core.logging import get_logger
from backend.app.models.knowledge import HistoricalAnalysisSummary, KnowledgeDocumentInDB
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.knowledge import KnowledgeIndexResponse
from backend.app.services.embedding_service import EmbeddingService
from backend.app.services.redactor import SecretRedactor

logger = get_logger("services.knowledge_indexer")


class KnowledgeIndexer:
    """
    Constructs, embeds, and indexes historical incident knowledge documents in MongoDB Atlas.
    Guarantees idempotency, tenant isolation, and strict distinction between
    engineer-verified resolutions and AI hypotheses.
    """

    def __init__(
        self,
        db: AsyncDatabase,
        embedding_service: Optional[EmbeddingService] = None,
        settings: Optional[Settings] = None,
    ):
        self._db = db
        self._settings = settings or get_settings()
        self._embedder = embedding_service or EmbeddingService(self._settings)

    @classmethod
    def generate_knowledge_id(cls) -> str:
        """Generates a human-readable unique knowledge base identifier."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        rand = uuid4().hex[:6].upper()
        return f"KB-{ts}-{rand}"

    @classmethod
    def construct_embedding_text(
        cls,
        service_name: str,
        environment: str,
        title: str,
        diagnostic_summary: str,
        historical_analysis: Optional[HistoricalAnalysisSummary] = None,
        confirmed_resolution: Optional[str] = None,
        confirmed_root_cause: Optional[str] = None,
        resolution_actions: Optional[List[str]] = None,
    ) -> str:
        """
        Builds a structured, ground-truth-weighted text string used to generate the embedding.
        Sanitizes all credentials before embedding.
        """
        parts = [
            f"Service: {service_name}",
            f"Environment: {environment}",
            f"Incident Title: {title}",
            f"Diagnostics: {diagnostic_summary}",
        ]

        if historical_analysis:
            parts.append(f"Historical Hypothesis: {historical_analysis.probable_root_cause}")
            if historical_analysis.explanation:
                parts.append(f"Hypothesis Detail: {historical_analysis.explanation}")

        if confirmed_root_cause:
            parts.append(f"Confirmed Root Cause: {confirmed_root_cause}")

        if confirmed_resolution:
            parts.append(f"Verified Resolution: {confirmed_resolution}")

        if resolution_actions:
            actions_text = "; ".join(resolution_actions)
            parts.append(f"Resolution Actions: {actions_text}")

        raw_text = " | ".join(parts)
        clean_text = SecretRedactor.redact_text(raw_text)
        return clean_text

    async def _fetch_incident_diagnostic_summary(self, incident_doc: Dict[str, Any]) -> str:
        """
        Gathers diagnostic summary from related logs or falls back to incident title.
        """
        owner_id = incident_doc.get("user_id")
        related_log_ids = incident_doc.get("related_log_ids", [])
        logs_col = self._db["logs"]

        if related_log_ids:
            oids = [ObjectId(lid) for lid in related_log_ids if ObjectId.is_valid(lid)]
            if oids:
                cursor = logs_col.find({"_id": {"$in": oids}, "user_id": owner_id}).limit(5)
                log_docs = await cursor.to_list(length=5)
                if log_docs:
                    messages = [doc.get("message", "") for doc in log_docs if doc.get("message")]
                    if messages:
                        return " ; ".join(messages[:3])

        return incident_doc.get("title", "")

    async def _fetch_latest_analysis(self, incident_id: str, user_id: str) -> Optional[HistoricalAnalysisSummary]:
        """
        Retrieves the most recent RCA analysis for this incident, if one exists.
        Explicitly marked as an AI hypothesis.
        """
        analyses_col = self._db["analyses"]
        doc = await analyses_col.find_one(
            {"incident_id": incident_id, "user_id": user_id},
            sort=[("created_at", -1)],
        )
        if not doc:
            return None

        return HistoricalAnalysisSummary(
            analysis_id=doc.get("analysis_id"),
            probable_root_cause=doc.get("probable_root_cause", "Unknown hypothesis"),
            explanation=doc.get("explanation", ""),
            recommended_actions=doc.get("recommended_actions", []),
            confidence_level=str(doc.get("confidence_level", "LOW")),
        )

    async def index_incident(
        self,
        incident_id: str,
        user: UserInDB,
        force_reindex: bool = False,
    ) -> Dict[str, Any]:
        """
        Builds, embeds, and stores a knowledge base document for a specific incident.
        Idempotent: updates existing document if already indexed.
        """
        incidents_col = self._db["incidents"]
        kb_col = self._db["knowledge_base"]

        # 1. Fetch source incident
        query: Dict[str, Any] = {"incident_id": incident_id}
        if ObjectId.is_valid(incident_id):
            query = {"$or": [{"incident_id": incident_id}, {"_id": ObjectId(incident_id)}]}

        incident_doc = await incidents_col.find_one(query)
        if not incident_doc:
            raise ResourceNotFoundError(f"Incident '{incident_id}' not found.")

        # Enforce tenant isolation
        if user.role != UserRole.ADMIN and incident_doc.get("user_id") != user.id:
            raise ResourceNotFoundError(f"Incident '{incident_id}' not found.")

        owner_user_id = incident_doc.get("user_id")
        resolved_incident_id = str(incident_doc.get("incident_id", incident_id))

        # Check existing knowledge record
        existing = await kb_col.find_one({
            "user_id": owner_user_id,
            "source_incident_id": resolved_incident_id,
        })
        if existing and not force_reindex:
            logger.info(f"Incident '{resolved_incident_id}' already indexed as '{existing.get('knowledge_id')}'.")
            return existing

        # 2. Gather diagnostic evidence and historical RCA
        diag_summary = await self._fetch_incident_diagnostic_summary(incident_doc)
        historical_analysis = await self._fetch_latest_analysis(resolved_incident_id, owner_user_id)

        # 3. Check for confirmed resolution (only if actually verified by an engineer)
        # Note: Do NOT treat AI-generated probable_root_cause as confirmed resolution!
        confirmed_resolution = incident_doc.get("confirmed_resolution")
        confirmed_root_cause = incident_doc.get("confirmed_root_cause")
        resolution_actions = incident_doc.get("resolution_actions") or []
        has_verified = bool(incident_doc.get("has_verified_resolution", False) or (confirmed_resolution and confirmed_resolution.strip()))

        # 4. Construct embedding text and generate vector
        clean_title = SecretRedactor.redact_text(incident_doc.get("title", ""))
        clean_diag = SecretRedactor.redact_text(diag_summary)
        embed_text = self.construct_embedding_text(
            service_name=incident_doc.get("service_name", ""),
            environment=incident_doc.get("environment", ""),
            title=clean_title,
            diagnostic_summary=clean_diag,
            historical_analysis=historical_analysis,
            confirmed_resolution=confirmed_resolution if has_verified else None,
            confirmed_root_cause=confirmed_root_cause if has_verified else None,
            resolution_actions=resolution_actions if has_verified else None,
        )

        embedding_vector = self._embedder.generate_embedding(embed_text)

        # 5. Build document payload
        now = datetime.now(timezone.utc)
        knowledge_id = existing.get("knowledge_id") if existing else self.generate_knowledge_id()

        update_payload: Dict[str, Any] = {
            "knowledge_id": knowledge_id,
            "source_incident_id": resolved_incident_id,
            "incident_ref_id": resolved_incident_id,
            "user_id": owner_user_id,
            "service_name": incident_doc.get("service_name", ""),
            "environment": incident_doc.get("environment", ""),
            "error_signature": incident_doc.get("error_signature", ""),
            "title": clean_title,
            "description": incident_doc.get("description"),
            "diagnostic_summary": clean_diag,
            "historical_analysis": historical_analysis.model_dump() if historical_analysis else None,
            "confirmed_root_cause": confirmed_root_cause if has_verified else None,
            "confirmed_resolution": confirmed_resolution if has_verified else None,
            "resolution_actions": resolution_actions if has_verified else [],
            "has_verified_resolution": has_verified,
            "embedding": embedding_vector,
            "source_metadata": {
                "event_count": incident_doc.get("event_count", 1),
                "severity": incident_doc.get("severity", "LOW"),
                "status": incident_doc.get("status", "OPEN"),
                "first_seen": str(incident_doc.get("first_seen", "")),
                "last_seen": str(incident_doc.get("last_seen", "")),
            },
            "updated_at": now,
        }

        # Idempotent upsert
        filter_doc = {"user_id": owner_user_id, "source_incident_id": resolved_incident_id}
        doc = await kb_col.find_one_and_update(
            filter_doc,
            {
                "$set": update_payload,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        logger.info(f"Indexed incident '{resolved_incident_id}' into knowledge base as '{knowledge_id}'.")
        return doc

    async def index_incidents_batch(
        self,
        user: UserInDB,
        limit: int = 50,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        force_reindex: bool = False,
    ) -> KnowledgeIndexResponse:
        """
        Batch indexes historical incidents matching the provided criteria.
        Tracks failures gracefully without corrupting existing records.
        """
        incidents_col = self._db["incidents"]

        query: Dict[str, Any] = {}
        if user.role != UserRole.ADMIN:
            query["user_id"] = user.id

        if service_name:
            query["service_name"] = service_name
        if environment:
            query["environment"] = environment

        cursor = incidents_col.find(query).sort("last_seen", -1).limit(limit)
        incident_docs = await cursor.to_list(length=limit)

        total_eligible = len(incident_docs)
        indexed_count = 0
        skipped_count = 0
        failed_count = 0
        indexed_ids: List[str] = []
        errors: List[Dict[str, Any]] = []

        kb_col = self._db["knowledge_base"]

        for inc in incident_docs:
            inc_id = inc.get("incident_id")
            u_id = inc.get("user_id")

            # Check if already indexed
            if not force_reindex:
                already_indexed = await kb_col.find_one({"user_id": u_id, "source_incident_id": inc_id})
                if already_indexed:
                    skipped_count += 1
                    continue

            try:
                # Index incident
                doc = await self.index_incident(
                    incident_id=inc_id,
                    user=user,
                    force_reindex=force_reindex,
                )
                indexed_count += 1
                indexed_ids.append(doc.get("knowledge_id"))
            except Exception as exc:
                failed_count += 1
                logger.error(f"Failed to index incident '{inc_id}': {exc}")
                errors.append({"incident_id": inc_id, "error": str(exc)})

        return KnowledgeIndexResponse(
            total_eligible=total_eligible,
            indexed_count=indexed_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            indexed_knowledge_ids=indexed_ids,
            errors=errors,
        )
