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

from backend.logger import logger
from backend.utils import print_stack_trace, is_file_fresh, get_file_age_string
import backend.constants as CONSTANTS

from backend.fetch_data.calculate_up_to_date_pricing import calculate_up_to_date_pricing
from backend.config_loader import load_config_file, load_json_file, load_combined_pricing
from backend.fetch_data import initial_fetch_aws, initial_fetch_azure, initial_fetch_google
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
        "<ul><li><a href=\"/documentation/docs-overview.html\" target=\"_blank\"><strong>Documentation Overview</strong></a></li></ul>"
    ),
    openapi_tags=[
        # {"name": "WebUI", "description": "Endpoints for serving the web-based user interface."},
        {"name": "Calculation", "description": "Endpoints related to cloud cost calculation."},
        {"name": "Pricing", "description": "Endpoints for fetching cloud service pricing data."},
        {"name": "Regions", "description": "Endpoints for fetching cloud regions."},
        {"name": "File Status", "description": "Endpoints for checking the age of data files."},
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
    
    # New parameters for supporter services
    useEventChecking: bool = False
    triggerNotificationWorkflow: bool = False
    returnFeedbackToDevice: bool = False
    integrateErrorHandling: bool = False
    
    orchestrationActionsPerMessage: int = 3
    eventsPerMessage: int = 1
    apiCallsPerDashboardRefresh: int = 1
    average3DModelSizeInMB: float = 100.0

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
                "entityCount": 1,
                "amountOfActiveEditors": 0,
                "amountOfActiveViewers": 0,
                "dashboardRefreshesPerHour": 2,
                "dashboardActiveHoursPerDay": 0,
                "currency": "USD",
                "useEventChecking": True,
                "triggerNotificationWorkflow": True,
                "returnFeedbackToDevice": False,
                "integrateErrorHandling": True,
                "orchestrationActionsPerMessage": 3,
                "eventsPerMessage": 1,
                "apiCallsPerDashboardRefresh": 1
            }
        }
        
        
# --------------------------------------------------
# UI endpoint
# --------------------------------------------------

app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/json", StaticFiles(directory="json"), name="static-json")
app.mount("/documentation", StaticFiles(directory="docs"), name="docs")
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
# UI Documentation endpoint - REMOVED (Served statically via /documentation)
# --------------------------------------------------

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
        "currency": "USD",
        "useEventChecking": True,
        "triggerNotificationWorkflow": True,
        "returnFeedbackToDevice": False,
        "integrateErrorHandling": True,
        "orchestrationActionsPerMessage": 3,
        "eventsPerMessage": 1,
        "apiCallsPerDashboardRefresh": 1
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

        # We now load combined pricing from separate files
        pricing_data = load_combined_pricing()
        result = calculate_cheapest_costs(params_dict, pricing=pricing_data)
        
        return {"result": result}
    except Exception as e:
        logger.error(f"Error during calculation: {e}")
        print_stack_trace()
        return {"error": str(e)}
    
        
    
@app.post("/api/fetch_pricing/aws", tags=["Pricing"], summary="Fetch AWS Pricing")
def fetch_pricing_aws(additional_debug: bool = False, force_fetch: bool = False):
    """
    Fetches the latest AWS pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the AWS Price List API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for AWS services.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AWS_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached AWS pricing data")
            return load_json_file(CONSTANTS.AWS_PRICING_FILE_PATH)
        
        logger.info("🔄 Fetching fresh AWS pricing...")
        return calculate_up_to_date_pricing("aws", additional_debug)
    except Exception as e:
        logger.error(f"Error fetching AWS pricing: {e}")
        return {"error": str(e)}

@app.post("/api/fetch_pricing/azure", tags=["Pricing"], summary="Fetch Azure Pricing")
def fetch_pricing_azure(additional_debug: bool = False, force_fetch: bool = False):
    """
    Fetches the latest Azure pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the Azure Retail Prices API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for Azure services.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AZURE_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached Azure pricing data")
            return load_json_file(CONSTANTS.AZURE_PRICING_FILE_PATH)
        
        logger.info("🔄 Fetching fresh Azure pricing...")
        return calculate_up_to_date_pricing("azure", additional_debug)
    except Exception as e:
        logger.error(f"Error fetching Azure pricing: {e}")
        return {"error": str(e)}

