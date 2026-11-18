from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.asynchronous.database import AsyncDatabase
from backend.app.core.logging import get_logger

logger = get_logger("db.indexes")


async def setup_database_indexes(db: AsyncDatabase) -> None:
    """
    Ensures all required standard indexes exist across MongoDB collections.
    Safe to run repeatedly; MongoDB creates only missing indexes.
    """
    logger.info("Initializing database indexes...")

    try:
        # 1. Users collection indexes
        users_collection = db["users"]
        await users_collection.create_indexes([
            IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email_unique"),
            IndexModel([("is_active", ASCENDING)], name="idx_users_is_active"),
        ])
        logger.info("Indexes initialized for 'users' collection.")

        # 2. Logs collection indexes
        logs_collection = db["logs"]
        await logs_collection.create_indexes([
            IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_logs_user_timestamp"),
            IndexModel([("service_name", ASCENDING), ("timestamp", DESCENDING)], name="idx_logs_service_timestamp"),
            IndexModel([("level", ASCENDING), ("timestamp", DESCENDING)], name="idx_logs_level_timestamp"),
            IndexModel([("request_id", ASCENDING)], name="idx_logs_request_id", sparse=True),
            IndexModel([("trace_id", ASCENDING)], name="idx_logs_trace_id", sparse=True),
            # Module 3: Fast sliding-window count and idempotency indexes
            IndexModel([
                ("user_id", ASCENDING),
                ("environment", ASCENDING),
                ("service_name", ASCENDING),
                ("error_signature", ASCENDING),
                ("timestamp", DESCENDING)
            ], name="idx_logs_detection_window"),
            IndexModel([
                ("detection_status", ASCENDING),
                ("detection_lease_until", ASCENDING)
            ], name="idx_logs_detection_lease", sparse=True),
        ])
        logger.info("Indexes initialized for 'logs' collection.")

        # 3. Incidents collection indexes (Module 3)
        incidents_collection = db["incidents"]
        await incidents_collection.create_indexes([
            IndexModel([("incident_id", ASCENDING)], unique=True, name="idx_incidents_id_unique"),
            # Active incident uniqueness: at most 1 OPEN or ACKNOWLEDGED incident per (user, env, service, sig)
            IndexModel(
                [
                    ("user_id", ASCENDING),
                    ("environment", ASCENDING),
                    ("service_name", ASCENDING),
                    ("error_signature", ASCENDING)
                ],
                unique=True,
                partialFilterExpression={"status": {"$in": ["OPEN", "ACKNOWLEDGED"]}},
                name="idx_incidents_active_unique"
            ),
            IndexModel(
                [("user_id", ASCENDING), ("environment", ASCENDING), ("status", ASCENDING), ("severity", ASCENDING)],
                name="idx_incidents_user_env_status_severity"
            ),
            IndexModel([("user_id", ASCENDING), ("last_seen", DESCENDING)], name="idx_incidents_user_last_seen"),
        ])
        logger.info("Indexes initialized for 'incidents' collection.")

        # 4. Knowledge Base collection indexes (standard filters)
        kb_collection = db["knowledge_base"]
        await kb_collection.create_indexes([
            IndexModel([("service_name", ASCENDING)], name="idx_kb_service_name"),
            IndexModel([("incident_ref_id", ASCENDING)], name="idx_kb_incident_ref_id"),
        ])
        logger.info("Indexes initialized for 'knowledge_base' collection.")

    except Exception as exc:
        logger.error(f"Error establishing database indexes: {exc}")
