from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from src.models.database import get_db
from src.schemas.management_contracts import HealthResponse

router = APIRouter(tags=["health"])

@router.get(
    "/health",
    response_model=HealthResponse,
    operation_id="healthCheck",
    summary="Health check endpoint",
    description="Returns API and database connection status."
)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Test DB connection
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": str(e)
        }
