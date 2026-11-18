import logging
import sys
from typing import Optional
from backend.app.config import get_settings


class Formatter(logging.Formatter):
    """Custom formatter with clean timestamp and context."""
    def format(self, record: logging.LogRecord) -> str:
        return super().format(record)


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Configures application-wide structured logging.
    """
    settings = get_settings()
    level_name = log_level or ("DEBUG" if settings.DEBUG else "INFO")
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)

    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger with UTF-8 stream output to prevent charmap errors on Windows
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt=date_format,
        handlers=[handler],
        force=True
    )

    # Set specific third-party logger noise levels
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("pymongo").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance for a given module.
    """
    return logging.getLogger(f"opssage.{name}")
