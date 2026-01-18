"""
Digital Twin Manager REST API.

This is the main FastAPI application entry point.
Uses lazy imports for globals to support the new provider pattern.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from logger import logger

import src.core.state as state

# Import API routers
from src.api import projects, validation, deployment, status, info, simulator, credentials, functions

# --------- Lifespan context manager ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"API Startup. Active Project: {state.get_active_project()}")
    yield
    # Shutdown

# --------- Initialize FastAPI app ----------
app = FastAPI(
    title="Digital Twin Manager API",
    version="2.0",
    description=(
        "API for deploying, destroying, and inspecting Digital Twin environment resources."
        "<h3>🔗 Useful Links</h3>"
        "<h4>📘 Documentation</h4>"
        "<ul><li><a href=\"/documentation/docs-overview.html\" target=\"_blank\"><strong>Documentation Overview</strong></a></li></ul>"
        ),
    openapi_tags=[
        {
            "name": "Projects", 
            "description": "Project lifecycle management: upload, configure, validate, delete. "
                          "Includes config retrieval, simulator download, and AWS TwinMaker cleanup."
        },
        {
            "name": "Infrastructure", 
            "description": "Infrastructure deployment and status. Deploy/destroy cloud resources "
                          "across all 5 layers (L1-L5) with Terraform. Check deployment status."
        },
        {
            "name": "Validation", 
            "description": "Pre-deployment validation endpoints. Validate project zip structure, "
                          "config files, function code, state machines, and simulator payloads."
        },
        {
            "name": "Permissions - Upload", 
            "description": "Verify cloud provider permissions from request body. "
                          "Tests AWS/Azure/GCP credentials before deployment."
        },
        {
            "name": "Permissions - Project", 
            "description": "Verify cloud provider permissions from project config. "
                          "Reads credentials from project's config_credentials.json."
        },
        {
            "name": "Functions", 
            "description": "User function management. List updatable functions (event actions, "
                          "processors, feedback) and update function code via SDK."
        }
    ],
    lifespan=lifespan
)

app.mount("/documentation", StaticFiles(directory="docs"), name="docs")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("docs/references/favicon.ico")

# Include Routers
app.include_router(info.router)
app.include_router(projects.router)
app.include_router(validation.router)
app.include_router(deployment.router)
app.include_router(status.router)
app.include_router(simulator.router)
app.include_router(credentials.router)
app.include_router(functions.router)
