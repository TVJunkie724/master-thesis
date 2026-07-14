import logging

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.database import get_db
from src.schemas.management_contracts import HealthResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

@router.get(
    "/health",
    response_model=HealthResponse,
    operation_id="healthCheck",
    summary="Health check endpoint",
    description="Returns API and database connection status."
)
async def health_check(response: Response, db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Test DB connection
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as exc:
        logger.error("Database health check failed (%s)", type(exc).__name__)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "database": "unavailable"
        }
