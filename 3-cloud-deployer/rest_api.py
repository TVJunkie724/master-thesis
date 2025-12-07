from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

import globals
import aws.globals_aws as globals_aws
from logger import logger

# Import API routers
from api import projects, validation, deployment, status, info, aws_gateway

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
    ]
)

app.mount("/documentation", StaticFiles(directory="docs"), name="docs")

# --------- Initialize configuration once ----------
@app.on_event("startup")
def startup_event():
    globals.initialize_all()
    globals_aws.initialize_aws_clients()
    
    logger.info("✅ Globals initialized. API ready.")

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
