"""
API Info Endpoints - Health check only.

All config endpoints have been migrated to `/projects/{name}/config/{type}`.
"""

from fastapi import APIRouter
import src.core.state as state

router = APIRouter()


@router.get("/", tags=["Projects"])
def read_root():
    """
    API health check endpoint.
    
    Returns API status and currently active project.
    """
    return {"status": "API is running", "active_project": state.get_active_project()}
