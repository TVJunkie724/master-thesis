import sys
import io
import subprocess
import json
import os
from enum import Enum

from fastapi import FastAPI, Body, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from py.logger import logger
import py.fetch_data.fetch_aws_pricing as aws_fetch
import py.fetch_data.fetch_azure_pricing as azure_fetch
import py.fetch_data.fetch_google_pricing as gcp_fetch

import py.fetch_data.initial_fetch_aws as aws_fetch_initial
import py.fetch_data.initial_fetch_azure as azure_fetch_initial
import py.fetch_data.initial_fetch_google as gcp_fetch_initial
from py.config_loader import load_config_file, load_json_file

def create_enum(name: str, values: list[str]) -> type[Enum]:
    """Dynamically create an Enum for Swagger dropdowns."""
    if not values:
        values = ["N/A"]
    return Enum(name, {v: v for v in values})

def load_api_config():
    global AWS_REGION_MAP, AWS_SERVICE_CODES, AZURE_REGION_MAP, AZURE_SERVICE_CODES, GCP_REGIONS, GCP_SERVICES
    global AwsRegionEnum, AwsServiceEnum, AzureRegionEnum, AzureServiceEnum, GcpRegionEnum, GcpServiceEnum

    config = {}
    try:
        logger.info("🚀 Starting Twin2Clouds API...")
        config = load_config_file()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    twin2clouds_config = config.get("twin2clouds", {})
        
    fetch_aws_anew = twin2clouds_config.get("fetch_aws_data_anew", False)
    fetch_azure_anew = twin2clouds_config.get("fetch_azure_data_anew", False)
    fetch_gcp_anew = twin2clouds_config.get("fetch_gcp_data_anew", False)
    
    # Prepare service and region dropdowns for Swagger
    print("\n")
    if fetch_aws_anew:
        logger.info("---------------------------------------------------")
        logger.info("🔄 Fetching AWS pricing data anew...")
        AWS_REGION_MAP = aws_fetch_initial.fetch_region_map()
        AWS_SERVICE_CODES = aws_fetch_initial.fetch_aws_service_codes()
    else:
        AWS_REGION_MAP = aws_fetch.load_aws_regions_file()
        AWS_SERVICE_CODES = aws_fetch.load_aws_service_codes_file()    
    
    # print("\n")
    # if fetch_azure_anew:
    #     logger.info("---------------------------------------------------")
    #     logger.info("🔄 Fetching Azure pricing data anew...")
    #     AZURE_REGION_MAP = azure_fetch_initial.fetch_azure_regions()
    #     AZURE_SERVICE_CODES = azure_fetch_initial.fetch_azure_service_names()
    #     print(AZURE_SERVICE_CODES)
    # else:
    #     AZURE_REGION_MAP = azure_fetch.load_azure_regions_file()
    #     AZURE_SERVICE_CODES = azure_fetch.load_azure_service_names_file()
        
    print("\n")
    if fetch_gcp_anew:
        logger.info("---------------------------------------------------")
        logger.info("🔄 Fetching GCP pricing data anew...")
        GCP_REGIONS = gcp_fetch_initial.fetch_gcp_regions()
        GCP_SERVICES = gcp_fetch_initial.fetch_gcp_services()
    else:
        GCP_REGIONS = gcp_fetch.load_gcp_regions_file()
        GCP_SERVICES = gcp_fetch.load_gcp_service_names_file()

    print("\n")
    # TODO add filter from config file


    # ✅ Create Enums dynamically for Swagger dropdowns
    AwsRegionEnum = create_enum("AwsRegionEnum", list(AWS_REGION_MAP.keys()))
    AwsServiceEnum = create_enum("AwsServiceEnum", list(AWS_SERVICE_CODES.keys()))
    # AzureRegionEnum = create_enum("AzureRegionEnum", list(AZURE_REGION_MAP.keys()))
    # AzureServiceEnum = create_enum("AzureServiceEnum", list(AZURE_SERVICE_CODES.values()))
    GcpRegionEnum = create_enum("GcpRegionEnum", list(GCP_REGIONS.keys()))
    GcpServiceEnum = create_enum("GcpServiceEnum", list(GCP_SERVICES.keys()))



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
    ),
    openapi_tags=[
        {"name": "WebUI", "description": "Endpoints for serving the web-based user interface."},
        {"name": "Calculation", "description": "Endpoints related to cloud cost calculation."},
        {"name": "Pricing", "description": "Endpoints for fetching cloud service pricing data."},
    ] 
)