@app.post("/api/fetch_pricing/gcp", tags=["Pricing"], summary="Fetch GCP Pricing")
def fetch_pricing_gcp(additional_debug: bool = False, force_fetch: bool = False):
    """
    Fetches the latest Google Cloud Platform (GCP) pricing data.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from the Google Cloud Billing API.
    - **additional_debug**: Enables verbose logging during the fetch process.
    
    **Returns**: A JSON object containing the structured pricing data for GCP services.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.GCP_PRICING_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached GCP pricing data")
            return load_json_file(CONSTANTS.GCP_PRICING_FILE_PATH)
        
        logger.info("🔄 Fetching fresh GCP pricing...")
        return calculate_up_to_date_pricing("gcp", additional_debug)
    except Exception as e:
        logger.error(f"Error fetching GCP pricing: {e}")
        return {"error": str(e)}

# --------------------------------------------------
# Region Fetching Endpoints
# --------------------------------------------------

@app.post("/api/fetch_regions/aws", tags=["Regions"], summary="Fetch AWS Regions")
def fetch_regions_aws(force_fetch: bool = False):
    """
    Fetches the latest list of available AWS regions.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from AWS.
    
    **Returns**: A dictionary mapping region codes (e.g., `us-east-1`) to human-readable names (e.g., `US East (N. Virginia)`).
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AWS_REGIONS_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached AWS regions data")
            return load_json_file(CONSTANTS.AWS_REGIONS_FILE_PATH)

        logger.info("🔄 Fetching fresh AWS regions...")
        return initial_fetch_aws.fetch_region_map(force_update=True)
    except Exception as e:
        logger.error(f"Error fetching AWS regions: {e}")
        return {"error": str(e)}

