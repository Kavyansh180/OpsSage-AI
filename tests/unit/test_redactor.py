import pytest
from backend.app.services.redactor import SecretRedactor


def test_redact_bearer_token():
    text = "Authorization: Bearer mySecretToken1234567890abcdef and more text"
    redacted, count = SecretRedactor.redact(text)
    assert count >= 1
    assert "mySecretToken1234567890abcdef" not in redacted
    assert "[REDACTED_TOKEN]" in redacted or "[REDACTED_SECRET]" in redacted


def test_redact_jwt_token():
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    text = f"User session header: {jwt}"
    redacted, count = SecretRedactor.redact(text)
    assert count >= 1
    assert jwt not in redacted
    assert "[REDACTED_JWT]" in redacted


def test_redact_google_api_key():
    key = "AIzaSyD-1234567890abcdefghij-klmnopqr"
    text = f"Using API key {key} to call Gemini"
    redacted, count = SecretRedactor.redact(text)
    assert count >= 1
    assert key not in redacted
    assert "[REDACTED_API_KEY]" in redacted or "[REDACTED_SECRET]" in redacted


def test_redact_openai_api_key():
    key = "sk-proj-1234567890abcdefghijklmnopqr"
    text = f"Error with key {key}"
    redacted, count = SecretRedactor.redact(text)
    assert count >= 1
    assert key not in redacted
    assert "[REDACTED_API_KEY]" in redacted or "[REDACTED_SECRET]" in redacted


def test_redact_aws_key():
    aws_key = "AKIAIOSFODNN7EXAMPLE"
    text = f"AWS S3 upload using {aws_key}"
    redacted, count = SecretRedactor.redact(text)
    assert count >= 1
    assert aws_key not in redacted
    assert "[REDACTED_AWS_KEY]" in redacted


def test_redact_database_connection_credentials():
    postgres_uri = "postgresql://db_admin:SuperSecretPass123@db.prod.internal:5432/app_db"
    redacted, count = SecretRedactor.redact(postgres_uri)
    assert count >= 1
    assert "SuperSecretPass123" not in redacted
    assert "db_admin" not in redacted
    assert "[REDACTED_USER]:[REDACTED_PASSWORD]@db.prod.internal:5432/app_db" in redacted


def test_redact_mongo_srv_credentials():
    mongo_uri = "mongodb+srv://admin_user:Passw0rdWithSpecial!@cluster0.mongodb.net/test?retryWrites=true"
    redacted, count = SecretRedactor.redact(mongo_uri)
    assert count >= 1
    assert "Passw0rdWithSpecial!" not in redacted
    assert "admin_user" not in redacted


def test_redact_key_value_secrets():
    text = 'Config: {"password": "topSecretPassword123", "client_secret": "mySecretClientToken"}'
    redacted, count = SecretRedactor.redact(text)
    assert count >= 2
    assert "topSecretPassword123" not in redacted
    assert "mySecretClientToken" not in redacted


def test_preserves_technical_diagnostics_and_errors():
    error_msg = (
        "psycopg2.OperationalError: connection to server at '10.0.0.5', port 5432 failed: "
        "FATAL: password authentication failed for user 'ops_worker'. "
        "HTTP 500 on endpoint /api/v1/checkout/process"
    )
    redacted, count = SecretRedactor.redact(error_msg)
    # The technical diagnostics must remain fully intact for the RCA engine
    assert "psycopg2.OperationalError" in redacted
    assert "port 5432" in redacted
    assert "FATAL: password authentication failed for user 'ops_worker'" in redacted
    assert "HTTP 500" in redacted
    assert "/api/v1/checkout/process" in redacted


def test_redact_empty_or_clean_text():
    assert SecretRedactor.redact("") == ("", 0)
    assert SecretRedactor.redact(None) == (None, 0)

    clean_text = "Server started successfully on port 8080. Healthcheck OK."
    redacted, count = SecretRedactor.redact(clean_text)
    assert count == 0
    assert redacted == clean_text
