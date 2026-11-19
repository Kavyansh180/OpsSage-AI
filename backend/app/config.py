from functools import lru_cache
from typing import Any, List, Union
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
        "https://*.streamlit.app",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return []

    @field_validator("MONGODB_URI", "SECRET_KEY", "GEMINI_API_KEY", mode="before")
    @classmethod
    def resolve_ssm_if_needed(cls, v: Any) -> Any:
        """
        Dynamically resolves SSM parameter references (e.g. 'ssm:/opssage/prod/MONGODB_URI')
        when running in AWS environments with IAM permissions.
        Ensures secrets are not exposed in CloudFormation templates or console environment variables.
        """
        if isinstance(v, str) and (v.startswith("ssm:/") or v.startswith("/opssage/")):
            param_name = v.replace("ssm:", "").strip()
            try:
                import boto3
                ssm = boto3.client("ssm")
                resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
                return resp["Parameter"]["Value"]
            except Exception:
                return v
        return v

    # Database: MongoDB Atlas
    MONGODB_URI: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URI (Atlas SRV or local instance)"
    )
    MONGODB_DB_NAME: str = "opssage_ai"
    MONGODB_MAX_POOL_SIZE: int = 10
    MONGODB_MIN_POOL_SIZE: int = 0
    MONGODB_TIMEOUT_MS: int = 5000
    INITIALIZE_INDEXES_ON_STARTUP: bool = True

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
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: int = 25
    RCA_MAX_EVIDENCE_LOGS: int = 30

    # Vector Search & Embeddings (Module 5)
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    ATLAS_VECTOR_INDEX_NAME: str = "vector_index_knowledge_base"
    RAG_TOP_K: int = 3
    RAG_MIN_SIMILARITY: float = 0.65
    RAG_NUM_CANDIDATES: int = 50
    RAG_ENABLED: bool = True

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
