import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    """
    Test that /api/v1/health returns 200 OK with expected status.
    """
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "OpsSage AI"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_ready_check_endpoint(async_client: AsyncClient):
    """
    Test that /api/v1/ready responds with either 200 or 503 depending on database status,
    returning a structured readiness payload.
    """
    response = await async_client.get("/api/v1/ready")
    assert response.status_code in [200, 503]
    data = response.json()
    assert data["status"] in ["ready", "unready"]
    assert data["database"] in ["connected", "disconnected"]
    assert "timestamp" in data
