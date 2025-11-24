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

from backend.logger import logger
from backend.utils import print_stack_trace
import backend.constants as CONSTANTS

from backend.calculate_up_to_date_pricing import calculate_up_to_date_pricing
from backend.config_loader import load_config_file, load_json_file


def load_api_config():

    config = {}
    try:
        print("")
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
    currency: str = "USD" # Default to USD, can be "EUR"

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
                "dashboardActiveHoursPerDay": 0,
                "currency": "USD"
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
        "processes them through the Python calculation engine, and returns "
        "the calculated cost breakdown for AWS, Azure, and GCP, along with the optimal provider "
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
                                "L1": "GCP",
                                "L2": {"Hot": "AWS", "Cool": "GCP", "Archive": "AWS"},
                                "L3": "AWS",
                                "L4": "GCP",
                                "L5": "GCP"
                            },
                            "awsCosts": "...",
                            "azureCosts": "...",
                            "gcpCosts": "...",
                            "cheapestPath": ["L1_GCP", "L2_AWS_Hot", "L2_GCP_Cool", "L2_AWS_Archive", "L3_AWS", "L4_GCP", "L5_GCP"]
                        }
                    }
                }
            },
        },
        400: {"description": "Invalid input parameters."},
        500: {"description": "Internal error during cost calculation."},
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
        "dashboardActiveHoursPerDay": 8,
        "currency": "USD"
    }
)):
    """
    Perform a cloud cost optimization calculation based on Digital Twin configuration parameters.
    """
    try:
        from backend.calculation.engine import calculate_cheapest_costs
        
        # Convert Pydantic model to dict
        params_dict = params.dict()
        
        # Calculate costs using Python engine
        result = calculate_cheapest_costs(params_dict)
        
        return {"result": result}
    except Exception as e:
        logger.error(f"Error during calculation: {e}")
        print_stack_trace()
        return {"error": str(e)}
    
        
    
@app.get(
    "/api/fetch_up_to_date_pricing", 
    tags=["Pricing"], 
    summary="Fetch Up-to-Date Cloud Pricing",
    description=(
        "Triggers the pricing fetcher to retrieve the latest cloud service pricing from AWS, Azure, and GCP. "
        "This endpoint fetches dynamic pricing from cloud provider APIs where available, and uses static defaults "
        "for services that don't have accessible pricing APIs.\n\n"
        "**Process:**\n"
        "1. Fetches AWS pricing using boto3 Pricing API\n"
        "2. Fetches Azure pricing using Azure Retail Prices API\n"
        "3. Uses GCP static defaults (dynamic fetching to be implemented)\n"
        "4. Saves results to `pricing/fetched_data/pricing_dynamic.json`\n\n"
        "**Parameters:**\n"
        "- `additional_debug` (optional): Enable verbose debug logging for pricing fetcher operations"
    ),
    response_description="The complete pricing schema for all three cloud providers",
    responses={
        200: {
            "description": "Successfully fetched and saved pricing data.",
            "content": {
                "application/json": {
                    "example": {
                        "aws": {"transfer": "...", "iot": "...", "functions": "..."},
                        "azure": {"transfer": "...", "iotHub": "...", "functions": "..."},
                        "gcp": {"transfer": "...", "iot": "...", "functions": "..."}
                    }
                }
            }
        },
        500: {"description": "Error during pricing fetch operation."}
    }
)
def fetch_up_to_date_pricing_endpoint(additional_debug: bool = False):
    """
    Trigger the calculation of up-to-date cloud pricing across AWS, Azure, and GCP.
    This function loads the latest pricing data and saves it to pricing_dynamic.json.
    Pricing is only re-fetched if the existing file is older than 7 days.
    """
    try:
        from backend.utils import is_file_fresh
        
        # Check if we have a fresh pricing file (< 7 days old)
        if is_file_fresh(CONSTANTS.DYNAMIC_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached pricing data (less than 7 days old)")
            fetched_pricing_result = load_json_file(CONSTANTS.DYNAMIC_PRICING_FILE_PATH)
            return fetched_pricing_result
        
        # File is stale or doesn't exist, fetch new pricing
        logger.info("🔄 Fetching fresh pricing data from cloud providers...")
        calculate_up_to_date_pricing(additional_debug)
        fetched_pricing_result = load_json_file(CONSTANTS.DYNAMIC_PRICING_FILE_PATH)
        return fetched_pricing_result
    except Exception as e:
        logger.error(f"Error during up-to-date pricing calculation: {e}")
        print_stack_trace()
        return {"error": str(e)}

    
