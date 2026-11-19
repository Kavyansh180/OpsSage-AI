from typing import Any, Dict, Optional
from fastapi import status
from backend.app.core.exceptions import AppException


class LLMError(AppException):
    """Base exception for errors communicating with or receiving responses from LLMs."""
    def __init__(
        self,
        message: str = "LLM provider failure",
        status_code: int = status.HTTP_502_BAD_GATEWAY,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message=message, status_code=status_code, details=details)


class LLMTimeoutError(LLMError):
    """Raised when the LLM provider call exceeds the configured timeout."""
    def __init__(
        self,
        message: str = "LLM provider request timed out",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details=details,
        )


class LLMRateLimitError(LLMError):
    """Raised when the LLM provider returns a 429 rate limit or quota exceeded error."""
    def __init__(
        self,
        message: str = "LLM provider rate limit exceeded. Please retry later.",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class LLMConfigurationError(LLMError):
    """Raised when LLM provider is misconfigured (e.g., missing API key or unknown provider)."""
    def __init__(
        self,
        message: str = "LLM provider is not properly configured",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class LLMResponseParsingError(LLMError):
    """Raised when the LLM response cannot be parsed into the expected JSON or schema."""
    def __init__(
        self,
        message: str = "Failed to parse structured response from LLM",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )
