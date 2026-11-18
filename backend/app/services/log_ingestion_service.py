from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import status
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import BulkWriteError
from backend.app.config import get_settings
from backend.app.core.exceptions import AppException, ResourceNotFoundError
from backend.app.core.logging import get_logger
from backend.app.models.log import LogLevel
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.log import (
    BatchItemError,
    BatchLogIngestRequest,
    BatchLogIngestResponse,
    LogIngestRequest,
    LogResponse,
    PaginatedLogResponse,
)
from backend.app.services.error_signature import ErrorSignatureGenerator
from backend.app.services.incident_detection_service import IncidentDetectionService
from backend.app.services.log_normalizer import LogNormalizer
from backend.app.services.log_parser import LogParser

logger = get_logger("services.log_ingestion")
settings = get_settings()


class LogIngestionService:
    """
    Orchestrates log parsing, normalization, validation, and asynchronous MongoDB persistence.
    """

    @classmethod
    async def ingest_single_log(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        log_in: LogIngestRequest
    ) -> LogResponse:
        """
        Parses, normalizes, and stores a single log entry associated with the user.
        """
        try:
            parsed = LogParser.parse(
                raw_log=log_in.raw_log,
                explicit_message=log_in.message,
                explicit_service=log_in.service_name,
                explicit_env=log_in.environment,
                explicit_level=log_in.level,
                explicit_timestamp=log_in.timestamp,
                explicit_metadata=log_in.metadata,
                explicit_request_id=log_in.request_id,
                explicit_trace_id=log_in.trace_id,
                explicit_host=log_in.host,
                explicit_source=log_in.source,
            )
        except Exception as exc:
            logger.warning(f"Failed to parse log from user {user.email}: {exc}")
            raise AppException(
                message=f"Log parsing error: {str(exc)}",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        normalized_msg = LogNormalizer.normalize(parsed.message)
        now = datetime.now(timezone.utc)

        is_error_or_crit = parsed.level in [LogLevel.ERROR, LogLevel.CRITICAL]
        error_sig = None
        if is_error_or_crit:
            error_sig = ErrorSignatureGenerator.generate(
                service_name=parsed.service_name,
                environment=parsed.environment,
                normalized_message=normalized_msg
            )

        doc = {
            "user_id": user.id,
            "service_name": parsed.service_name,
            "environment": parsed.environment,
            "level": parsed.level.value,
            "message": parsed.message,
            "normalized_message": normalized_msg,
            "error_signature": error_sig,
            "detection_status": "PENDING" if is_error_or_crit else "SKIPPED",
            "incident_id": None,
            "timestamp": parsed.timestamp,
            "ingested_at": now,
            "source": parsed.source,
            "host": parsed.host,
            "request_id": parsed.request_id,
            "trace_id": parsed.trace_id,
            "metadata": parsed.metadata,
            "raw_log": parsed.raw_log,
        }

        result = await db["logs"].insert_one(doc)
        logger.debug(f"Log {result.inserted_id} ingested for service '{parsed.service_name}'.")

        # Asynchronous/Safe Incident Detection Trigger
        if is_error_or_crit:
            try:
                await IncidentDetectionService.process_log_for_detection(
                    db=db,
                    user_id=user.id,
                    log_id=result.inserted_id
                )
            except Exception as exc:
                logger.error(f"Incident detection non-fatal error on log {result.inserted_id}: {exc}")

        return LogResponse(
            id=str(result.inserted_id),
            user_id=user.id,
            service_name=parsed.service_name,
            environment=parsed.environment,
            level=parsed.level,
            message=parsed.message,
            normalized_message=normalized_msg,
            timestamp=parsed.timestamp,
            ingested_at=now,
            source=parsed.source,
            host=parsed.host,
            request_id=parsed.request_id,
            trace_id=parsed.trace_id,
            metadata=parsed.metadata,
            raw_log=parsed.raw_log,
        )

    @classmethod
    async def ingest_batch_logs(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        batch_in: BatchLogIngestRequest
    ) -> BatchLogIngestResponse:
        """
        Processes a batch of logs with atomic per-item error isolation.
        Does not allow one malformed entry to fail the entire batch.
        """
        total = len(batch_in.logs)
        if total > settings.MAX_LOG_BATCH_SIZE:
            raise AppException(
                message=(
                    f"Batch size of {total} exceeds the maximum allowed limit of "
                    f"{settings.MAX_LOG_BATCH_SIZE} records per request."
                ),
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        now = datetime.now(timezone.utc)
        docs_to_insert: List[Dict[str, Any]] = []
        doc_index_to_orig_index: List[int] = []
        errors: List[BatchItemError] = []

        for idx, item_raw in enumerate(batch_in.logs):
            try:
                if isinstance(item_raw, dict):
                    item = LogIngestRequest.model_validate(item_raw)
                elif isinstance(item_raw, LogIngestRequest):
                    item = item_raw
                else:
                    raise ValueError(f"Expected JSON object for log item, got {type(item_raw).__name__}")

                parsed = LogParser.parse(
                    raw_log=item.raw_log,
                    explicit_message=item.message,
                    explicit_service=item.service_name,
                    explicit_env=item.environment,
                    explicit_level=item.level,
                    explicit_timestamp=item.timestamp,
                    explicit_metadata=item.metadata,
                    explicit_request_id=item.request_id,
                    explicit_trace_id=item.trace_id,
                    explicit_host=item.host,
                    explicit_source=item.source,
                )
                normalized_msg = LogNormalizer.normalize(parsed.message)

                is_error_or_crit = parsed.level in [LogLevel.ERROR, LogLevel.CRITICAL]
                error_sig = None
                if is_error_or_crit:
                    error_sig = ErrorSignatureGenerator.generate(
                        service_name=parsed.service_name,
                        environment=parsed.environment,
                        normalized_message=normalized_msg
                    )

                doc = {
                    "_id": ObjectId(),
                    "user_id": user.id,
                    "service_name": parsed.service_name,
                    "environment": parsed.environment,
                    "level": parsed.level.value,
                    "message": parsed.message,
                    "normalized_message": normalized_msg,
                    "error_signature": error_sig,
                    "detection_status": "PENDING" if is_error_or_crit else "SKIPPED",
                    "incident_id": None,
                    "timestamp": parsed.timestamp,
                    "ingested_at": now,
                    "source": parsed.source,
                    "host": parsed.host,
                    "request_id": parsed.request_id,
                    "trace_id": parsed.trace_id,
                    "metadata": parsed.metadata,
                    "raw_log": parsed.raw_log,
                }
                docs_to_insert.append(doc)
                doc_index_to_orig_index.append(idx)
            except Exception as exc:
                snippet = None
                if isinstance(item_raw, dict):
                    snippet = str(item_raw.get("raw_log") or item_raw.get("message") or "")[:100]
                elif isinstance(item_raw, str):
                    snippet = item_raw[:100]

                err_msg = str(exc)
                if "Value error," in err_msg:
                    err_msg = err_msg.split("Value error,")[-1].strip()

                errors.append(
                    BatchItemError(
                        index=idx,
                        reason=f"Validation/Parsing failed: {err_msg}",
                        raw_snippet=snippet if snippet else None
                    )
                )

        inserted_ids: List[str] = []
        failed_doc_indices = set()
        if docs_to_insert:
            try:
                result = await db["logs"].insert_many(docs_to_insert, ordered=False)
                inserted_ids = [str(_id) for _id in result.inserted_ids]
            except BulkWriteError as bwe:
                logger.warning(
                    f"BulkWriteError during batch ingestion: {bwe.details.get('nInserted', 0)} inserted, "
                    f"{len(bwe.details.get('writeErrors', []))} write errors."
                )
                write_errors = bwe.details.get("writeErrors", [])

                for we in write_errors:
                    doc_idx = we.get("index")
                    failed_doc_indices.add(doc_idx)

                    orig_idx = (
                        doc_index_to_orig_index[doc_idx]
                        if doc_idx is not None and doc_idx < len(doc_index_to_orig_index)
                        else (doc_idx if doc_idx is not None else -1)
                    )

                    snippet = None
                    if 0 <= orig_idx < len(batch_in.logs):
                        raw_item = batch_in.logs[orig_idx]
                        if isinstance(raw_item, dict):
                            snippet = str(raw_item.get("raw_log") or raw_item.get("message") or "")[:100]
                        elif isinstance(raw_item, str):
                            snippet = raw_item[:100]

                    errmsg = we.get("errmsg", "Database write error")
                    errors.append(
                        BatchItemError(
                            index=orig_idx,
                            reason=f"Database insertion failed: {errmsg}",
                            raw_snippet=snippet if snippet else None
                        )
                    )

                # Collect inserted_ids for the documents that succeeded
                for doc_idx, doc in enumerate(docs_to_insert):
                    if doc_idx not in failed_doc_indices:
                        inserted_ids.append(str(doc["_id"]))

            except Exception as exc:
                logger.error(f"MongoDB batch insertion unexpected error: {exc}")
                raise AppException(
                    message="Failed to persist log batch to database.",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Trigger Incident Detection for all successfully persisted error/critical logs
        for doc_idx, doc in enumerate(docs_to_insert):
            if doc_idx not in failed_doc_indices and doc.get("detection_status") == "PENDING":
                try:
                    await IncidentDetectionService.process_log_for_detection(
                        db=db,
                        user_id=user.id,
                        log_id=doc["_id"]
                    )
                except Exception as exc:
                    logger.error(f"Incident detection non-fatal error on batch log {doc['_id']}: {exc}")

        # Ensure all reported errors are sorted by original input index
        errors.sort(key=lambda e: e.index)

        logger.info(
            f"Batch ingestion complete: {len(inserted_ids)} succeeded, "
            f"{len(errors)} failed out of {total} records."
        )

        return BatchLogIngestResponse(
            total_received=total,
            successful_count=len(inserted_ids),
            failed_count=len(errors),
            inserted_ids=inserted_ids,
            errors=errors
        )

    @classmethod
    async def get_logs(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedLogResponse:
        """
        Retrieves logs with filtering, sorting, pagination, and multi-tenant authorization.
        """
        query: Dict[str, Any] = {}

        # Tenancy policy: Non-admins strictly only see their own logs
        if user.role != UserRole.ADMIN:
            query["user_id"] = user.id

        if service_name:
            query["service_name"] = service_name
        if environment:
            query["environment"] = environment
        if level:
            parsed_lvl = LogLevel.from_string(level)
            query["level"] = parsed_lvl.value

        if start_time or end_time:
            query["timestamp"] = {}
            if start_time:
                query["timestamp"]["$gte"] = start_time
            if end_time:
                query["timestamp"]["$lte"] = end_time

        total = await db["logs"].count_documents(query)

        cursor = db["logs"].find(query).sort("timestamp", -1).skip(offset).limit(limit)
        docs = await cursor.to_list(length=limit)

        items = []
        items = []
        for d in docs:
            d["id"] = str(d["_id"])
            items.append(LogResponse.model_validate(d))

        return PaginatedLogResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset
        )

    @classmethod
    async def get_log_by_id(
        cls,
        db: AsyncDatabase,
        user: UserInDB,
        log_id: str
    ) -> LogResponse:
        """
        Retrieves a single log document by ID with authorization checks.
        """
        if not ObjectId.is_valid(log_id):
            raise ResourceNotFoundError(f"Log with ID '{log_id}' not found.")

        doc = await db["logs"].find_one({"_id": ObjectId(log_id)})
        if not doc:
            raise ResourceNotFoundError(f"Log with ID '{log_id}' not found.")

        # Tenancy check: Non-admins cannot view another user's log
        if user.role != UserRole.ADMIN and doc.get("user_id") != user.id:
            # Return 404 to avoid leaking existence of other tenants' records
            raise ResourceNotFoundError(f"Log with ID '{log_id}' not found.")

        doc["id"] = str(doc["_id"])
        return LogResponse.model_validate(doc)
