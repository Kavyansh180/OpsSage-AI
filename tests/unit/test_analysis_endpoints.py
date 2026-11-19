from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from bson import ObjectId
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.dependencies import get_current_user, get_db
from backend.app.main import app
from backend.app.models.analysis import ConfidenceLevel
from backend.app.models.user import UserInDB, UserRole
from backend.app.schemas.analysis import AnalysisResponse, PaginatedAnalysisResponse


@pytest.fixture
def mock_engineer():
    return UserInDB(
        id="user-eng",
        email="eng@example.com",
        full_name="DevOps Engineer",
        hashed_password="pw",
        role=UserRole.ENGINEER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_viewer():
    return UserInDB(
        id="user-view",
        email="viewer@example.com",
        full_name="Viewer User",
        hashed_password="pw",
        role=UserRole.VIEWER,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_analyze_incident_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/api/v1/incidents/INC-001/analyze")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_analyze_incident_viewer_role_forbidden(mock_viewer):
    app.dependency_overrides[get_current_user] = lambda: mock_viewer
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/v1/incidents/INC-001/analyze",
                headers={"Authorization": "Bearer mock-token"},
            )
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analyze_incident_engineer_success(mock_engineer):
    app.dependency_overrides[get_current_user] = lambda: mock_engineer
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    sample_analysis = AnalysisResponse(
        id="mongo-id-1",
        analysis_id="RCA-20261118-TEST1",
        incident_id="INC-20261118-001",
        user_id=mock_engineer.id,
        probable_root_cause="Redis connection timeout",
        explanation="Redis cluster reached maximum client connection threshold.",
        supporting_evidence=["Log at 10:00:00: Redis timeout 5000ms"],
        contributing_factors=["Connection pool spike"],
        confidence_level=ConfidenceLevel.HIGH,
        recommended_actions=["Restart cache pod", "Scale cluster"],
        limitations=[],
        provider="gemini",
        model="gemini-3.5-flash-lite",
        evidence_log_count=5,
        redacted_secrets_count=1,
        created_at=datetime.now(timezone.utc),
    )

    try:
        with patch("backend.app.services.rca_service.RCAService.analyze_incident", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = sample_analysis

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.post(
                    "/api/v1/incidents/INC-20261118-001/analyze",
                    json={"additional_context": "Restarted earlier"},
                    headers={"Authorization": "Bearer mock-token"},
                )
                assert resp.status_code == 201
                data = resp.json()
                assert data["analysis_id"] == "RCA-20261118-TEST1"
                assert data["probable_root_cause"] == "Redis connection timeout"
                assert data["confidence_level"] == "HIGH"
                assert data["provider"] == "gemini"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_incident_analyses_endpoint(mock_engineer):
    app.dependency_overrides[get_current_user] = lambda: mock_engineer
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    paginated_mock = PaginatedAnalysisResponse(
        items=[
            AnalysisResponse(
                id="item-1",
                analysis_id="RCA-HIST-1",
                incident_id="INC-001",
                user_id=mock_engineer.id,
                probable_root_cause="OOM",
                explanation="Out of memory",
                supporting_evidence=[],
                contributing_factors=[],
                confidence_level=ConfidenceLevel.MEDIUM,
                recommended_actions=[],
                limitations=[],
                provider="gemini",
                model="gemini-3.5-flash-lite",
                evidence_log_count=1,
                redacted_secrets_count=0,
                created_at=datetime.now(timezone.utc),
            )
        ],
        total=1,
        limit=50,
        offset=0,
    )

    try:
        with patch("backend.app.services.rca_service.RCAService.get_incident_analyses", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = paginated_mock

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(
                    "/api/v1/incidents/INC-001/analyses",
                    headers={"Authorization": "Bearer mock-token"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
                assert len(data["items"]) == 1
                assert data["items"][0]["analysis_id"] == "RCA-HIST-1"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_analysis_by_id_endpoint(mock_engineer):
    app.dependency_overrides[get_current_user] = lambda: mock_engineer
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    analysis_mock = AnalysisResponse(
        id="item-2",
        analysis_id="RCA-SINGLE-1",
        incident_id="INC-002",
        user_id=mock_engineer.id,
        probable_root_cause="Network partition",
        explanation="VPC routing table error",
        supporting_evidence=[],
        contributing_factors=[],
        confidence_level=ConfidenceLevel.HIGH,
        recommended_actions=[],
        limitations=[],
        provider="gemini",
        model="gemini-3.5-flash-lite",
        evidence_log_count=3,
        redacted_secrets_count=0,
        created_at=datetime.now(timezone.utc),
    )

    try:
        with patch("backend.app.services.rca_service.RCAService.get_analysis_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = analysis_mock

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                resp = await client.get(
                    "/api/v1/analyses/RCA-SINGLE-1",
                    headers={"Authorization": "Bearer mock-token"},
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["analysis_id"] == "RCA-SINGLE-1"
                assert data["probable_root_cause"] == "Network partition"
    finally:
        app.dependency_overrides.clear()
