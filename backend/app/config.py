from functools import lru_cache
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings managed via Pydantic BaseSettings.
    Loads environment variables from .env file or host environment.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Application Metadata
    APP_NAME: str = "OpsSage AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Cross-Origin Resource Sharing (CORS)
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:3000",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Database: MongoDB Atlas
    MONGODB_URI: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URI (Atlas SRV or local instance)"
    )
    MONGODB_DB_NAME: str = "opssage_ai"
    MONGODB_MAX_POOL_SIZE: int = 10
    MONGODB_MIN_POOL_SIZE: int = 0
    MONGODB_TIMEOUT_MS: int = 5000

    # Security & JWT Authentication
    SECRET_KEY: str = Field(
        default="change-this-insecure-key-for-production-min-32-chars",
        description="Secret key for signing JWT tokens"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 60 minutes (1 hour) for operational security

    # LLM Provider Configuration
    LLM_PROVIDER: str = Field(
        default="gemini",
        description="Primary LLM provider ('gemini' or 'openai')"
    )
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Vector Search & Embeddings
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    ATLAS_VECTOR_INDEX_NAME: str = "vector_index_knowledge_base"

    # Ingestion Configuration
    MAX_LOG_BATCH_SIZE: int = 500

    # Incident Detection Configuration (Module 3)
    INCIDENT_DETECTION_WINDOW_SECONDS: int = 300
    INCIDENT_MIN_EVENTS_THRESHOLD: int = 3
    INCIDENT_MEDIUM_EVENT_THRESHOLD: int = 5
    INCIDENT_HIGH_EVENT_THRESHOLD: int = 8
    INCIDENT_CRITICAL_EVENT_THRESHOLD: int = 15
    INCIDENT_PROCESSING_LEASE_SECONDS: int = 30


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance to avoid repeated file reads and re-parsing.
    """
    return Settings()
