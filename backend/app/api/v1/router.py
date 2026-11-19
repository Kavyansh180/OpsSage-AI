from fastapi import APIRouter
from backend.app.api.v1.endpoints import analytics, analysis, auth, health, incidents, knowledge, logs

api_router = APIRouter()

# Core diagnostic and health endpoints
api_router.include_router(health.router)

# Module 1: Authentication & User Management
api_router.include_router(auth.router, prefix="/auth")

# Module 2: Log Ingestion & Parsing Engine
api_router.include_router(logs.router, prefix="/logs")

# Module 3: Deterministic Incident Detection
api_router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])

# Module 4: AI Root Cause Analysis
api_router.include_router(analysis.router, tags=["AI Root Cause Analysis"])

# Module 5: RAG Historical Incident Retrieval
api_router.include_router(knowledge.router)

# Module 7: Analytics & KPIs
api_router.include_router(analytics.router)
