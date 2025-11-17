import sys
import io
import subprocess
import json
import os
from enum import Enum

from fastapi import FastAPI, Body
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from py.logger import logger
from py.utils import print_stack_trace
import py.constants as CONSTANTS

from py.calculate_up_to_date_pricing import calculate_up_to_date_pricing
from py.config_loader import load_config_file, load_json_file


def load_api_config():

    config = {}
    try:
        logger.info("🚀 Starting Twin2Clouds API...")
        config = load_config_file()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    twin2clouds_config = config.get("twin2clouds", {})
          
load_api_config()

# ----------- FastAPI app initialization -----------
app = FastAPI(
    title="twin2clouds REST API",
    version="1.1",
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
        "<ul><li><a href=\"/documentation/overview\" target=\"_blank\"><strong>Documentation Overview</strong></a></li></ul>"
    ),
    openapi_tags=[
        # {"name": "WebUI", "description": "Endpoints for serving the web-based user interface."},
        {"name": "Calculation", "description": "Endpoints related to cloud cost calculation."},
        {"name": "Pricing", "description": "Endpoints for fetching cloud service pricing data."},
    ] 
)

@app.on_event("startup")
def startup_event():
    logger.info("✅ API ready.")
    
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("references/favicon.ico")

    
# --------------------------------------------------
# Input model for calculation
# --------------------------------------------------
class CalcParams(BaseModel):
    """
    Defines the parameters for calculating the cost-optimized Digital Twin deployment.
    """
    numberOfDevices: int
    deviceSendingIntervalInMinutes: float
    averageSizeOfMessageInKb: float
    hotStorageDurationInMonths: int
    coolStorageDurationInMonths: int
    archiveStorageDurationInMonths: int
    needs3DModel: bool
    entityCount: int
    amountOfActiveEditors: int
    amountOfActiveViewers: int
    dashboardRefreshesPerHour: int
    dashboardActiveHoursPerDay: int

    class Config:
        json_schema_extra = {
            "example": {
                "numberOfDevices": 100,
                "deviceSendingIntervalInMinutes": 2,
                "averageSizeOfMessageInKb": 0.25,
                "hotStorageDurationInMonths": 1,
                "coolStorageDurationInMonths": 3,
                "archiveStorageDurationInMonths": 12,
                "needs3DModel": False,
                "entityCount": 0,
                "amountOfActiveEditors": 0,
                "amountOfActiveViewers": 0,
                "dashboardRefreshesPerHour": 2,
                "dashboardActiveHoursPerDay": 0
            }
        }
        
        
# --------------------------------------------------
# UI endpoint
# --------------------------------------------------

app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/pricing", StaticFiles(directory="pricing"), name="static-pricing")
app.mount("/docs", StaticFiles(directory="docs"), name="docs")
app.mount("/references", StaticFiles(directory="references"), name="references")


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
    return FileResponse("index.html")

# --------------------------------------------------
# UI Documentation endpoint

@app.get(
    "/documentation/overview",
    tags=["WebUI"],
    summary="Documentation Overview", include_in_schema=False,
    description=(
        "Serves the **Twin2Clouds Documentation Overview** page.<br><br>"
        "📘 <a href='/documentation/overview' target='_blank'>Open Documentation Overview in a new tab</a><br><br>"
        "Provides navigation to AWS, Azure, and Google Cloud pricing schema documentation "
        "as well as cost formula definitions."
    ),
)
def serve_docs_overview():
    return FileResponse("docs/docs-overview.html")


@app.get(
    "/documentation/aws_pricing",
    tags=["WebUI"],
    summary="AWS Pricing Schema Documentation", include_in_schema=False,
    description=(
        "Serves the **AWS Pricing Documentation** page describing how each AWS service "
        "price is fetched, calculated, or set as static.<br><br>"
        "📘 <a href='/documentation/aws_pricing' target='_blank'>Open AWS Pricing Documentation in a new tab</a>"
    ),
)
def serve_docs_aws():
    return FileResponse("docs/docs-aws-pricing.html")


