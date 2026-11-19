from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from backend.app.api.v1.router import api_router
from backend.app.config import get_settings
from backend.app.core.exceptions import (
    AppException,
    app_exception_handler,
    unhandled_exception_handler,
)
from backend.app.core.logging import get_logger, setup_logging
from backend.app.db.indexes import setup_database_indexes
from backend.app.db.mongodb import MongoDBManager

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager handling startup and shutdown hooks.
    """
    # 1. Startup phase
    setup_logging()
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' mode...")

    # Connect to MongoDB
    await MongoDBManager.connect()

    # If connection was successful, optionally initialize collection indexes
    if settings.INITIALIZE_INDEXES_ON_STARTUP:
        if await MongoDBManager.ping():
            db = MongoDBManager.get_database()
            await setup_database_indexes(db)
        else:
            logger.warning("Database ping unverified at startup. Skipping index initialization.")

    yield

    # 2. Shutdown phase
    logger.info("Initiating graceful shutdown...")
    await MongoDBManager.close()
    logger.info("Shutdown complete.")


def create_application() -> FastAPI:
    """
    Application factory building and configuring the FastAPI instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description=(
            "AI-Powered DevOps Incident Investigation and Root-Cause Analysis Platform. "
            "Automates log processing, incident clustering, vector-based RAG retrieval, "
            "and evidence-backed root-cause analysis."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing (CORS) Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_origin_regex=r"https://.*\.streamlit\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # API Versioned Router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        """Redirects root URL to interactive Swagger documentation."""
        return RedirectResponse(url="/docs")

    return app


app = create_application()
