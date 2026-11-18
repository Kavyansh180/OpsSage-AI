from backend.app.services.log_normalizer import LogNormalizer


def test_normalize_uuid_and_ip():
    msg = "Request 123e4567-e89b-12d3-a456-426614174000 failed from 192.168.1.42:8080"
    normalized = LogNormalizer.normalize(msg)

    assert "<UUID>" in normalized
    assert "<IP>" in normalized
    assert "123e4567" not in normalized
    assert "192.168.1.42" not in normalized


def test_normalize_hex_addresses():
    msg = "Segmentation fault at 0x7fff5fbff820 in worker thread"
    normalized = LogNormalizer.normalize(msg)

    assert "0x7fff5fbff820" not in normalized
    assert "<HEX>" in normalized


def test_normalize_variable_numeric_ids():
    msg = "Connection timeout for user 12345 on account_id=89211 with order #99482"
    normalized = LogNormalizer.normalize(msg)

    assert "user <ID>" in normalized
    assert "account_id=<ID>" in normalized
    assert "order #<ID>" in normalized
    assert "12345" not in normalized
    assert "89211" not in normalized


def test_normalize_standalone_large_numbers():
    msg = "Processed batch item 99182746 in queue"
    normalized = LogNormalizer.normalize(msg)

    assert "<NUM>" in normalized
    assert "99182746" not in normalized


def test_normalize_embedded_timestamps():
    msg = "Job triggered at 2026-11-02 10:30:45 and finished at 10:31:12"
    normalized = LogNormalizer.normalize(msg)

    assert "<TIMESTAMP>" in normalized
    assert "<TIME>" in normalized
    assert "2026-11-02 10:30:45" not in normalized


def test_preserves_technical_exception_names():
    msg = "Unhandled NullPointerException: DatabaseConnectionError occurred in payment-gateway"
    normalized = LogNormalizer.normalize(msg)

    assert "NullPointerException" in normalized
    assert "DatabaseConnectionError" in normalized
    assert "payment-gateway" in normalized


def test_preserves_sql_codes_and_http_paths():
    msg = "Database query failed with ORA-00942 and PG-08006 during POST /api/v1/checkout 504"
    normalized = LogNormalizer.normalize(msg)

    assert "ORA-00942" in normalized
    assert "PG-08006" in normalized
    assert "POST /api/v1/checkout" in normalized
    assert "504" in normalized


def test_preserves_http_status_codes_and_endpoints():
    msg = "GET /api/v1/payments returned 500 Internal Server Error; retry returned 502 Bad Gateway then 404 Not Found"
    normalized = LogNormalizer.normalize(msg)

    assert "500" in normalized
    assert "502" in normalized
    assert "404" in normalized
    assert "/api/v1/payments" in normalized


def test_preserves_sql_numeric_error_codes():
    msg = "PostgreSQL query failed with error 23505: duplicate key value violates unique constraint; SQLSTATE 23505"
    normalized = LogNormalizer.normalize(msg)

    assert "23505" in normalized
    assert "SQLSTATE 23505" in normalized or "23505" in normalized
    assert "<NUM>" not in normalized


def test_preserves_port_numbers_and_durations():
    msg = "Postgres listening on port 54321 timed out after 30000 ms (threshold 60000ms, wait 120s)"
    normalized = LogNormalizer.normalize(msg)

    assert "54321" in normalized
    assert "30000 ms" in normalized
    assert "60000ms" in normalized
    assert "120s" in normalized
    assert "<NUM>" not in normalized


def test_preserves_retry_counts_and_attempts():
    msg = "Transaction failed after 3 retries (attempt 2 of 5) on host 10.0.0.1"
    normalized = LogNormalizer.normalize(msg)

    assert "3 retries" in normalized
    assert "attempt 2 of 5" in normalized
    assert "<IP>" in normalized


def test_original_message_immutability():
    original = "User 12345 experienced TimeoutException at 10:30:00"
    normalized = LogNormalizer.normalize(original)

    # Normalization produces new string, leaving original untouched
    assert original == "User 12345 experienced TimeoutException at 10:30:00"
    assert normalized != original
    assert "<ID>" in normalized
