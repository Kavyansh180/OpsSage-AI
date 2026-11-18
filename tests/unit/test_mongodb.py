import pytest
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from backend.app.db.mongodb import MongoDBManager


@pytest.mark.asyncio
async def test_mongodb_manager_client_initialization():
    """
    Verify that MongoDBManager connects using native AsyncMongoClient
    and returns proper AsyncDatabase instances.
    """
    # Ensure clean state
    await MongoDBManager.close()

    # Trigger connection attempt
    await MongoDBManager.connect()

    # The client must be an instance of native AsyncMongoClient
    client = MongoDBManager.get_client()
    assert isinstance(client, AsyncMongoClient)

    # The database must be an instance of native AsyncDatabase
    db = MongoDBManager.get_database()
    assert isinstance(db, AsyncDatabase)

    # Ping returns a boolean (True or False depending on local daemon)
    is_alive = await MongoDBManager.ping()
    assert isinstance(is_alive, bool)

    # Cleanup and restore
    await MongoDBManager.close()
    assert MongoDBManager._client is None
    assert MongoDBManager._db is None
    await MongoDBManager.connect()