@app.get(
    "/documentation/formulas",
    tags=["WebUI"],
    summary="Formulas and Service Mapping Documentation", include_in_schema=False,
    description=(
        "Serves the **Formulas Documentation** page detailing all cost calculation formulas, "
        "parameter definitions, and mapping between services and cost model formulas.<br><br>"
        "📘 <a href='/documentation/formulas' target='_blank'>Open Formulas Documentation in a new tab</a>"
    ),
)
def serve_docs_formulas():
    return FileResponse("docs/docs-formulas.html")

# --------------------------------------------------
# Calculation endpoint
# --------------------------------------------------
@app.put(
    "/api/calculate",
    tags=["Calculation"],
    summary="Calculate Cloud Costs and Determine Cheapest Provider Setup",
    description=(
        "This endpoint receives a complete set of **Digital Twin scenario parameters**, "
        "passes them to the Node.js computation module (`cost_calculation.js`), and returns "
        "the calculated cost breakdown for AWS and Azure, along with the optimal provider "
        "per architectural layer (L1–L5)."
        "\n"
        "**Layers overview:**\n"
        "- **L1:** IoT Data Acquisition & Processing\n"
        "- **L2:** Storage (Hot, Cool, Archive)\n"
        "- **L3:** Data Processing & Integration\n"
        "- **L4:** Twin Management (3D model)\n"
        "- **L5:** Data Visualization (Dashboards)"
    ),
    response_description="JSON object containing cost breakdowns and cheapest provider path.",
    responses={
        200: {
            "description": "Successful calculation of costs and cheapest cloud configuration.",
            "content": {
                "application/json": {
                    "example": {
                        "result": {
                            "calculationResult": {
                                "L1": "AWS",
                                "L2": {"Hot": "AWS", "Cool": "Azure", "Archive": "Azure"},
                                "L3": "Azure",
                                "L4": "AWS",
                                "L5": "Azure"
                            },
                            "awsCosts": "...",
                            "azureCosts": "...",
                            "cheapestPath": ["L1_AWS", "L2_Azure_Hot", "L2_Azure_Cool", "L2_Azure_Archive", "L3_Azure", "L4_AWS", "L5_Azure"]
                        }
                    }
                }
            },
        },
        400: {"description": "Invalid input parameters."},
        500: {"description": "Internal error during cost calculation or Node script execution."},
    },
)

def calc(params: CalcParams = Body(
    ...,
    example={
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 2,
        "amountOfActiveViewers": 10,
        "dashboardRefreshesPerHour": 4,
        "dashboardActiveHoursPerDay": 8
    }
)):
    """
    Perform a cloud cost optimization calculation based on Digital Twin configuration parameters.
    """
    payload = json.dumps(params.dict())

    result = subprocess.run(
        ["node", "js/calculation/cost_calculation.js", "calculateCheapestCostsFromApiCall", payload],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    try:
        return {"result": json.loads(result.stdout.strip())}
    except Exception:
        return {"raw_output on error": result.stdout.strip()}
    
        
    
@app.get("/api/fetch_up_to_date_pricing", tags=["Pricing"], summary="Fetch Up-to-Date Cloud Pricing")
def fetch_up_to_date_pricing_endpoint(additional_debug: bool = False):
    """
    Trigger the calculation of up-to-date cloud pricing across AWS, Azure, and GCP.
    This function loads the latest pricing data and computes costs based on predefined workloads.
    """
    try:
        calculate_up_to_date_pricing(additional_debug)
        fetched_pricing_result = load_json_file(CONSTANTS.DYNAMIC_PRICING_FILE_PATH)
        return fetched_pricing_result
    except Exception as e:
        logger.error(f"Error during up-to-date pricing calculation: {e}")
        print_stack_trace()
        return {"error": str(e)}
    
