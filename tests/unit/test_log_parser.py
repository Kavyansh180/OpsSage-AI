from datetime import datetime, timezone
import pytest
from backend.app.models.log import LogLevel
from backend.app.services.log_parser import LogParser


def test_parse_valid_json_log():
    raw_json = (
        '{"timestamp": "2026-11-02T10:30:00Z", "level": "ERROR", '
        '"service": "payment-service", "message": "Database connection failed", '
        '"request_id": "req-123", "trace_id": "tr-456", "customer_id": 9981}'
    )
    result = LogParser.parse(raw_log=raw_json)

    assert result.service_name == "payment-service"
    assert result.level == LogLevel.ERROR
    assert result.message == "Database connection failed"
    assert result.request_id == "req-123"
    assert result.trace_id == "tr-456"
    assert result.metadata.get("customer_id") == 9981
    assert result.timestamp == datetime(2026, 11, 2, 10, 30, 0, tzinfo=timezone.utc)
    assert result.metadata.get("timestamp_inferred") is False
    assert result.metadata.get("original_timestamp_raw") == "2026-11-02T10:30:00Z"


def test_parse_valid_standard_application_log():
    raw_line = "2026-11-02 10:30:00 ERROR payment-service - Connection refused to PostgreSQL"
    result = LogParser.parse(raw_log=raw_line)

    assert result.service_name == "payment-service"
    assert result.level == LogLevel.ERROR
    assert result.message == "Connection refused to PostgreSQL"
    assert result.timestamp == datetime(2026, 11, 2, 10, 30, 0, tzinfo=timezone.utc)
    assert result.metadata.get("timestamp_inferred") is False
    assert result.metadata.get("original_timestamp_raw") == "2026-11-02 10:30:00"


def test_parse_simple_log_without_service():
    raw_line = "2026-11-02 10:30:00 WARN High CPU usage detected on host"
    result = LogParser.parse(raw_log=raw_line)

    assert result.service_name == "unknown-service"
    assert result.level == LogLevel.WARNING
    assert result.message == "High CPU usage detected on host"


def test_parse_missing_timestamp_fallback():
    raw_json = '{"level": "INFO", "service": "auth-service", "message": "User logged in"}'
    result = LogParser.parse(raw_log=raw_json)

    assert result.service_name == "auth-service"
    assert result.level == LogLevel.INFO
    assert isinstance(result.timestamp, datetime)
    assert result.timestamp.tzinfo == timezone.utc
    assert result.metadata.get("timestamp_inferred") is True
    assert result.metadata.get("original_timestamp_raw") is None


def test_parse_invalid_timestamp_fallback_and_provenance():
    raw_json = '{"timestamp": "not-a-valid-date", "level": "INFO", "message": "Test message"}'
    result = LogParser.parse(raw_log=raw_json)

    assert isinstance(result.timestamp, datetime)
    assert result.timestamp.tzinfo == timezone.utc
    assert result.metadata.get("timestamp_inferred") is True
    assert result.metadata.get("original_timestamp_raw") == "not-a-valid-date"


def test_parse_timezone_aware_timestamp_converts_to_utc():
    # 15:30 at UTC+5:30 is 10:00 UTC
    raw_json = '{"timestamp": "2026-11-02T15:30:00+05:30", "message": "Indian region event"}'
    result = LogParser.parse(raw_log=raw_json)

    assert result.timestamp == datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)
    assert result.timestamp.tzinfo == timezone.utc
    assert result.metadata.get("timestamp_inferred") is False


def test_parse_timezone_naive_timestamp_assumes_utc():
    dt_naive = datetime(2026, 11, 2, 10, 30, 0)
    result = LogParser.parse(explicit_message="Event with naive dt", explicit_timestamp=dt_naive)

    assert result.timestamp.tzinfo == timezone.utc
    assert result.timestamp == datetime(2026, 11, 2, 10, 30, 0, tzinfo=timezone.utc)
    assert result.metadata.get("timestamp_inferred") is False


def test_raw_log_storage_semantics_avoids_duplicate():
    # 1. Structured log without raw_log: raw_log should be None to prevent redundant storage
    structured_result = LogParser.parse(
        explicit_message="Payment processed",
        explicit_service="payment-service"
    )
    assert structured_result.message == "Payment processed"
    assert structured_result.raw_log is None

    # 2. Raw unparsed log string: raw_log preserves the original string line
    raw_str = "2026-11-02 10:30:00 INFO payment-service - Payment processed"
    raw_result = LogParser.parse(raw_log=raw_str)
    assert raw_result.message == "Payment processed"
    assert raw_result.raw_log == raw_str


def test_parse_missing_severity():
    raw_json = '{"message": "General system event without level"}'
    result = LogParser.parse(raw_log=raw_json)

    assert result.level == LogLevel.UNKNOWN


def test_parse_unknown_severity():
    raw_json = '{"level": "CUSTOM_ALERT_LEVEL", "message": "Special alert"}'
    result = LogParser.parse(raw_log=raw_json)

    assert result.level == LogLevel.UNKNOWN


def test_parse_empty_message_raises_error():
    with pytest.raises(ValueError) as exc_info:
        LogParser.parse(raw_log='{"message": "   "}')

    assert "empty message" in str(exc_info.value).lower()


def test_parse_unrecognized_format():
    raw_line = "Just some unstructured arbitrary raw console output line"
    result = LogParser.parse(raw_log=raw_line)

    assert result.service_name == "unknown-service"
    assert result.level == LogLevel.UNKNOWN
    assert result.message == raw_line
    assert result.raw_log == raw_line
    assert result.metadata.get("unrecognized_format") is True
