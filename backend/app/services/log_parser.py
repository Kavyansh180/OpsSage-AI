import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from backend.app.core.logging import get_logger
from backend.app.models.log import LogLevel

logger = get_logger("services.log_parser")

# Regex patterns for standard unstructured logs
# 1. ISO/Standard: 2026-11-02 10:30:00 ERROR payment-service - Message OR ... [payment-service]: Message
STANDARD_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?:\[?(?P<level>[A-Za-z]+)\]?)\s+"
    r"(?:"
      r"\[(?P<service_bracket>[a-zA-Z0-9_\-\.]+)\]\s*(?:[:-]\s+)?"
      r"|"
      r"(?P<service>[a-zA-Z0-9_\-\.]+)\s*(?:[:-]\s+|\s+-\s+)"
    r")"
    r"(?P<message>.*)$",
    re.DOTALL
)

# 2. Simple format without service: 2026-11-02 10:30:00 ERROR Message
SIMPLE_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
    r"(?:\[?(?P<level>[A-Za-z]+)\]?)\s*"
    r"(?:[:-]\s+|\s+)"
    r"(?P<message>.*)$",
    re.DOTALL
)

COMMON_DATETIME_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S,%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
]


class ParsedLogResult:
    """
    Normalized result container produced by the LogParser.
    """
    def __init__(
        self,
        service_name: str,
        environment: str,
        level: LogLevel,
        message: str,
        timestamp: datetime,
        source: Optional[str] = None,
        host: Optional[str] = None,
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        raw_log: Optional[str] = None,
        is_timestamp_inferred: bool = False,
        original_timestamp_raw: Optional[str] = None,
    ):
        self.service_name = service_name
        self.environment = environment
        self.level = level
        self.message = message
        self.timestamp = timestamp
        self.source = source
        self.host = host
        self.request_id = request_id
        self.trace_id = trace_id
        self.metadata = metadata or {}
        self.raw_log = raw_log
        self.is_timestamp_inferred = is_timestamp_inferred
        self.original_timestamp_raw = original_timestamp_raw


