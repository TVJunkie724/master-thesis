"""
Digital Twin Manager REST API.

This is the main FastAPI application entry point.
Uses lazy imports for globals to support the new provider pattern.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from logger import logger
from src.api.error_handling import internal_server_error

# Import API routers
from src.api import (
    capabilities,
    credentials,
    deployment,
    functions,
    info,
    logs,
    projects,
    simulator,
    status,
    validation,
    verify,
)

# --------- Lifespan context manager ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("API Startup.")
    yield
    # Shutdown

# --------- Initialize FastAPI app ----------
app = FastAPI(
    title="Digital Twin Manager API",
    version="2.0",
    description="Internal API for deploying, destroying, and inspecting Digital Twin resources.",
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
            "description": "Debug/local-cloud only. Verify cloud provider permissions "
                          "from project config when ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS=true."
        },
        {
            "name": "Functions", 
            "description": "User function management. List updatable functions (event actions, "
                          "processors, feedback) and update function code via SDK."
        }
    ],
    lifespan=lifespan
)


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Fail closed for exceptions that escape every route boundary."""
    error = internal_server_error(f"{request.method} request", exc)
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail},
    )


app.add_exception_handler(Exception, unhandled_exception_handler)

# Include Routers
app.include_router(info.router)
app.include_router(projects.router)
app.include_router(validation.router)
app.include_router(deployment.router)
app.include_router(status.router)
app.include_router(simulator.router)
app.include_router(credentials.router)
app.include_router(functions.router)
app.include_router(logs.router)
app.include_router(verify.router)
app.include_router(capabilities.router)
