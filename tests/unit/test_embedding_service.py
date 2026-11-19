from unittest.mock import MagicMock
import numpy as np
import pytest

from backend.app.config import Settings
from backend.app.services.embedding_service import EmbeddingError, EmbeddingService


class DummyEncoder:
    """Mock model that returns deterministic 384-dimensional unit vectors."""
    def encode(self, texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False):
        if isinstance(texts, str):
            # Deterministic 384d vector
            val = float(len(texts)) / 1000.0
            vec = np.zeros(384, dtype=np.float32)
            vec[0] = 1.0
            vec[1] = val
            return vec
        else:
            vectors = []
            for t in texts:
                val = float(len(t)) / 1000.0
                vec = np.zeros(384, dtype=np.float32)
                vec[0] = 1.0
                vec[1] = val
                vectors.append(vec)
            return vectors


@pytest.fixture(autouse=True)
def setup_mock_embedding():
    dummy = DummyEncoder()
    EmbeddingService.set_mock_model(dummy, model_name="mock-minilm")
    yield
    EmbeddingService.reset_model()


def test_preprocess_text_collapses_whitespace():
    raw = "  Database   connection \n\n timeout  on \r\n port 5432.   "
    clean = EmbeddingService.preprocess_text(raw)
    assert clean == "Database connection timeout on port 5432."


def test_preprocess_text_empty_raises_value_error():
    with pytest.raises(ValueError):
        EmbeddingService.preprocess_text("")

    with pytest.raises(ValueError):
        EmbeddingService.preprocess_text("   \n\t  ")


def test_generate_embedding_returns_384_dimensions():
    service = EmbeddingService(Settings(EMBEDDING_DIMENSION=384))
    vector = service.generate_embedding("PostgreSQL operational error connection refused")
    assert isinstance(vector, list)
    assert len(vector) == 384
    assert all(isinstance(x, float) for x in vector)


def test_generate_embeddings_batch():
    service = EmbeddingService(Settings(EMBEDDING_DIMENSION=384))
    texts = [
        "First incident error: connection timeout",
        "Second incident error: memory limit exceeded",
        "Third incident error: disk space full",
    ]
    vectors = service.generate_embeddings(texts)
    assert len(vectors) == 3
    for vec in vectors:
        assert len(vec) == 384
        assert isinstance(vec, list)


def test_generate_embeddings_empty_batch():
    service = EmbeddingService()
    assert service.generate_embeddings([]) == []


def test_dimension_mismatch_raises_error():
    bad_encoder = MagicMock()
    bad_encoder.encode.return_value = np.zeros(128, dtype=np.float32)  # 128 != 384
    EmbeddingService.set_mock_model(bad_encoder)

    service = EmbeddingService(Settings(EMBEDDING_DIMENSION=384))
    with pytest.raises(EmbeddingError) as exc_info:
        service.generate_embedding("Text")
    assert "Embedding dimension mismatch" in str(exc_info.value)
