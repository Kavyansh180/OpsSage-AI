from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from backend.app.core.exceptions import ResourceNotFoundError
from backend.app.core.logging import get_logger
from backend.app.models.user import UserInDB, UserRole
from backend.app.services.redactor import SecretRedactor

logger = get_logger("services.evidence_collector")


@dataclass
class EvidenceBundle:
    """
    Encapsulates all verified diagnostic evidence collected for an incident.
    """
    incident: Dict[str, Any]
    logs: List[Dict[str, Any]]
    evidence_log_count: int
    redacted_secrets_count: int


class EvidenceCollector:
    """
    Retrieves, sanitizes, and prepares incident and log evidence for LLM analysis.
    Guarantees tenant isolation, chronological sorting, and secret redaction.
    """

    def __init__(self, db: AsyncDatabase):
        self._db = db

    async def collect_evidence(
        self,
        incident_id: str,
        user: UserInDB,
        max_evidence_logs: int = 30,
    ) -> EvidenceBundle:
        """
        Retrieves incident details and up to max_evidence_logs chronologically ordered,
        redacted logs for analysis.
        """
        incidents_col = self._db["incidents"]
        logs_col = self._db["logs"]

        # 1. Fetch incident by incident_id or ObjectId
        query: Dict[str, Any] = {"incident_id": incident_id}
        if ObjectId.is_valid(incident_id):
            query = {"$or": [{"incident_id": incident_id}, {"_id": ObjectId(incident_id)}]}

        incident_doc = await incidents_col.find_one(query)
        if not incident_doc:
            raise ResourceNotFoundError(f"Incident with ID '{incident_id}' not found.")

        # 2. Enforce tenant isolation: non-admins can only analyze their own incidents
        if user.role != UserRole.ADMIN and incident_doc.get("user_id") != user.id:
            raise ResourceNotFoundError(f"Incident with ID '{incident_id}' not found.")

        owner_user_id = incident_doc.get("user_id")
        related_log_ids = incident_doc.get("related_log_ids", [])

        # 3. Fetch associated logs
        logs_docs: List[Dict[str, Any]] = []

        if related_log_ids:
            # Convert valid IDs to ObjectIds
            object_ids = [ObjectId(lid) for lid in related_log_ids if ObjectId.is_valid(lid)]
            if object_ids:
                # Restrict to incident owner tenant
                cursor = logs_col.find({
                    "_id": {"$in": object_ids},
                    "user_id": owner_user_id,
                })
                logs_docs = await cursor.to_list(length=max_evidence_logs)

        # Fallback if no logs found via related_log_ids: query by error signature and environment
        if not logs_docs:
            cursor = logs_col.find({
                "user_id": owner_user_id,
                "service_name": incident_doc.get("service_name"),
                "environment": incident_doc.get("environment"),
                "error_signature": incident_doc.get("error_signature"),
            }).sort("timestamp", -1)
            logs_docs = await cursor.to_list(length=max_evidence_logs)

        # 4. Sort logs chronologically (oldest -> newest)
        def get_timestamp(doc: Dict[str, Any]) -> datetime:
            ts = doc.get("timestamp")
            if isinstance(ts, datetime):
                return ts
            return datetime.min

        logs_docs.sort(key=get_timestamp)

        # Truncate to max_evidence_logs if needed
        if len(logs_docs) > max_evidence_logs:
            logs_docs = logs_docs[-max_evidence_logs:]

        # 5. Sanitize incident fields and log messages using SecretRedactor
        total_redactions = 0

        # Sanitize incident title
        incident_title = incident_doc.get("title", "")
        clean_title, count = SecretRedactor.redact(incident_title)
        incident_doc["title"] = clean_title
        total_redactions += count

        sanitized_logs: List[Dict[str, Any]] = []
        for log_entry in logs_docs:
            raw_msg = log_entry.get("message", "")
            clean_msg, r_count = SecretRedactor.redact(raw_msg)
            total_redactions += r_count

            norm_msg = log_entry.get("normalized_message", "")
            clean_norm, n_count = SecretRedactor.redact(norm_msg)
            total_redactions += n_count

            sanitized_entry = {
                "id": str(log_entry.get("_id", "")),
                "timestamp": str(log_entry.get("timestamp", "")),
                "level": log_entry.get("level", "INFO"),
                "service_name": log_entry.get("service_name", ""),
                "environment": log_entry.get("environment", ""),
                "message": clean_msg,
                "normalized_message": clean_norm,
                "source": log_entry.get("source"),
                "request_id": log_entry.get("request_id"),
                "trace_id": log_entry.get("trace_id"),
            }
            sanitized_logs.append(sanitized_entry)

        return EvidenceBundle(
            incident=incident_doc,
            logs=sanitized_logs,
            evidence_log_count=len(sanitized_logs),
            redacted_secrets_count=total_redactions,
        )