@app.post("/api/fetch_regions/azure", tags=["Regions"], summary="Fetch Azure Regions")
def fetch_regions_azure(force_fetch: bool = False):
    """
    Fetches the latest list of available Azure regions.
    
    - **Cache Duration**: 7 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from Azure.
    
    **Returns**: A dictionary mapping region codes (e.g., `westeurope`) to human-readable names (e.g., `West Europe`).
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.AZURE_REGIONS_FILE_PATH, max_age_days=7):
            logger.info("✅ Using cached Azure regions data")
            return load_json_file(CONSTANTS.AZURE_REGIONS_FILE_PATH)

        logger.info("🔄 Fetching fresh Azure regions...")
        return initial_fetch_azure.fetch_region_map(force_update=True)
    except Exception as e:
        logger.error(f"Error fetching Azure regions: {e}")
        return {"error": str(e)}

@app.post("/api/fetch_regions/gcp", tags=["Regions"], summary="Fetch GCP Regions")
def fetch_regions_gcp(force_fetch: bool = False):
    """
    Fetches the latest list of available Google Cloud regions.
    
    ---------------
    - **`WARNING`**: fetching GCP regions takes about 5-10 minutes!!!!!
    ---------------
    
    - **Cache Duration**: 30 days.
    - **force_fetch**: If `true`, ignores the local cache and fetches fresh data from GCP.
    
    **Returns**: A dictionary mapping region codes (e.g., `us-central1`) to human-readable names.
    """
    try:
        if not force_fetch and is_file_fresh(CONSTANTS.GCP_REGIONS_FILE_PATH, max_age_days=30):
            logger.info("✅ Using cached GCP regions data")
            return load_json_file(CONSTANTS.GCP_REGIONS_FILE_PATH)

        logger.info("🔄 Fetching fresh GCP regions...")
        return initial_fetch_google.fetch_region_map(force_update=True)
    except Exception as e:
        logger.error(f"Error fetching GCP regions: {e}")
        return {"error": str(e)}

# --------------------------------------------------
# File Age Endpoints
# --------------------------------------------------

@app.get("/api/regions_age/aws", tags=["File Status"], summary="Get AWS Regions File Age")
def get_regions_age_aws():
    """
    Returns the age of the local AWS regions data file.
    
    **Returns**: A JSON object with the `age` string (e.g., "2 days", "5 hours").
    """
    return {"age": get_file_age_string(CONSTANTS.AWS_REGIONS_FILE_PATH)}

@app.get("/api/regions_age/azure", tags=["File Status"], summary="Get Azure Regions File Age")
def get_regions_age_azure():
    """
    Returns the age of the local Azure regions data file.
    
    **Returns**: A JSON object with the `age` string.
    """
    return {"age": get_file_age_string(CONSTANTS.AZURE_REGIONS_FILE_PATH)}

@app.get("/api/regions_age/gcp", tags=["File Status"], summary="Get GCP Regions File Age")
def get_regions_age_gcp():
    """
    Returns the age of the local GCP regions data file.
    
    **Returns**: A JSON object with the `age` string.
    """
    return {"age": get_file_age_string(CONSTANTS.GCP_REGIONS_FILE_PATH)}

@app.get("/api/pricing_age/aws", tags=["File Status"], summary="Get AWS Pricing File Status")
def get_pricing_age_aws():
    """
    Checks the age and validity of the local AWS pricing data file.
    
    **Returns**:
    - **age**: Time since last update (e.g., "3 days").
    - **status**: Validation status (`valid`, `incomplete`, `missing`, `error`).
    - **missing_keys**: List of missing service keys if status is `incomplete`.
    """
    age = get_file_age_string(CONSTANTS.AWS_PRICING_FILE_PATH)
    status = "missing"
    missing_keys = []
    
    if os.path.isfile(CONSTANTS.AWS_PRICING_FILE_PATH):
        try:
            from backend.pricing_utils import validate_pricing_schema
            data = load_json_file(CONSTANTS.AWS_PRICING_FILE_PATH)
            validation = validate_pricing_schema("aws", data)
            status = validation["status"]
            missing_keys = validation["missing_keys"]
        except Exception as e:
            logger.error(f"Failed to validate AWS pricing: {e}")
            status = "error"
            
    return {
        "age": age,
        "status": status,
        "missing_keys": missing_keys
    }

@app.get("/api/pricing_age/azure", tags=["File Status"], summary="Get Azure Pricing File Status")
def get_pricing_age_azure():
    """
    Checks the age and validity of the local Azure pricing data file.
    
    **Returns**:
    - **age**: Time since last update.
    - **status**: Validation status (`valid`, `incomplete`, `missing`, `error`).
    - **missing_keys**: List of missing service keys if status is `incomplete`.
    """
    age = get_file_age_string(CONSTANTS.AZURE_PRICING_FILE_PATH)
    status = "missing"
    missing_keys = []
    
    if os.path.isfile(CONSTANTS.AZURE_PRICING_FILE_PATH):
        try:
            from backend.pricing_utils import validate_pricing_schema
            data = load_json_file(CONSTANTS.AZURE_PRICING_FILE_PATH)
            validation = validate_pricing_schema("azure", data)
            status = validation["status"]
            missing_keys = validation["missing_keys"]
        except Exception as e:
            logger.error(f"Failed to validate Azure pricing: {e}")
            status = "error"
            
    return {
        "age": age,
        "status": status,
        "missing_keys": missing_keys
    }

@app.get("/api/pricing_age/gcp", tags=["File Status"], summary="Get GCP Pricing File Status")
def get_pricing_age_gcp():
    """
    Checks the age and validity of the local GCP pricing data file.
    
    **Returns**:
    - **age**: Time since last update.
    - **status**: Validation status (`valid`, `incomplete`, `missing`, `error`).
    - **missing_keys**: List of missing service keys if status is `incomplete`.
    """
    age = get_file_age_string(CONSTANTS.GCP_PRICING_FILE_PATH)
    status = "missing"
    missing_keys = []
    
    if os.path.isfile(CONSTANTS.GCP_PRICING_FILE_PATH):
        try:
            from backend.pricing_utils import validate_pricing_schema
            data = load_json_file(CONSTANTS.GCP_PRICING_FILE_PATH)
            validation = validate_pricing_schema("gcp", data)
            status = validation["status"]
            missing_keys = validation["missing_keys"]
        except Exception as e:
            logger.error(f"Failed to validate GCP pricing: {e}")
            status = "error"
            
    return {
        "age": age,
        "status": status,
        "missing_keys": missing_keys
    }

@app.get("/api/currency_age", tags=["File Status"], summary="Get Currency File Age")
def get_currency_age():
    """
    Returns the age of the local currency conversion rates file.
    
    **Returns**: A JSON object with the `age` string.
    """
    return {"age": get_file_age_string(CONSTANTS.CURRENCY_CONVERSION_FILE_PATH)}

@app.post("/api/fetch_currency", tags=["Pricing"], summary="Fetch Currency Rates")
def fetch_currency_rates():
    """
    Fetches up-to-date currency exchange rates (USD/EUR).
    
    - **Cache Duration**: 1 day.
    
    **Returns**: A dictionary of currency rates (e.g., `{"USD": 1.0, "EUR": 0.92}`).
    """
    try:
        from backend import pricing_utils
        logger.info("🔄 Fetching fresh currency rates...")
        rates = pricing_utils.get_currency_rates()
        return rates
    except Exception as e:
        logger.error(f"Error fetching currency rates: {e}")
        return {"error": str(e)}
