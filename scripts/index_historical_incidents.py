"""
Standalone CLI script to index historical incidents into MongoDB Atlas Knowledge Base.
Usage:
    python -m scripts.index_historical_incidents [--limit 100] [--force]
"""
import argparse
import asyncio
import sys
from backend.app.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.db.mongodb import MongoDBManager
from backend.app.models.user import UserInDB, UserRole
from backend.app.services.knowledge_indexer import KnowledgeIndexer

logger = get_logger("scripts.index_historical_incidents")


async def main():
    parser = argparse.ArgumentParser(description="Index historical incidents into OpsSage AI Knowledge Base.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of incidents to index.")
    parser.add_argument("--force", action="store_true", help="Force reindexing even if already indexed.")
    parser.add_argument("--service", type=str, default=None, help="Filter incidents by service name.")
    parser.add_argument("--environment", type=str, default=None, help="Filter incidents by environment.")
    args = parser.parse_args()

    settings = get_settings()
    print("=" * 60)
    print("OpsSage AI — Historical Incident Knowledge Base Indexer")
    print(f"Embedding Model: {settings.EMBEDDING_MODEL_NAME} ({settings.EMBEDDING_DIMENSION}d)")
    print(f"Atlas Vector Search Index: {settings.ATLAS_VECTOR_INDEX_NAME}")
    print("=" * 60)

    # 1. Connect to MongoDB
    print("\n[1/3] Connecting to MongoDB...")
    await MongoDBManager.connect()
    is_live = await MongoDBManager.ping()
    if not is_live:
        print("[ERROR] Could not connect to MongoDB database. Check your configuration.")
        sys.exit(1)
    print("[SUCCESS] MongoDB connection established.")

    db = MongoDBManager.get_database()

    # 2. Find an administrative user context
    print("\n[2/3] Resolving user context...")
    admin_doc = await db["users"].find_one({"role": UserRole.ADMIN.value})
    if not admin_doc:
        admin_doc = await db["users"].find_one({})

    if admin_doc:
        system_user = UserInDB.model_validate(admin_doc)
        print(f"[INFO] Running indexing as user: {system_user.email} (role: {system_user.role})")
    else:
        from datetime import datetime, timezone
        system_user = UserInDB(
            id="system-indexer",
            email="system@opssage.local",
            full_name="System Indexer",
            hashed_password="",
            role=UserRole.ADMIN,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        print("[INFO] Running indexing as virtual System Admin user.")

    # 3. Execute batch indexing
    print(f"\n[3/3] Scanning and indexing up to {args.limit} incidents (force_reindex={args.force})...")
    indexer = KnowledgeIndexer(db=db, settings=settings)

    response = await indexer.index_incidents_batch(
        user=system_user,
        limit=args.limit,
        service_name=args.service,
        environment=args.environment,
        force_reindex=args.force,
    )

    print("\n" + "=" * 60)
    print("INDEXING RESULTS:")
    print(f"- Total Eligible Incidents: {response.total_eligible}")
    print(f"- Successfully Indexed:    {response.indexed_count}")
    print(f"- Skipped (Already Done):  {response.skipped_count}")
    print(f"- Failed:                  {response.failed_count}")
    if response.errors:
        print(f"\nErrors encountered ({len(response.errors)}):")
        for err in response.errors[:5]:
            print(f"  * Incident {err['incident_id']}: {err['error']}")
    print("=" * 60)

    await MongoDBManager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
