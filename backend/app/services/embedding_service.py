import re
from typing import List, Optional
from backend.app.config import Settings, get_settings
from backend.app.core.exceptions import AppException
from backend.app.core.logging import get_logger

logger = get_logger("services.embedding")


class EmbeddingError(AppException):
    """Raised when text embedding generation fails."""
    def __init__(self, message: str = "Embedding generation failure", details: Optional[dict] = None):
        super().__init__(message=message, status_code=500, details=details)


class EmbeddingService:
    """
    Dedicated local text embedding engine using sentence-transformers/all-MiniLM-L6-v2.
    Produces 384-dimensional dense vectors with consistent preprocessing.
    Loads the model as a reusable singleton to prevent repeated disk I/O and initialization overhead.
    """

    _model_instance = None
    _model_name: Optional[str] = None
    _is_mock: bool = False

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._expected_dim = self._settings.EMBEDDING_DIMENSION
        self._target_model_name = self._settings.EMBEDDING_MODEL_NAME

    @classmethod
    def get_model(cls, model_name: str):
        """
        Retrieves or lazily initializes the shared SentenceTransformer model instance.
        Thread-safe in standard CPython GIL operations.
        """
        if cls._is_mock and cls._model_instance is not None:
            return cls._model_instance

        if cls._model_instance is None or cls._model_name != model_name:
            logger.info(f"Loading local embedding model: '{model_name}'...")
            try:
                from sentence_transformers import SentenceTransformer
                cls._model_instance = SentenceTransformer(model_name)
                cls._model_name = model_name
                cls._is_mock = False
                logger.info(f"Embedding model '{model_name}' loaded successfully.")
            except Exception as exc:
                logger.error(f"Failed to initialize embedding model '{model_name}': {exc}")
                raise EmbeddingError(
                    f"Could not load embedding model '{model_name}': {str(exc)}",
                    details={"model_name": model_name},
                ) from exc
        return cls._model_instance

    @classmethod
    def set_mock_model(cls, mock_model, model_name: str = "mock-model"):
        """
        Allows test suites to inject an in-memory mock model to avoid heavy model downloads.
        """
        cls._model_instance = mock_model
        cls._model_name = model_name
        cls._is_mock = True

    @classmethod
    def reset_model(cls):
        """Resets the singleton model instance."""
        cls._model_instance = None
        cls._model_name = None
        cls._is_mock = False

    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        Applies consistent text normalization for both indexing and query retrieval.
        Strips whitespace, normalizes excessive newlines/spaces, and truncates extreme lengths.
        """
        if not text or not text.strip():
            raise ValueError("Input text for embedding generation cannot be empty.")

        cleaned = text.strip()
        # Collapse multi-newlines and multi-spaces
        cleaned = re.sub(r"\r\n|\r|\n", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Truncate to maximum characters (sentence-transformers models typically have 256-512 token limits)
        MAX_CHARS = 8000
        if len(cleaned) > MAX_CHARS:
            cleaned = cleaned[:MAX_CHARS]

        return cleaned

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a 384-dimensional dense vector embedding for a single text string.
        """
        clean_text = self.preprocess_text(text)
        model = self.get_model(self._target_model_name)

        try:
            vector = model.encode(
                clean_text,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            # Convert numpy array to standard Python list of floats
            if hasattr(vector, "tolist"):
                vector_list = vector.tolist()
            else:
                vector_list = list(vector)

            vector_floats = [float(x) for x in vector_list]

            if len(vector_floats) != self._expected_dim:
                raise EmbeddingError(
                    f"Embedding dimension mismatch: expected {self._expected_dim}, got {len(vector_floats)}"
                )

            return vector_floats

        except Exception as exc:
            if isinstance(exc, (EmbeddingError, ValueError)):
                raise
            logger.exception("Error during single embedding generation")
            raise EmbeddingError(f"Embedding generation failed: {str(exc)}") from exc

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates 384-dimensional dense vector embeddings for a batch of text strings.
        """
        if not texts:
            return []

        clean_texts = [self.preprocess_text(t) for t in texts]
        model = self.get_model(self._target_model_name)

        try:
            vectors = model.encode(
                clean_texts,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            result: List[List[float]] = []
            for vec in vectors:
                if hasattr(vec, "tolist"):
                    v_list = vec.tolist()
                else:
                    v_list = list(vec)
                v_floats = [float(x) for x in v_list]

                if len(v_floats) != self._expected_dim:
                    raise EmbeddingError(
                        f"Embedding dimension mismatch: expected {self._expected_dim}, got {len(v_floats)}"
                    )
                result.append(v_floats)

            return result

        except Exception as exc:
            if isinstance(exc, (EmbeddingError, ValueError)):
                raise
            logger.exception("Error during batch embedding generation")
            raise EmbeddingError(f"Batch embedding generation failed: {str(exc)}") from exc
