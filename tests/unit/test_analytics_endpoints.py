from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.main import app
from backend.app.models.user import UserInDB, UserRole


@pytest.fixture
def mock_engineer():
    return UserInDB(
        id="test-eng-1",
        email="eng@example.com",
        full_name="Analytics Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_incidents():
    now = datetime.now(timezone.utc)
    return [
        {
            "_id": ObjectId(),
            "incident_id": "INC-001",
            "user_id": "test-eng-1",
            "service_name": "auth-service",
            "environment": "production",
            "severity": "CRITICAL",
            "status": "OPEN",
            "error_signature": "sig-1",
            "title": "Auth failure",
            "event_count": 5,
            "created_at": now,
            "first_seen": now,
        },
        {
            "_id": ObjectId(),
            "incident_id": "INC-002",
            "user_id": "test-eng-1",
            "service_name": "payment-service",
            "environment": "production",
            "severity": "HIGH",
            "status": "RESOLVED",
            "error_signature": "sig-2",
            "title": "Payment timeout",
            "event_count": 10,
            "created_at": now,
            "first_seen": now,
            "acknowledged_at": now,
            "resolved_at": now,
        },
    ]


@pytest.mark.asyncio
async def test_analytics_overview_calculation(mock_engineer, sample_incidents):
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=sample_incidents)
    mock_db["incidents"].find = MagicMock(return_value=mock_cursor)

    app.dependency_overrides[get_current_user] = lambda: mock_engineer
    app.dependency_overrides[get_db] = lambda: mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/analytics/overview")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["total_incidents"] == 2
        assert data["open_incidents"] == 1
        assert data["resolved_incidents"] == 1
        assert data["critical_incidents"] == 1
        assert data["high_incidents"] == 1
        assert data["resolution_rate_pct"] == 50.0
        assert "auth-service" in data["by_service"]
        assert "payment-service" in data["by_service"]
        assert len(data["recurring_patterns"]) == 2

    app.dependency_overrides.clear()
