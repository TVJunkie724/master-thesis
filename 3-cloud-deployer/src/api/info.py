"""
API Info Endpoints - Health check only.

All config endpoints have been migrated to `/projects/{name}/config/{type}`.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/", 
    operation_id="getApiHealth",
    tags=["Projects"],
    summary="API health check",
    description=(
        "**Purpose:** Check API status and active project.\\n\\n"
        "**When to call:** For health checks and debugging."
    )
)
def read_root():
    """
    API health check endpoint.
    
    Returns API status and currently active project.
    """
    return {"status": "API is running", "active_project": None}
