from unittest.mock import MagicMock, patch
import pytest

from frontend.api_client import APIClient


@pytest.fixture
def client():
    return APIClient(base_url="http://testserver:8000")


def test_api_client_url_normalization():
    c1 = APIClient(base_url="http://localhost:8000")
    assert c1.base_url == "http://localhost:8000/api/v1"

    c2 = APIClient(base_url="http://localhost:8000/api/v1")
    assert c2.base_url == "http://localhost:8000/api/v1"

    c3 = APIClient(base_url="http://localhost:8000/api/v1/")
    assert c3.base_url == "http://localhost:8000/api/v1"


def test_api_client_login_success(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "mock-token", "token_type": "bearer"}

    with patch("httpx.Client.post", return_value=mock_resp):
        res = client.login("test@example.com", "password123")
        assert res["access_token"] == "mock-token"


def test_api_client_login_failure(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"detail": "Invalid credentials"}
    mock_resp.text = "Invalid credentials"

    with patch("httpx.Client.post", return_value=mock_resp):
        with pytest.raises(Exception) as exc:
            client.login("test@example.com", "wrong")
        assert "Login failed (401)" in str(exc.value)


def test_api_client_list_incidents_filters(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"items": [], "total": 0, "limit": 50, "offset": 0}

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        res = client.list_incidents(
            token="token123",
            status="OPEN",
            severity="CRITICAL",
            environment="production",
        )
        assert res["total"] == 0
        call_params = mock_get.call_args[1]["params"]
        assert call_params["status"] == "OPEN"
        assert call_params["severity"] == "CRITICAL"
        assert call_params["environment"] == "production"


def test_api_client_record_resolution(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"incident_id": "INC-123", "status": "RESOLVED"}

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res = client.record_resolution(
            token="token123",
            incident_id="INC-123",
            root_cause="Redis memory limit exceeded",
            resolution="Increased maxmemory and enabled allkeys-lru",
            actions=["Updated config", "Restarted cluster"],
            is_verified=True,
        )
        assert res["status"] == "RESOLVED"
        payload = mock_post.call_args[1]["json"]
        assert payload["confirmed_root_cause"] == "Redis memory limit exceeded"
        assert payload["is_verified"] is True


def test_api_client_get_analytics(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "total_incidents": 10,
        "open_incidents": 2,
        "resolved_incidents": 8,
        "resolution_rate_pct": 80.0,
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = client.get_analytics("token123", days=30)
        assert res["total_incidents"] == 10
        assert res["resolution_rate_pct"] == 80.0
