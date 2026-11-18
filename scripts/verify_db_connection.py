"""
Verification script for MongoDB Atlas connectivity and index setup.
Usage:
    .venv\\Scripts\\python.exe scripts/verify_db_connection.py
"""
import asyncio
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import get_settings
from backend.app.core.logging import get_logger, setup_logging
from backend.app.db.indexes import setup_database_indexes
from backend.app.db.mongodb import MongoDBManager, _mask_uri

logger = get_logger("scripts.verify_db")


async def main() -> int:
    setup_logging()
    settings = get_settings()

    logger.info("==================================================")
    logger.info("OpsSage AI - MongoDB Atlas Live Verification")
    logger.info("==================================================")
    logger.info(f"Target Database: {settings.MONGODB_DB_NAME}")
    logger.info(f"Connection Pool: maxPoolSize={settings.MONGODB_MAX_POOL_SIZE}, minPoolSize={settings.MONGODB_MIN_POOL_SIZE}")
    logger.info(f"Connecting to: {_mask_uri(settings.MONGODB_URI)}")

    # Check for unpopulated template placeholder
    if "<db_password>" in settings.MONGODB_URI or "<password>" in settings.MONGODB_URI:
        logger.error("[CONFIGURATION REQUIRED] Detected placeholder '<db_password>' in MONGODB_URI in your .env file.")
        logger.error("Please replace '<db_password>' with the actual password for database user in .env and rerun.")
        return 1

    await MongoDBManager.connect()

    client = MongoDBManager.get_client()
    try:
        # Step 1: Explicit Admin Ping Command
        logger.info("Executing explicit admin ping command...")
        ping_result = await client.admin.command("ping")
        logger.info(f"[SUCCESS] Admin ping response from cluster: {ping_result}")
    except Exception as exc:
        logger.error(f"[FAILED] MongoDB ping command failed: {exc}")
        logger.info("Tips for MongoDB Atlas:")
        logger.info("1. Ensure Network Access in MongoDB Atlas has your IP (or 0.0.0.0/0 for dev) whitelisted.")
        logger.info("2. Ensure Database User credentials and permissions are correct in Atlas.")
        logger.info("3. Check that the password does not contain unescaped special characters (e.g. '@' or ':').")
        await MongoDBManager.close()
        return 1

    # Step 2: Database and Index Initialization
    db = MongoDBManager.get_database()
    logger.info(f"Initializing collection indexes on database '{settings.MONGODB_DB_NAME}'...")
    await setup_database_indexes(db)

    # Step 3: List collections and verify indexes
    collections = await db.list_collection_names()
    logger.info(f"Collections present in '{settings.MONGODB_DB_NAME}': {collections}")

    for coll_name in ["users", "logs", "incidents", "knowledge_base"]:
        if coll_name in collections:
            indexes = await db[coll_name].index_information()
            logger.info(f"  -> Collection '{coll_name}' indexes ({len(indexes)}):")
            for idx_name, idx_info in indexes.items():
                logger.info(f"       * {idx_name}: key={idx_info.get('key')}, unique={idx_info.get('unique', False)}")
        else:
            logger.info(f"  -> Collection '{coll_name}': created on first write.")

    await MongoDBManager.close()
    logger.info("==================================================")
    logger.info("[SUCCESS] MongoDB Atlas live verification complete!")
    logger.info("==================================================")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
