"""
Twin2Clouds REST API

FastAPI application serving the thesis PoC cost optimizer.
API endpoints are organized into separate router modules in the api/ directory.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import API routers
from api import (
    calculation,
    capabilities,
    pricing,
    validation,
)
from backend.architecture_profiles import (
    validate_six_layer_strategy_readiness,
)
from backend.config_loader import load_config_file
from backend.logger import logger
from backend.pricing_catalog_repository import get_pricing_catalog_repository

# =============================================================================
# Lifespan Context Manager (replaces deprecated on_event)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    try:
        logger.info("🚀 Starting Twin2Clouds API...")
        load_config_file()
        get_pricing_catalog_repository().verify_readiness()
        validate_six_layer_strategy_readiness()
        logger.info("✅ API ready.")
    except Exception:
        logger.exception("Optimizer startup readiness failed")
        raise
    
    yield
    
    # Shutdown (if needed in future)


# =============================================================================
# FastAPI App Initialization
# =============================================================================

app = FastAPI(
    title="twin2clouds REST API",
    version="1.2",
    description=(
        "Internal cost-optimization service for the Twin2MultiCloud thesis PoC. "
        "It evaluates the fixed Six-layer Eventing contract across AWS, Azure, "
        "and Google Cloud using pinned thesis pricing evidence."
        "<h3>Documentation</h3>"
        "<ul><li><a href=\"/documentation/docs-overview.html\" target=\"_blank\"><strong>Documentation Overview</strong></a></li></ul>"
    ),
    openapi_tags=[
        {"name": "Calculation", "description": "Endpoints related to cloud cost calculation."},
        {
            "name": "Pricing Evidence",
            "description": "Read-only access to the pinned thesis price snapshots.",
        },
        {"name": "Validation", "description": "Endpoints for validating optimizer configuration."},
        {"name": "Capabilities", "description": "Provider-layer calculation capability contracts."},
    ],
    lifespan=lifespan
)


# =============================================================================
# Static File Mounts
# =============================================================================

# Documentation (including its css, js, and references subdirectories)
app.mount("/documentation", StaticFiles(directory="docs"), name="docs")


# =============================================================================
# Static Endpoints
# =============================================================================

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("docs/references/favicon.ico")

# =============================================================================
# Include Routers
# =============================================================================

app.include_router(calculation.router)
app.include_router(pricing.router)
app.include_router(validation.router)
app.include_router(capabilities.router)
