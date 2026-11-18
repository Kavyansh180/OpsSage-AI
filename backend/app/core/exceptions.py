from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from backend.app.core.logging import get_logger

logger = get_logger("exceptions")


class AppException(Exception):
    """Base application exception."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class DatabaseConnectionError(AppException):
    """Raised when MongoDB connection fails or times out."""
    def __init__(self, message: str = "Database connection unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details)


class ResourceNotFoundError(AppException):
    """Raised when a requested resource is not found."""
    def __init__(self, message: str = "Requested resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class AuthenticationError(AppException):
    """Raised for authentication failures."""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED, details=details)


class AuthorizationError(AppException):
    """Raised for unauthorized access attempts."""
    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN, details=details)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Global handler for domain-specific AppExceptions."""
    logger.error(
        f"Domain exception on {request.method} {request.url.path}: {exc.message} (status: {exc.status_code})",
        extra={"details": exc.details}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details
        }
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions."""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "InternalServerError",
            "message": "An unexpected internal server error occurred.",
            "details": {}
        }
    )
