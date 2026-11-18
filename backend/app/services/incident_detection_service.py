import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from fastapi import status
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, OperationFailure

from backend.app.config import get_settings
from backend.app.core.exceptions import AppException, ResourceNotFoundError
from backend.app.core.logging import get_logger
from backend.app.models.incident import IncidentInDB, IncidentSeverity, IncidentStatus
from backend.app.models.log import LogLevel
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.incident import IncidentResponse, PaginatedIncidentResponse
from backend.app.services.error_signature import ErrorSignatureGenerator

logger = get_logger("services.incident_detection")
settings = get_settings()

def _ensure_utc(dt: Any, default: datetime) -> datetime:
    """Ensures a datetime is UTC-aware and falls back to default if missing."""
    if not dt or not isinstance(dt, datetime):
        dt = default
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class IncidentDetectionService:
    """
    Deterministic incident detection engine.
    Orchestrates error signature clustering, sliding-window frequency counting,
    lease-fenced atomic log claiming, idempotent event accounting, and incident lifecycle management.
    """

    @classmethod
    def generate_incident_id(cls) -> str:
        """Generates a human-readable unique incident ID (e.g. INC-20261102-A1B2C3)."""
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        unique_suffix = uuid.uuid4().hex[:6].upper()
        return f"INC-{date_str}-{unique_suffix}"

    @classmethod
    def determine_severity(cls, window_count: int, has_critical: bool) -> IncidentSeverity:
        """
        Calculates severity deterministically based on frequency and severity evidence:
        - CRITICAL: 15+ events or any CRITICAL log in window
        - HIGH: 8-14 events
        - MEDIUM: 5-7 events
        - LOW: < 5 events
        """
        if has_critical or window_count >= settings.INCIDENT_CRITICAL_EVENT_THRESHOLD:
            return IncidentSeverity.CRITICAL
        elif window_count >= settings.INCIDENT_HIGH_EVENT_THRESHOLD:
            return IncidentSeverity.HIGH
        elif window_count >= settings.INCIDENT_MEDIUM_EVENT_THRESHOLD:
            return IncidentSeverity.MEDIUM
        else:
            return IncidentSeverity.LOW

    @classmethod
    async def claim_log_for_processing(
        cls,
        db: AsyncDatabase,
        log_id: Any
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Acquires an atomic processing lease for a log document.
        Uses a fencing lease token to ensure exactly-once claiming.
        Recovers expired leases if an earlier worker crashed.
        Returns: (claimed_log_dict, lease_token) or (None, None).
        """
        now = datetime.now(timezone.utc)
        lease_timeout = now + timedelta(seconds=settings.INCIDENT_PROCESSING_LEASE_SECONDS)
        lease_token = uuid.uuid4().hex

        # Query matches: PENDING, unassigned, or an expired lease (crash recovery)
        claim_filter = {
            "_id": ObjectId(log_id) if isinstance(log_id, str) and ObjectId.is_valid(log_id) else log_id,
            "$or": [
                {"detection_status": "PENDING"},
                {"detection_status": None},
                {"detection_status": "PROCESSING", "detection_lease_until": {"$lt": now}}
            ]
        }
        claim_update = {
            "$set": {
                "detection_status": "PROCESSING",
                "lease_token": lease_token,
                "detection_lease_until": lease_timeout
            }
        }

        claimed = await db["logs"].find_one_and_update(
            claim_filter,
            claim_update,
            return_document=ReturnDocument.AFTER
        )
        if not claimed:
            return None, None

        if "detection_lease_until" in claimed and claimed["detection_lease_until"]:
            if claimed["detection_lease_until"].tzinfo is None:
                claimed["detection_lease_until"] = claimed["detection_lease_until"].replace(tzinfo=timezone.utc)

        return claimed, lease_token

    @classmethod
    async def process_log_for_detection(
        cls,
        db: AsyncDatabase,
        user_id: str,
        log_id: Any
    ) -> Optional[str]:
        """
        Evaluates a newly persisted log document for incident triggering or active incident updates.
        Returns the incident_id if an incident was created or updated, else None.
        """
        claimed_log, lease_token = await cls.claim_log_for_processing(db, log_id)
        if not claimed_log or not lease_token:
            # Already claimed or processed by another worker / attempt
            return None

        actual_log_id = claimed_log["_id"]
        level = claimed_log.get("level")

        # 1. Scope restriction: Only ERROR and CRITICAL logs trigger incident detection
        if level not in [LogLevel.ERROR.value, LogLevel.CRITICAL.value, LogLevel.ERROR, LogLevel.CRITICAL]:
            await db["logs"].update_one(
                {"_id": actual_log_id, "lease_token": lease_token},
                {"$set": {"detection_status": "SKIPPED", "lease_token": None, "detection_lease_until": None}}
            )
            return None

        # 2. Extract failure grouping attributes
        service_name = claimed_log.get("service_name", "unknown-service")
        environment = claimed_log.get("environment", "production")
        normalized_msg = claimed_log.get("normalized_message") or claimed_log.get("message", "")
        error_signature = claimed_log.get("error_signature")

        if not error_signature:
            error_signature = ErrorSignatureGenerator.generate(
                service_name=service_name,
                environment=environment,
                normalized_message=normalized_msg
            )
            # Ensure error_signature is recorded on log document
            await db["logs"].update_one(
                {"_id": actual_log_id, "lease_token": lease_token},
                {"$set": {"error_signature": error_signature}}
            )

        log_ts = claimed_log.get("timestamp") or datetime.now(timezone.utc)
        if log_ts.tzinfo is None:
            log_ts = log_ts.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        window_start = log_ts - timedelta(seconds=settings.INCIDENT_DETECTION_WINDOW_SECONDS)

        # 3. Check for an ACTIVE incident (OPEN or ACKNOWLEDGED)
        active_filter = {
            "user_id": user_id,
            "environment": environment,
            "service_name": service_name,
            "error_signature": error_signature,
            "status": {"$in": [IncidentStatus.OPEN.value, IncidentStatus.ACKNOWLEDGED.value]}
        }
        active_incident = await db["incidents"].find_one(active_filter)

        # -------------------------------------------------------------
        # BRANCH A: Active Incident Exists -> Update Regardless of Threshold
        # -------------------------------------------------------------
        if active_incident:
            target_incident_id = active_incident["incident_id"]

            # SAFEGUARD 1 & 2: Atomic Transaction for Active Incident Update & Log Completion
            client = db.client
            for attempt in range(5):
                try:
                    async with client.start_session() as session:
                        await session.start_transaction()
                        try:
                            # 1. Fetch FRESH active incident inside this transaction attempt
                            fresh_incident = await db["incidents"].find_one(
                                {
                                    "_id": active_incident["_id"],
                                    "status": {"$in": [IncidentStatus.OPEN.value, IncidentStatus.ACKNOWLEDGED.value]}
                                },
                                session=session
                            )
                            if not fresh_incident:
                                # Incident was concurrently resolved or is no longer active
                                logger.info(
                                    f"Active incident {target_incident_id} is no longer open/acknowledged; aborting update."
                                )
                                await session.abort_transaction()
                                return None

                            # 2. Verify lease token and that log has not been assigned to an incident yet
                            log_update = await db["logs"].update_one(
                                {
                                    "_id": actual_log_id,
                                    "lease_token": lease_token,
                                    "incident_id": None
                                },
                                {
                                    "$set": {
                                        "detection_status": "PROCESSED",
                                        "incident_id": target_incident_id,
                                        "lease_token": None,
                                        "detection_lease_until": None
                                    }
                                },
                                session=session
                            )
                            if log_update.modified_count != 1:
                                # Check if already linked to this incident by a previous attempt or concurrent claim
                                check_log = await db["logs"].find_one({"_id": actual_log_id}, session=session)
                                if check_log and check_log.get("incident_id") == target_incident_id:
                                    await session.abort_transaction()
                                    return target_incident_id
                                await session.abort_transaction()
                                return None

                            # 3. Calculate latest window rate and severity evidence
                            window_logs_cursor = db["logs"].find({
                                "user_id": user_id,
                                "environment": environment,
                                "service_name": service_name,
                                "error_signature": error_signature,
                                "timestamp": {"$gte": window_start, "$lte": max(_ensure_utc(fresh_incident.get("last_seen"), log_ts), log_ts)}
                            }, session=session)
                            window_logs = await window_logs_cursor.to_list(length=500)
                            window_count = max(len(window_logs), fresh_incident.get("window_event_count", 0) + 1)

                            has_crit = any(
                                l.get("level") in ["CRITICAL", LogLevel.CRITICAL.value]
                                for l in window_logs
                            ) or claimed_log.get("level") in ["CRITICAL", LogLevel.CRITICAL.value]

                            incoming_sev = cls.determine_severity(window_count, has_crit)

                            # MONOTONIC SEVERITY ESCALATION:
                            # Compare incoming calculated severity with fresh database severity.
                            # Severity can ONLY move up, NEVER down!
                            db_sev = IncidentSeverity(fresh_incident.get("severity", IncidentSeverity.LOW.value))
                            final_sev = max(db_sev, incoming_sev, key=lambda s: IncidentSeverity.rank(s))

                            # TIMESTAMPS:
                            # first_seen is the MINIMUM of existing first_seen and incoming log_ts
                            existing_first_seen = _ensure_utc(fresh_incident.get("first_seen"), log_ts)
                            new_first_seen = min(existing_first_seen, log_ts)

                            # last_seen is the MAXIMUM of existing last_seen and incoming log_ts
                            existing_last_seen = _ensure_utc(fresh_incident.get("last_seen"), log_ts)
                            new_last_seen = max(existing_last_seen, log_ts)

                            # 4. Increment event_count and atomically update incident state
                            inc_update = await db["incidents"].update_one(
                                {
                                    "_id": fresh_incident["_id"],
                                    "status": {"$in": [IncidentStatus.OPEN.value, IncidentStatus.ACKNOWLEDGED.value]}
                                },
                                {
                                    "$inc": {"event_count": 1},
                                    "$set": {
                                        "first_seen": new_first_seen,
                                        "last_seen": new_last_seen,
                                        "updated_at": now,
                                        "severity": final_sev.value,
                                        "window_event_count": window_count
                                    },
                                    "$push": {
                                        "related_log_ids": {
                                            "$each": [str(actual_log_id)],
                                            "$slice": -100
                                        }
                                    }
                                },
                                session=session
                            )
                            if inc_update.modified_count != 1:
                                logger.warning(f"Active incident {target_incident_id} not updated; aborting transaction.")
                                await session.abort_transaction()
                                return None

                            await session.commit_transaction()
                            logger.info(f"Updated active incident {target_incident_id} with log {actual_log_id} (transaction committed).")
                            return target_incident_id
                        except OperationFailure as tx_err:
                            await session.abort_transaction()
                            if hasattr(tx_err, "has_error_label") and tx_err.has_error_label("TransientTransactionError"):
                                await asyncio.sleep(0.05 * (attempt + 1))
                                continue
                            raise
                except OperationFailure as sess_err:
                    if hasattr(sess_err, "has_error_label") and sess_err.has_error_label("TransientTransactionError"):
                        await asyncio.sleep(0.05 * (attempt + 1))
                        continue
                    raise
            return None

        # -------------------------------------------------------------
        # BRANCH B: No Active Incident -> Check Sliding Window Threshold
        # -------------------------------------------------------------
        window_logs_cursor = db["logs"].find({
            "user_id": user_id,
            "environment": environment,
            "service_name": service_name,
            "error_signature": error_signature,
            "timestamp": {"$gte": window_start, "$lte": log_ts}
        }).sort("timestamp", 1)
        matching_window_logs = await window_logs_cursor.to_list(length=500)

        # If threshold not reached: log is processed, but no incident is created yet
        if len(matching_window_logs) < settings.INCIDENT_MIN_EVENTS_THRESHOLD:
            await db["logs"].update_one(
                {"_id": actual_log_id, "lease_token": lease_token},
                {
                    "$set": {
                        "detection_status": "PROCESSED",
                        "incident_id": None,
                        "lease_token": None,
                        "detection_lease_until": None
                    }
                }
            )
            logger.debug(
                f"Log {actual_log_id} evaluated: count {len(matching_window_logs)} "
                f"< threshold {settings.INCIDENT_MIN_EVENTS_THRESHOLD}."
            )
            return None

        # Threshold reached! Create new incident incorporating earlier window logs
        # SAFEGUARD 1: Exactly-once event accounting via atomic ownership claiming
        earlier_unclaimed_ids = [d["_id"] for d in matching_window_logs if d["_id"] != actual_log_id]
        claimed_earlier_ids: List[Any] = []

        if earlier_unclaimed_ids:
            lease_timeout = now + timedelta(seconds=settings.INCIDENT_PROCESSING_LEASE_SECONDS)
            # Claim earlier unlinked window logs using our lease token.
            # Logs evaluated below threshold were marked PROCESSED with incident_id=None;
            # they must now be claimed into this new incident.
            await db["logs"].update_many(
                {
                    "_id": {"$in": earlier_unclaimed_ids},
                    "incident_id": None,
                    "$or": [
                        {"detection_status": {"$in": ["PENDING", "PROCESSED", None]}},
                        {"detection_status": "PROCESSING", "detection_lease_until": {"$lt": now}}
                    ]
                },
                {"$set": {"detection_status": "PROCESSING", "lease_token": lease_token, "detection_lease_until": lease_timeout}}
            )
            # Find the ones we successfully claimed
            claimed_earlier = await db["logs"].find(
                {"_id": {"$in": earlier_unclaimed_ids}, "lease_token": lease_token}
            ).to_list(length=500)
            claimed_earlier_ids = [d["_id"] for d in claimed_earlier]

        # Logs contributing to this new incident
        contributing_logs = [claimed_log] + [d for d in matching_window_logs if d["_id"] in claimed_earlier_ids]
        initial_event_count = len(contributing_logs)

        def _get_aware_ts(doc: dict) -> datetime:
            ts = doc.get("timestamp")
            if not ts or not isinstance(ts, datetime):
                ts = doc.get("ingested_at", now)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts

        first_seen_ts = min(_get_aware_ts(d) for d in contributing_logs)
        last_seen_ts = max(_get_aware_ts(d) for d in contributing_logs)

        has_crit = any(
            d.get("level") in ["CRITICAL", LogLevel.CRITICAL.value]
            for d in matching_window_logs
        )
        initial_severity = cls.determine_severity(len(matching_window_logs), has_crit)
        incident_id = cls.generate_incident_id()

        new_incident = IncidentInDB(
            incident_id=incident_id,
            user_id=user_id,
            environment=environment,
            service_name=service_name,
            error_signature=error_signature,
            title=normalized_msg[:200] if normalized_msg else f"Recurring error in {service_name}",
            severity=initial_severity,
            status=IncidentStatus.OPEN,
            first_seen=first_seen_ts,
            last_seen=last_seen_ts,
            window_event_count=len(matching_window_logs),
            event_count=initial_event_count,
            related_log_ids=[str(d["_id"]) for d in contributing_logs[-100:]],
            created_at=now,
            updated_at=now
        )

        all_claimed_ids = [actual_log_id] + claimed_earlier_ids
        target_incident_id = incident_id
        client = db.client

        # SAFEGUARD 1 & 2: Atomic Transaction for Initial Incident Creation & Log Assignment
        try:
            async with client.start_session() as session:
                await session.start_transaction()
                try:
                    # 1. Verify our lease on all claimed logs and ensure incident_id is None
                    claimed_count = await db["logs"].count_documents(
                        {"_id": {"$in": all_claimed_ids}, "lease_token": lease_token, "incident_id": None},
                        session=session
                    )
                    if claimed_count != len(all_claimed_ids):
                        logger.warning(
                            f"Fencing rejection during creation: claimed {len(all_claimed_ids)} logs, "
                            f"but verified {claimed_count} with valid lease."
                        )
                        await session.abort_transaction()
                        return None

                    # 2. Insert new incident with unique index concurrency protection
                    insert_dict = new_incident.model_dump(by_alias=True)
                    if "_id" in insert_dict and insert_dict["_id"] is None:
                        del insert_dict["_id"]
                    await db["incidents"].insert_one(insert_dict, session=session)

                    # 3. Mark all claimed logs PROCESSED matching lease_token
                    await db["logs"].update_many(
                        {"_id": {"$in": all_claimed_ids}, "lease_token": lease_token},
                        {
                            "$set": {
                                "detection_status": "PROCESSED",
                                "incident_id": target_incident_id,
                                "lease_token": None,
                                "detection_lease_until": None
                            }
                        },
                        session=session
                    )

                    await session.commit_transaction()
                    logger.info(
                        f"Incident {incident_id} created for {service_name} ({environment}) "
                        f"with {initial_event_count} initial events (committed atomically)."
                    )
                    return incident_id
                except (DuplicateKeyError, OperationFailure) as creation_tx_err:
                    await session.abort_transaction()
                    raise
                except Exception as e:
                    await session.abort_transaction()
                    logger.error(f"Transaction aborted during initial incident creation: {e}")
                    raise
        except (DuplicateKeyError, OperationFailure) as creation_err:
            if not isinstance(creation_err, DuplicateKeyError) and not (
                hasattr(creation_err, "has_error_label") and creation_err.has_error_label("TransientTransactionError")
            ):
                raise
            # Concurrent worker created the active incident or caused a write conflict!
            # The previous transaction was aborted cleanly.
            # Retry updating the active race winner with backoff.
            logger.info("Concurrent creation race detected; resolving against existing active incident.")
            for race_attempt in range(5):
                await asyncio.sleep(0.05 * (race_attempt + 1))
                try:
                    async with client.start_session() as session:
                        await session.start_transaction()
                        try:
                            active_race_winner = await db["incidents"].find_one(active_filter, session=session)
                            if not active_race_winner:
                                await session.abort_transaction()
                                continue
                            target_incident_id = active_race_winner["incident_id"]

                            # Monotonic severity comparison against fresh race winner in DB
                            winner_db_sev = IncidentSeverity(active_race_winner.get("severity", IncidentSeverity.LOW.value))
                            winner_final_sev = max(winner_db_sev, initial_severity, key=lambda s: IncidentSeverity.rank(s))

                            # Timestamps against fresh race winner:
                            # first_seen is MINIMUM of existing and incoming window first seen
                            winner_first_seen = _ensure_utc(active_race_winner.get("first_seen"), first_seen_ts)
                            winner_new_first_seen = min(winner_first_seen, first_seen_ts)

                            # last_seen is MAXIMUM of existing and incoming window last seen
                            winner_last_seen = _ensure_utc(active_race_winner.get("last_seen"), last_seen_ts)
                            winner_new_last_seen = max(winner_last_seen, last_seen_ts)

                            winner_window_count = max(
                                len(matching_window_logs),
                                active_race_winner.get("window_event_count", 0) + initial_event_count
                            )

                            await db["incidents"].update_one(
                                {
                                    "_id": active_race_winner["_id"],
                                    "status": {"$in": [IncidentStatus.OPEN.value, IncidentStatus.ACKNOWLEDGED.value]}
                                },
                                {
                                    "$inc": {"event_count": initial_event_count},
                                    "$set": {
                                        "first_seen": winner_new_first_seen,
                                        "last_seen": winner_new_last_seen,
                                        "updated_at": now,
                                        "severity": winner_final_sev.value,
                                        "window_event_count": winner_window_count
                                    },
                                    "$push": {
                                        "related_log_ids": {
                                            "$each": [str(_id) for _id in all_claimed_ids],
                                            "$slice": -100
                                        }
                                    }
                                },
                                session=session
                            )
                            await db["logs"].update_many(
                                {"_id": {"$in": all_claimed_ids}, "lease_token": lease_token},
                                {
                                    "$set": {
                                        "detection_status": "PROCESSED",
                                        "incident_id": target_incident_id,
                                        "lease_token": None,
                                        "detection_lease_until": None
                                    }
                                },
                                session=session
                            )
                            await session.commit_transaction()
                            logger.info(
                                f"Concurrency race resolved atomically: updated active incident {target_incident_id} "
                                f"with {initial_event_count} events (attempt {race_attempt + 1})."
                            )
                            return target_incident_id
                        except OperationFailure as race_op_err:
                            await session.abort_transaction()
                            if hasattr(race_op_err, "has_error_label") and race_op_err.has_error_label("TransientTransactionError"):
                                continue
                            raise
                except OperationFailure as race_sess_err:
                    if hasattr(race_sess_err, "has_error_label") and race_sess_err.has_error_label("TransientTransactionError"):
                        continue
                    raise
            return None

    # -----------------------------------------------------------------
    # Retrieval & Lifecycle Management
    # -----------------------------------------------------------------

    @classmethod
    async def get_incidents(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        environment: Optional[str] = None,
        service_name: Optional[str] = None,
        status_filter: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedIncidentResponse:
        """
        Retrieves incidents with multi-tenant isolation, filtering, and pagination.
        """
        query: Dict[str, Any] = {}

        if user.role != UserRole.ADMIN:
            query["user_id"] = user.id

        if environment:
            query["environment"] = environment
        if service_name:
            query["service_name"] = service_name
        if status_filter:
            query["status"] = status_filter.upper()
        if severity:
            query["severity"] = severity.upper()

        if start_time or end_time:
            query["last_seen"] = {}
            if start_time:
                query["last_seen"]["$gte"] = start_time
            if end_time:
                query["last_seen"]["$lte"] = end_time

        total = await db["incidents"].count_documents(query)
        cursor = db["incidents"].find(query).sort("last_seen", -1).skip(offset).limit(limit)
        docs = await cursor.to_list(length=limit)

        items = []
        for d in docs:
            d["id"] = str(d["_id"])
            items.append(IncidentResponse.model_validate(d))

        return PaginatedIncidentResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset
        )

    @classmethod
    async def get_incident_by_id(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str
    ) -> IncidentResponse:
        """
        Retrieves a single incident by incident_id or MongoDB ObjectId.
        Enforces tenant isolation: returns 404 if not found or unauthorized.
        """
        query: Dict[str, Any] = {}
        if ObjectId.is_valid(incident_id):
            query["$or"] = [{"incident_id": incident_id}, {"_id": ObjectId(incident_id)}]
        else:
            query["incident_id"] = incident_id

        doc = await db["incidents"].find_one(query)
        if not doc:
            raise ResourceNotFoundError(f"Incident '{incident_id}' not found.")

        # Multi-tenant isolation
        if user.role != UserRole.ADMIN and doc.get("user_id") != user.id:
            raise ResourceNotFoundError(f"Incident '{incident_id}' not found.")

        doc["id"] = str(doc["_id"])
        return IncidentResponse.model_validate(doc)

    @classmethod
    async def acknowledge_incident(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str
    ) -> IncidentResponse:
        """
        Transitions incident from OPEN -> ACKNOWLEDGED.
        Restricted to admin and engineer roles.
        """
        if user.role == UserRole.VIEWER:
            raise AppException("Viewers are not authorized to acknowledge incidents.", status_code=status.HTTP_403_FORBIDDEN)

        incident = await cls.get_incident_by_id(db, user, incident_id)
        if incident.status == IncidentStatus.RESOLVED:
            raise AppException("Cannot acknowledge an already resolved incident.", status_code=status.HTTP_400_BAD_REQUEST)

        now = datetime.now(timezone.utc)
        await db["incidents"].update_one(
            {"incident_id": incident.incident_id},
            {
                "$set": {
                    "status": IncidentStatus.ACKNOWLEDGED.value,
                    "acknowledged_at": now,
                    "acknowledged_by": user.id,
                    "updated_at": now
                }
            }
        )
        return await cls.get_incident_by_id(db, user, incident_id)

    @classmethod
    async def resolve_incident(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        incident_id: str
    ) -> IncidentResponse:
        """
        Transitions incident to RESOLVED.
        Permanently freezes the historical record; subsequent failures trigger a new incident.
        Restricted to admin and engineer roles.
        """
        if user.role == UserRole.VIEWER:
            raise AppException("Viewers are not authorized to resolve incidents.", status_code=status.HTTP_403_FORBIDDEN)

        incident = await cls.get_incident_by_id(db, user, incident_id)
        if incident.status == IncidentStatus.RESOLVED:
            return incident  # Idempotent resolve

        now = datetime.now(timezone.utc)
        await db["incidents"].update_one(
            {"incident_id": incident.incident_id},
            {
                "$set": {
                    "status": IncidentStatus.RESOLVED.value,
                    "resolved_at": now,
                    "resolved_by": user.id,
                    "updated_at": now
                }
            }
        )
        logger.info(f"Incident {incident.incident_id} marked RESOLVED by user {user.email}.")
        return await cls.get_incident_by_id(db, user, incident_id)
