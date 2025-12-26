"""
Twin2Clouds REST API

FastAPI application serving the cost optimization platform for Digital Twin deployments.
API endpoints are organized into separate router modules in the api/ directory.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.logger import logger
from backend.config_loader import load_config_file

# Import API routers
from api import calculation, pricing, regions, file_status, credentials


# =============================================================================
# Lifespan Context Manager (replaces deprecated on_event)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    try:
        print("")
        logger.info("🚀 Starting Twin2Clouds API...")
        load_config_file()
        logger.info("✅ API ready.")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
    
    yield
    
    # Shutdown (if needed in future)


# =============================================================================
# FastAPI App Initialization
# =============================================================================

app = FastAPI(
    title="twin2clouds REST API",
    version="1.2",
    description=(
        "API backend for **Twin2Clouds**, a cost-optimization platform for engineering "
        "digital twins across multiple cloud providers (AWS, Azure, Google). "
        "This API serves both the web UI and the computational engine that calculates "
        "the most cost-efficient provider setup for each architectural layer."
        "<h3>🔗 Useful Links</h3>"
        "<h4>🖥️ Web Interface</h4>"
        "<ul><li><a href=\"/ui\" target=\"_blank\"><strong>Open Web UI</strong></a></br>"
        "  The graphical Twin2Clouds interface for configuring scenarios.</li></ul>"
        "<h4>📘 Documentation</h4>"
        "<ul><li><a href=\"/documentation/docs-overview.html\" target=\"_blank\"><strong>Documentation Overview</strong></a></li></ul>"
    ),
    openapi_tags=[
        {"name": "Calculation", "description": "Endpoints related to cloud cost calculation."},
        {"name": "Pricing", "description": "Endpoints for fetching cloud service pricing data."},
        {"name": "Regions", "description": "Endpoints for fetching cloud regions."},
        {"name": "File Status", "description": "Endpoints for checking the age of data files."},
        {"name": "Permissions - Upload", "description": "Verify cloud credentials from request body."},
        {"name": "Permissions - Project", "description": "Verify cloud credentials from project config."},
    ],
    lifespan=lifespan
)


# =============================================================================
# Static File Mounts
# =============================================================================

# Web UI assets (from webui/ folder)
app.mount("/js", StaticFiles(directory="webui/js"), name="js")
app.mount("/css", StaticFiles(directory="webui/css"), name="css")
app.mount("/json", StaticFiles(directory="json"), name="static-json")

# Documentation (including its css, js, and references subdirectories)
app.mount("/documentation", StaticFiles(directory="docs"), name="docs")


# =============================================================================
# Static Endpoints
# =============================================================================

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("docs/references/favicon.ico")


@app.get(
    "/ui",
    tags=["WebUI"],
    summary="Serve the Web Interface",
    description=(
        "Returns the main **index.html** file that serves as the graphical interface "
        "for Twin2Clouds. This page allows users to configure digital twin scenarios "
        "and trigger cloud cost calculations through the API."
    ),
    response_description="The index.html web interface file.",
    include_in_schema=False
)
def serve_ui():
    return FileResponse("webui/index.html")


# =============================================================================
# Include Routers
# =============================================================================

app.include_router(calculation.router)
app.include_router(pricing.router)
app.include_router(regions.router)
app.include_router(file_status.router)
app.include_router(credentials.router)
