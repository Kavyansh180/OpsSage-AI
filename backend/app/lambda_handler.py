"""
OpsSage AI - AWS Lambda Handler Entrypoint
Wraps FastAPI application with Mangum for serverless execution behind API Gateway.
"""

from typing import Any, Dict
from mangum import Mangum
from backend.app.core.logging import get_logger, setup_logging
from backend.app.main import app

# Ensure logging is initialized on Lambda container cold start
setup_logging()
logger = get_logger("lambda_handler")

# Initialize Mangum adapter with lifespan="off".
# CRITICAL FOR SERVERLESS: Setting lifespan="off" prevents Mangum from firing
# ASGI lifespan shutdown events after every single Lambda invocation.
# This ensures that PyMongo's AsyncMongoClient connection pool stays alive and
# is reused across warm Lambda invocations, avoiding severe connection churn
# and eliminating 100-200ms of reconnection/handshake latency per request.
handler = Mangum(app, lifespan="off")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entrypoint invoked by AWS Lambda runtime.
    Delegates directly to Mangum ASGI adapter.
    """
    return handler(event, context)
