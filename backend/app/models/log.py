from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class LogLevel(str, Enum):
    """
    Standardized log severity levels.
    """
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, level_str: Optional[str]) -> "LogLevel":
        """
        Parses common string representations of log severity into LogLevel enum.
        """
        if not level_str:
            return cls.UNKNOWN

        clean_level = level_str.strip().upper()
        mapping = {
            "DEBUG": cls.DEBUG,
            "INFO": cls.INFO,
            "WARN": cls.WARNING,
            "WARNING": cls.WARNING,
            "ERR": cls.ERROR,
            "ERROR": cls.ERROR,
            "CRIT": cls.CRITICAL,
            "CRITICAL": cls.CRITICAL,
            "FATAL": cls.CRITICAL,
            "EMERGENCY": cls.CRITICAL,
        }
        return mapping.get(clean_level, cls.UNKNOWN)


class LogInDB(BaseModel):
    """
    Internal model representing a structured log document stored in MongoDB.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: str = Field(alias="_id")
    user_id: str
    service_name: str
    environment: str = "production"
    level: LogLevel = LogLevel.INFO
    message: str
    normalized_message: str
    timestamp: datetime
    ingested_at: datetime
    source: Optional[str] = None
    host: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_log: Optional[str] = None
