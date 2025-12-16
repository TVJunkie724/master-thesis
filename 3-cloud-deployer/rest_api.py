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
from src.api import projects, validation, deployment, status, info, aws_gateway, simulator, credentials, functions

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
    version="1.2",
    description=(
        "API for deploying, destroying, and inspecting Digital Twin environment resources."
        "<h3>🔗 Useful Links</h3>"
        "<h4>📘 Documentation</h4>"
        "<ul><li><a href=\"/documentation/docs-overview.html\" target=\"_blank\"><strong>Documentation Overview</strong></a></li></ul>"
        ),
    openapi_tags=[
        {"name": "Projects", "description": "Endpoints to manage Digital Twin projects (upload, switch, list)."},
        {"name": "Info", "description": "Endpoints to check system status and configurations."},
        {"name": "Deployment", "description": "Endpoints to deploy core and IoT services."},
        {"name": "Destroy", "description": "Endpoints to destroy core and IoT services."},
        {"name": "Status", "description": "Endpoints to inspect the deployment status of all resources."},
        {"name": "AWS", "description": "Endpoints to update and fetch logs from Lambda functions."}
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
app.include_router(aws_gateway.router)
app.include_router(simulator.router)
app.include_router(credentials.router)
app.include_router(functions.router)