# --------- Initialize configuration once ----------
@app.on_event("startup")
def startup_event():
    logger.info("✅ API ready.")
    
    
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
@app.get(
    "/ui",
    tags=["WebUI"],
    summary="Serve the Web Interface",
    description=(
        "Returns the main **index.html** file that serves as the graphical interface "
        "for Twin2Clouds. This page allows users to configure digital twin scenarios "
        "and trigger cloud cost calculations through the API."
    ),
    response_description="The index.html web interface file."
)
def serve_ui():
    return FileResponse("index.html")


# Serve static assets (JavaScript and CSS)
app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/pricing", StaticFiles(directory="pricing"), name="static-pricing")


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
    
@app.put("/api/calculate", tags=["Calculation"])
def fetch_aws_iot_core():
    result = subprocess.run(
        ["node", "js/fetch_data/fetch_aws.js", "fetchIoTCorePricing"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    try:
        return {"result": json.loads(result.stdout.strip())}
    except Exception:
        return {"raw_output on error": result.stdout.strip()}
    

# --------------------------------------------------
# Pricing endpoints
# --------------------------------------------------
@app.get("/api/pricing_aws", tags=["Pricing"], summary="Get AWS Service Pricing",)
def get_aws_pricing(
        service_code: AwsServiceEnum = Query(..., description="AWS service"),
        region_code: AwsRegionEnum = Query("eu-central-1", description="AWS region"),
    ):
    logger.info(f"Fetching pricing for service: {service_code}, region: {region_code}")
    try:
        if service_code not in AWS_SERVICE_CODES or region_code not in AWS_REGION_MAP:
            return {"error": "Invalid service or region"}
        
        service = AWS_SERVICE_CODES[service_code]
        region = AWS_REGION_MAP[region_code]
        
        return aws_fetch.fetch_aws_pricing(service, region)
    except Exception as e:
        logger.error(f"Error fetching AWS pricing for service '{service_code}' in region '{region_code}': {e}")
        return {"error": str(e)}



@app.get("/api/pricing_azure", tags=["Pricing"], summary="Get Azure Service Pricing")
def get_azure_pricing(
        service_name: str = Query(..., description="Azure Service Name"),
        region_name: str = Query(..., description="Azure Region Name"),
    ):
    """
    Retrieve the retail (pay-as-you-go) price for a given Azure service in a specific region.
    """
    try:
        return azure_fetch.fetch_azure_pricing(service_name, region_name)
    except Exception as e:
        logger.error(f"Error fetching Azure pricing for {service_name} in {region_name}: {e}")
        return {"error": str(e)}
    


@app.get("/api/pricing_google", 
         summary="Get GCP Service Pricing", 
         description="Fetch Google Cloud service pricing for a given service and region.",
         tags=["Pricing"])
def get_gcp_pricing(
        service_id: GcpServiceEnum = Query(..., description="GCP Service ID"),
        region_id: GcpRegionEnum = Query(..., description="GCP Region ID"),
    ):
    logger.info(f"Fetching pricing for service: {service_id}, region: {region_id}")
    try:
        if service_id not in GCP_SERVICES or region_id not in GCP_REGIONS:
            return {"error": "Invalid service or region"}
        logger.info(f"Fetching GCP pricing for service={service_id}, region={region_id}")
        return gcp_fetch.fetch_gcp_pricing(service_id, region_id)
    except Exception as e:
        logger.error(f"Error fetching GCP pricing for service '{service_id}' in region '{region_id}': {e}")
        return {"error": str(e)}