class LogParser:
    """
    Deterministic log parser supporting JSON logs, standard structured log lines,
    and unstructured text with predictable fallback handling.
    """

    @classmethod
    def parse_timestamp(cls, ts_input: Any) -> Tuple[datetime, bool]:
        """
        Parses various timestamp representations into UTC-aware datetime.
        Returns (parsed_datetime, is_fallback).
        Guarantees that returned datetime is always timezone-aware in UTC.
        """
        if ts_input is None:
            return datetime.now(timezone.utc), True

        if isinstance(ts_input, datetime):
            if ts_input.tzinfo is None:
                return ts_input.replace(tzinfo=timezone.utc), False
            return ts_input.astimezone(timezone.utc), False

        if isinstance(ts_input, (int, float)):
            try:
                # Handle millisecond epoch vs second epoch
                epoch = ts_input / 1000.0 if ts_input > 1e11 else float(ts_input)
                return datetime.fromtimestamp(epoch, tz=timezone.utc), False
            except Exception:
                pass

        if isinstance(ts_input, str):
            ts_str = ts_input.strip()
            if not ts_str:
                return datetime.now(timezone.utc), True

            # Try Python ISO parser first
            try:
                clean_iso = ts_str[:-1] + "+00:00" if ts_str.endswith("Z") else ts_str
                parsed = datetime.fromisoformat(clean_iso)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc), False
            except Exception:
                pass

            # Try common format strings
            for fmt in COMMON_DATETIME_FORMATS:
                try:
                    parsed = datetime.strptime(ts_str, fmt)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed.astimezone(timezone.utc), False
                except ValueError:
                    continue

        # Intentional documented fallback: use ingestion time
        return datetime.now(timezone.utc), True

    @classmethod
    def parse(
        cls,
        raw_log: Optional[str] = None,
        explicit_message: Optional[str] = None,
        explicit_service: Optional[str] = None,
        explicit_env: Optional[str] = None,
        explicit_level: Optional[str] = None,
        explicit_timestamp: Optional[datetime] = None,
        explicit_metadata: Optional[Dict[str, Any]] = None,
        explicit_request_id: Optional[str] = None,
        explicit_trace_id: Optional[str] = None,
        explicit_host: Optional[str] = None,
        explicit_source: Optional[str] = None,
    ) -> ParsedLogResult:
        """
        Parses log data from raw string or explicit fields.
        Detects JSON vs Standard unstructured formats automatically.
        """
        raw_str = (raw_log or "").strip()
        metadata: Dict[str, Any] = (explicit_metadata or {}).copy()

        # 1. Check if raw_str is JSON
        if raw_str.startswith("{") and raw_str.endswith("}"):
            try:
                json_data = json.loads(raw_str)
                if isinstance(json_data, dict):
                    return cls._parse_json(
                        json_data=json_data,
                        raw_log=raw_str,
                        explicit_service=explicit_service,
                        explicit_env=explicit_env,
                        explicit_level=explicit_level,
                        explicit_metadata=metadata
                    )
            except (json.JSONDecodeError, TypeError):
                # Not valid JSON, continue to regex parser
                pass

        # 2. Check if raw_str matches standard application log regex
        if raw_str:
            std_match = STANDARD_LOG_PATTERN.match(raw_str)
            if std_match:
                groups = std_match.groupdict()
                raw_ts = groups["timestamp"]
                ts, is_fb = cls.parse_timestamp(raw_ts)
                metadata["timestamp_inferred"] = is_fb
                metadata["original_timestamp_raw"] = raw_ts

                level = LogLevel.from_string(explicit_level or groups["level"])
                service = explicit_service or groups.get("service") or groups.get("service_bracket") or "unknown-service"
                message = groups["message"].strip()

                return ParsedLogResult(
                    service_name=service,
                    environment=explicit_env or "production",
                    level=level,
                    message=message or raw_str,
                    timestamp=ts,
                    source=explicit_source,
                    host=explicit_host,
                    request_id=explicit_request_id,
                    trace_id=explicit_trace_id,
                    metadata=metadata,
                    raw_log=raw_str,
                    is_timestamp_inferred=is_fb,
                    original_timestamp_raw=raw_ts
                )

            # Simple log without service
            simple_match = SIMPLE_LOG_PATTERN.match(raw_str)
            if simple_match:
                groups = simple_match.groupdict()
                raw_ts = groups["timestamp"]
                ts, is_fb = cls.parse_timestamp(raw_ts)
                metadata["timestamp_inferred"] = is_fb
                metadata["original_timestamp_raw"] = raw_ts

                level = LogLevel.from_string(explicit_level or groups["level"])
                service = explicit_service or "unknown-service"
                message = groups["message"].strip()

                return ParsedLogResult(
                    service_name=service,
                    environment=explicit_env or "production",
                    level=level,
                    message=message or raw_str,
                    timestamp=ts,
                    source=explicit_source,
                    host=explicit_host,
                    request_id=explicit_request_id,
                    trace_id=explicit_trace_id,
                    metadata=metadata,
                    raw_log=raw_str,
                    is_timestamp_inferred=is_fb,
                    original_timestamp_raw=raw_ts
                )

        # 3. Explicit or unstructured fallback
        final_message = (explicit_message or raw_str).strip()
        if not final_message:
            raise ValueError("Log record contains an empty message.")

        ts, is_fb = cls.parse_timestamp(explicit_timestamp)
        metadata["timestamp_inferred"] = is_fb
        raw_ts_str = str(explicit_timestamp) if explicit_timestamp is not None else None
        if raw_ts_str:
            metadata["original_timestamp_raw"] = raw_ts_str

        level = LogLevel.from_string(explicit_level)
        service = explicit_service or "unknown-service"
        env = explicit_env or "production"

        if raw_str and not explicit_message:
            metadata["unrecognized_format"] = True

        # Avoid duplicate storage: only set raw_log if raw_str was provided
        stored_raw_log = raw_str if raw_str else None

        return ParsedLogResult(
            service_name=service,
            environment=env,
            level=level,
            message=final_message,
            timestamp=ts,
            source=explicit_source,
            host=explicit_host,
            request_id=explicit_request_id,
            trace_id=explicit_trace_id,
            metadata=metadata,
            raw_log=stored_raw_log,
            is_timestamp_inferred=is_fb,
            original_timestamp_raw=raw_ts_str
        )

    @classmethod
    def _parse_json(
        cls,
        json_data: Dict[str, Any],
        raw_log: str,
        explicit_service: Optional[str] = None,
        explicit_env: Optional[str] = None,
        explicit_level: Optional[str] = None,
        explicit_metadata: Optional[Dict[str, Any]] = None,
    ) -> ParsedLogResult:
        """
        Extracts structured fields from JSON payloads with key aliasing.
        """
        metadata = (explicit_metadata or {}).copy()

        # Service name
        service = (
            explicit_service
            or json_data.get("service")
            or json_data.get("service_name")
            or json_data.get("app")
            or json_data.get("application")
            or "unknown-service"
        )

        # Environment
        env = (
            explicit_env
            or json_data.get("environment")
            or json_data.get("env")
            or "production"
        )

        # Severity level
        raw_level = (
            explicit_level
            or json_data.get("level")
            or json_data.get("severity")
            or json_data.get("loglevel")
        )
        level = LogLevel.from_string(raw_level)

        # Message
        message = (
            json_data.get("message")
            or json_data.get("msg")
            or json_data.get("error")
            or json_data.get("log")
            or raw_log
        )
        if not str(message).strip():
            raise ValueError("JSON log contains an empty message field.")

        # Timestamp
        raw_ts = (
            json_data.get("timestamp")
            or json_data.get("@timestamp")
            or json_data.get("time")
            or json_data.get("datetime")
        )
        ts, is_fb = cls.parse_timestamp(raw_ts)
        metadata["timestamp_inferred"] = is_fb
        raw_ts_str = str(raw_ts) if raw_ts is not None else None
        if raw_ts_str:
            metadata["original_timestamp_raw"] = raw_ts_str

        # Correlation identifiers
        request_id = (
            json_data.get("request_id")
            or json_data.get("requestId")
            or json_data.get("x-request-id")
        )
        trace_id = (
            json_data.get("trace_id")
            or json_data.get("traceId")
            or json_data.get("x-trace-id")
        )
        host = (
            json_data.get("host")
            or json_data.get("hostname")
            or json_data.get("node")
        )
        source = (
            json_data.get("source")
            or json_data.get("logger")
            or json_data.get("logger_name")
        )

        # Store any remaining unmapped attributes in metadata
        reserved_keys = {
            "service", "service_name", "app", "application",
            "environment", "env",
            "level", "severity", "loglevel",
            "message", "msg", "error", "log",
            "timestamp", "@timestamp", "time", "datetime",
            "request_id", "requestId", "x-request-id",
            "trace_id", "traceId", "x-trace-id",
            "host", "hostname", "node",
            "source", "logger", "logger_name"
        }
        for k, v in json_data.items():
            if k not in reserved_keys:
                metadata[k] = v

        return ParsedLogResult(
            service_name=str(service),
            environment=str(env),
            level=level,
            message=str(message).strip(),
            timestamp=ts,
            source=str(source) if source else None,
            host=str(host) if host else None,
            request_id=str(request_id) if request_id else None,
            trace_id=str(trace_id) if trace_id else None,
            metadata=metadata,
            raw_log=raw_log,
            is_timestamp_inferred=is_fb,
            original_timestamp_raw=raw_ts_str
        )
