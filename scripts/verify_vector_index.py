"""
Diagnostic utility to check the status of MongoDB Atlas Vector Search index.
"""
import asyncio
from pathlib import Path
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import get_settings
from backend.app.db.mongodb import MongoDBManager


async def main():
    settings = get_settings()
    print("=" * 60)
    print("OpsSage AI — MongoDB Atlas Vector Search Verifier")
    print("=" * 60)

    await MongoDBManager.connect()
    db = MongoDBManager.get_database()

    target_index = settings.ATLAS_VECTOR_INDEX_NAME
    print(f"Target Vector Index Name: {target_index}")
    print(f"Collection: knowledge_base")

    try:
        kb_col = db["knowledge_base"]
        # In native async PyMongo 4.x, list_search_indexes() is an async coroutine
        cursor = await kb_col.list_search_indexes()
        indexes = await cursor.to_list(length=20)

        found = False
        for idx in indexes:
            name = idx.get("name")
            status = idx.get("status")
            queryable = idx.get("queryable")
            definition = idx.get("latestDefinition", {})
            print(f"- Found Index: '{name}', Status: {status}, Queryable: {queryable}")
            if name == target_index:
                found = True
                print(f"[SUCCESS] Vector Search index '{target_index}' is present and configured!")
                print(f"  Type: {idx.get('type')}")
                print(f"  Queryable: {queryable}")
                print(f"  Fields: {definition.get('fields', [])}")

        if not found:
            print(f"[WARNING] Vector Search index '{target_index}' was not found in knowledge_base collection.")
            print("Please see docs/ATLAS_VECTOR_SEARCH_SETUP.md to configure it in Atlas UI.")

    except Exception as exc:
        print(f"[ERROR] list_search_indexes failed: {exc}")
        print("Note: Atlas Search indexes require an active MongoDB Atlas cluster.")

    await MongoDBManager.close()


if __name__ == "__main__":
    asyncio.run(main())
