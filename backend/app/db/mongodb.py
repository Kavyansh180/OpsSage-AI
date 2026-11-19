import asyncio
from typing import Optional
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
from backend.app.config import get_settings
from backend.app.core.logging import get_logger

logger = get_logger("db.mongodb")


def _mask_uri(uri: str) -> str:
    """Masks credentials in MongoDB connection string for safe logging."""
    if "@" in uri:
        try:
            prefix, suffix = uri.split("@", 1)
            scheme = prefix.split("://")[0]
            return f"{scheme}://****:****@{suffix}"
        except Exception:
            return "mongodb+srv://****:****@<cluster>"
    return uri


class MongoDBManager:
    """
    Manages the lifecycle of asynchronous MongoDB connection pools using PyMongo's
    native AsyncMongoClient. Maintains a single client per application event loop.
    Supports warm-invocation client reuse and conservative pool sizing for AWS Lambda.
    """
    _client: Optional[AsyncMongoClient] = None
    _db: Optional[AsyncDatabase] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    async def connect(cls) -> None:
        """
        Initializes a single AsyncMongoClient and establishes connection pool.
        Executes an asynchronous ping command with timeout to verify connectivity.
        """
        settings = get_settings()
        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = asyncio.get_event_loop()

        if cls._client is not None:
            if cls._loop == current_loop:
                logger.debug("AsyncMongoClient already initialized for current event loop.")
                return
            else:
                logger.debug("New event loop detected. Re-initializing AsyncMongoClient for current loop.")
                try:
                    # Close previous client if bound to defunct loop
                    await cls._client.close()
                except Exception:
                    pass
                cls._client = None
                cls._db = None

        cls._loop = current_loop
        logger.info(f"Connecting to MongoDB database '{settings.MONGODB_DB_NAME}' via PyMongo AsyncMongoClient...")
        try:
            cls._client = AsyncMongoClient(
                settings.MONGODB_URI,
                maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
                minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
                serverSelectionTimeoutMS=settings.MONGODB_TIMEOUT_MS,
                connectTimeoutMS=settings.MONGODB_TIMEOUT_MS,
                maxIdleTimeMS=30000,  # Auto-close idle sockets after 30s for serverless efficiency
                appname=settings.APP_NAME
            )
            cls._db = cls._client[settings.MONGODB_DB_NAME]

            # Verify connection asynchronously with ping command
            await cls._client.admin.command("ping")
            logger.info("Successfully connected to MongoDB and verified with ping.")
        except (ConnectionFailure, ServerSelectionTimeoutError, OperationFailure) as exc:
            logger.warning(
                f"Failed to connect to MongoDB at {_mask_uri(settings.MONGODB_URI)}: {exc}. "
                "The application will start, but database-dependent features will report unready."
            )
        except Exception as exc:
            logger.error(f"Unexpected error initializing MongoDB connection: {exc}")

    @classmethod
    async def ensure_database(cls) -> AsyncDatabase:
        """
        Ensures AsyncMongoClient is connected and valid for the active event loop.
        Reuses existing connection pool across warm Lambda invocations.
        """
        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if cls._client is None or cls._loop != current_loop:
            await cls.connect()

        if cls._db is None and cls._client is not None:
            settings = get_settings()
            cls._db = cls._client[settings.MONGODB_DB_NAME]

        if cls._db is None:
            raise RuntimeError("Database connection could not be established.")
        return cls._db

    @classmethod
    async def close(cls) -> None:
        """
        Gracefully closes all connection pool sockets asynchronously.
        """
        if cls._client is not None:
            current_loop = None
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if cls._loop == current_loop:
                logger.info("Closing AsyncMongoClient connection pool...")
                try:
                    await cls._client.close()
                except Exception as exc:
                    logger.debug(f"Error during client close: {exc}")
            cls._client = None
            cls._db = None
            cls._loop = None
            logger.info("AsyncMongoClient connection pool closed.")

    @classmethod
    async def ping(cls) -> bool:
        """
        Checks current database connection liveness.
        Returns True if database responds to ping within timeout, else False.
        """
        if cls._client is None:
            return False
        try:
            await cls._client.admin.command("ping")
            return True
        except Exception as exc:
            logger.debug(f"MongoDB ping failed: {exc}")
            return False

    @classmethod
    def get_database(cls) -> AsyncDatabase:
        """
        Returns the active PyMongo AsyncDatabase instance.
        """
        if cls._db is None:
            settings = get_settings()
            if cls._client is not None:
                cls._db = cls._client[settings.MONGODB_DB_NAME]
                return cls._db
            raise RuntimeError("Database connection has not been initialized. Call connect() first.")
        return cls._db

    @classmethod
    def get_client(cls) -> AsyncMongoClient:
        """
        Returns the active PyMongo AsyncMongoClient instance.
        """
        if cls._client is None:
            raise RuntimeError("AsyncMongoClient has not been initialized. Call connect() first.")
        return cls._client


# FastAPI dependency to inject database instance
async def get_database() -> AsyncDatabase:
    """
    FastAPI dependency that returns the AsyncDatabase instance for endpoint injection.
    Ensures safe connection across warm Lambda invocations and standard ASGI servers.
    """
    return await MongoDBManager.ensure_database()
