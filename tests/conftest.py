import pytest
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from backend.app.db.mongodb import MongoDBManager
from backend.app.main import app
from backend.app.services.embedding_service import EmbeddingService


class GlobalDummyEncoder:
    """Default in-memory dummy encoder providing instant 384-dimensional vectors for tests."""
    def encode(self, texts, **kwargs):
        if isinstance(texts, str):
            return [1.0] + [0.0] * 383
        return [[1.0] + [0.0] * 383 for _ in texts]


@pytest.fixture(autouse=True)
def mock_default_embedding():
    EmbeddingService.set_mock_model(GlobalDummyEncoder())
    yield
    EmbeddingService.reset_model()


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
