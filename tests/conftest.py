import pytest
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from backend.app.db.mongodb import MongoDBManager
from backend.app.main import app


@pytest.fixture(autouse=True)
async def initialize_test_database():
    """
    Ensures MongoDB connection is initialized during test execution.
    """
    await MongoDBManager.connect()
    yield


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client for testing FastAPI endpoints.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
