import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.lambda_handler import lambda_handler
from backend.app.db.mongodb import MongoDBManager


class MockLambdaContext:
    function_name = "test-opssage-backend"
    memory_limit_in_mb = 2048
    invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-opssage-backend"
    aws_request_id = "test-aws-request-id-12345"


@pytest.fixture
def mock_context():
    return MockLambdaContext()


def test_lambda_handler_health_check_payload_v2(mock_context):
    """
    Verifies that the Mangum Lambda handler processes an API Gateway HTTP API (payload format 2.0)
    event to /api/v1/health and returns a valid 200 JSON response.
    """
    event = {
        "version": "2.0",
        "routeKey": "GET /api/v1/health",
        "rawPath": "/api/v1/health",
        "rawQueryString": "",
        "headers": {
            "accept": "application/json",
            "host": "api.opssage.test",
            "user-agent": "pytest-client",
            "x-forwarded-proto": "https"
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "testapi",
            "domainName": "api.opssage.test",
            "http": {
                "method": "GET",
                "path": "/api/v1/health",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest-client"
            },
            "requestId": "test-req-1",
            "routeKey": "GET /api/v1/health",
            "stage": "$default",
            "timeEpoch": 1583348638390
        },
        "isBase64Encoded": False
    }

    response = lambda_handler(event, mock_context)

    assert response["statusCode"] == 200
    assert "application/json" in response["headers"].get("content-type", "")
    body = json.loads(response["body"])
    assert body["status"] == "healthy"
    assert body["app_name"] == "OpsSage AI"


def test_lambda_handler_unauthenticated_protected_route(mock_context):
    """
    Verifies that a protected route (/api/v1/incidents) without credentials returns
    401 Unauthorized through Mangum and API Gateway.
    """
    event = {
        "version": "2.0",
        "routeKey": "GET /api/v1/incidents",
        "rawPath": "/api/v1/incidents",
        "rawQueryString": "",
        "headers": {
            "accept": "application/json",
            "host": "api.opssage.test"
        },
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "testapi",
            "http": {
                "method": "GET",
                "path": "/api/v1/incidents",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1"
            },
            "requestId": "test-req-2",
            "stage": "$default"
        },
        "isBase64Encoded": False
    }

    response = lambda_handler(event, mock_context)
    assert response["statusCode"] == 401
    body = json.loads(response["body"])
    assert "error" in body or "detail" in body


def test_lambda_handler_payload_v1_compatibility(mock_context):
    """
    Verifies backward compatibility with API Gateway Payload Format 1.0 (REST API format).
    """
    event = {
        "version": "1.0",
        "httpMethod": "GET",
        "path": "/api/v1/health",
        "queryStringParameters": None,
        "headers": {
            "Accept": "application/json",
            "Host": "api.opssage.test"
        },
        "requestContext": {
            "resourceId": "123456",
            "apiId": "testapi",
            "httpMethod": "GET",
            "requestId": "test-req-v1",
            "path": "/api/v1/health"
        },
        "body": None,
        "isBase64Encoded": False
    }

    response = lambda_handler(event, mock_context)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "healthy"


def test_lambda_handler_cors_preflight(mock_context):
    """
    Verifies CORS preflight OPTIONS request returns valid access control headers.
    """
    event = {
        "version": "2.0",
        "routeKey": "OPTIONS /api/v1/incidents",
        "rawPath": "/api/v1/incidents",
        "rawQueryString": "",
        "headers": {
            "origin": "https://test-dashboard.streamlit.app",
            "access-control-request-method": "GET",
            "access-control-request-headers": "authorization,content-type"
        },
        "requestContext": {
            "http": {
                "method": "OPTIONS",
                "path": "/api/v1/incidents",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest-client"
            },
            "stage": "$default"
        },
        "isBase64Encoded": False
    }

    response = lambda_handler(event, mock_context)
    assert response["statusCode"] == 200
    headers = {k.lower(): v for k, v in response.get("headers", {}).items()}
    assert "access-control-allow-origin" in headers


@pytest.mark.asyncio
async def test_mongodb_connection_reuse_across_invocations():
    """
    Verifies that MongoDBManager.ensure_database() reuses the existing client instance
    when running on the same event loop across sequential invocations.
    """
    # 1. Reset state
    await MongoDBManager.close()

    mock_db = MagicMock()
    mock_client = MagicMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})
    mock_client.__getitem__.return_value = mock_db

    with patch("backend.app.db.mongodb.AsyncMongoClient", return_value=mock_client) as mock_constructor:
        # First call: initializes client
        db1 = await MongoDBManager.ensure_database()
        assert db1 is not None
        assert mock_constructor.call_count == 1

        # Second call (simulating warm invocation on same loop): reuses client
        db2 = await MongoDBManager.ensure_database()
        assert db2 is not None
        assert mock_constructor.call_count == 1  # No re-instantiation

    # Cleanup
    await MongoDBManager.close()


def test_warm_lambda_invocations_preserve_mongodb_client(mock_context):
    """
    Verifies that sequential calls to lambda_handler in the same Lambda container
    do NOT close MongoDBManager._client, ensuring connection pool reuse across warm invocations.
    """
    event = {
        "version": "2.0",
        "routeKey": "GET /api/v1/ready",
        "rawPath": "/api/v1/ready",
        "rawQueryString": "",
        "headers": {
            "accept": "application/json",
            "host": "api.opssage.test"
        },
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/api/v1/ready",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1"
            },
            "stage": "$default"
        },
        "isBase64Encoded": False
    }

    mock_db = MagicMock()
    mock_client = MagicMock()
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})
    mock_client.__getitem__.return_value = mock_db

    # Force reset
    MongoDBManager._client = None
    MongoDBManager._db = None
    MongoDBManager._loop = None

    with patch("backend.app.db.mongodb.AsyncMongoClient", return_value=mock_client) as mock_constructor:
        # Invocation 1: Cold start
        resp1 = lambda_handler(event, mock_context)
        assert resp1["statusCode"] == 200, f"Expected 200 OK, got {resp1['statusCode']}"
        body1 = json.loads(resp1["body"])
        assert body1["status"] == "ready"
        assert body1["database"] == "connected"

        # After invocation 1 with lifespan='off', MongoDBManager._client must still be preserved (NOT closed!)
        assert MongoDBManager._client is not None, "Client should remain open after first Lambda invocation"
        assert MongoDBManager._client is mock_client
        assert mock_client.close.call_count == 0, "Client must not be closed between invocations"

        # Invocation 2: Warm invocation in the same container process
        resp2 = lambda_handler(event, mock_context)
        assert resp2["statusCode"] == 200, f"Expected 200 OK, got {resp2['statusCode']}"
        body2 = json.loads(resp2["body"])
        assert body2["status"] == "ready"
        assert body2["database"] == "connected"

        # Verify that database operations succeeded on both invocations
        # Call 1: initial connection verification ping inside MongoDBManager.connect()
        # Call 2: readiness check ping in Invocation 1
        # Call 3: readiness check ping in Invocation 2 (executed without reconnecting!)
        assert mock_client.admin.command.call_count == 3, "Database ping command must execute across invocations"

        # Confirm AsyncMongoClient was NOT re-instantiated on the second call (connection reused!)
        assert mock_constructor.call_count == 1, "AsyncMongoClient should be reused and not reconstructed"
        assert mock_client.close.call_count == 0, "Connection pool should remain alive across invocations"

    # Cleanup
    MongoDBManager._client = None
    MongoDBManager._db = None
    MongoDBManager._loop = None
