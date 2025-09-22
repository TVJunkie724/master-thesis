<<<<<<< HEAD
import json
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
import os
import sys 
import traceback

import globals
import aws.globals_aws as globals_aws
import deployers.core_deployer as core_deployer
import deployers.iot_deployer as iot_deployer
import info
import deployers.additional_deployer as hierarchy_deployer
import deployers.event_action_deployer as event_action_deployer
import aws.lambda_manager as lambda_manager
from aws.api_lambda_schemas import LambdaUpdateRequest, LambdaLogsRequest
from util import pretty_json

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

logger = None

# --------- Initialize FastAPI app ----------
app = FastAPI(
    title="Digital Twin Manager API",
    version="1.1",
    description="API for deploying, destroying, and inspecting Digital Twin environment resources.",
    openapi_tags=[
        {"name": "Info", "description": "Endpoints to check system status and configurations."},
        {"name": "Deployment", "description": "Endpoints to deploy or destroy core and IoT services."},
        {"name": "Status", "description": "Endpoints to inspect the deployment status of all layers and configured resources."},
        {"name": "AWS", "description": "Endpoints to update and fetch logs from Lambda functions."}
    ]
)

# --------- Initialize configuration once ----------
@app.on_event("startup")
def startup_event():
    globals.initialize_all()
    globals_aws.initialize_aws_clients()
    
    global logger
    logger = globals.logger
    
    
    logger.info("✅ Globals initialized. API ready.")


# --------- Root endpoint ----------
@app.get("/", tags=["Info"])
def read_root():
    """
    Check if the API is running.
    """
    return {"status": "API is running"}


# --------- Core + IoT Deploy/Destroy ----------
# Core and IoT deployment
@app.post("/deploy", tags=["Deployment"])
def deploy_all(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """
    Deploys the full digital twin environment including IoT devices, processors, and TwinMaker components.

    Steps performed:
    - Level 1 (L1): Creates IoT Things, certificates, and IoT policies for all configured devices.
    - Level 2 (L2): Creates IAM roles and Lambda functions for processors.
    - Level 4 (L4): Creates TwinMaker component types for each IoT device.

    Returns:
        JSON message confirming deployment started or completed.
    """
    try:
        provider = provider.lower()
        core_deployer.deploy(provider)
        iot_deployer.deploy(provider)
        hierarchy_deployer.deploy(provider)
        event_action_deployer.deploy(provider)
        return {"message": "Core and IoT services deployed successfully"}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/destroy", tags=["Deployment"])
def destroy_all(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """
    Destroys the full digital twin environment including IoT devices, processors, and TwinMaker components.

    Steps performed:
    - Level 4 (L4): Deletes TwinMaker component types for all IoT devices.
    - Level 2 (L2): Deletes processor Lambda functions and IAM roles.
    - Level 1 (L1): Deletes IoT Things, certificates, and IoT policies.

    Returns:
        JSON message confirming destruction started or completed.
    """
    try:
        provider = provider.lower()
        event_action_deployer.destroy(provider),
        hierarchy_deployer.destroy(provider),
        iot_deployer.destroy(provider), 
        core_deployer.destroy(provider)
        return {"message": "Core and IoT services destroyed successfully"}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deploy_l1", tags=["Deployment"])
def deploy_l1_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """
    Deploy Level 1 (L1) – IoT Dispatcher Layer.

    Actions performed:
    - Creates IAM role for dispatcher Lambda function.
    - Deploys dispatcher Lambda function.
    - Configures IoT topic rule to forward IoT device data to Lambda.
    
    Returns:
        JSON message confirming L1 deployment.
    """
    try:
        provider = provider.lower()
        core_deployer.deploy_l1(provider)
        return {"message": "L1 deployment (IoT Dispatcher Layer) completed successfully."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deploy_l2", tags=["Deployment"])
def deploy_l2_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """
    Deploy Level 2 (L2) – Persister / Processor Layer.

    Actions performed:
    - Creates IAM role for persister Lambda function.
    - Deploys persister Lambda function to process and store IoT data.
    
    Returns:
        JSON message confirming L2 deployment.
    """
    try:
        provider = provider.lower()
        core_deployer.deploy_l2(provider)
        return {"message": "L2 deployment (Persister Layer) completed successfully."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deploy_l3", tags=["Deployment"])
def deploy_l3_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """
    Deploy Level 3 (L3) – Storage Layers.

    Actions performed:
    - Hot Storage:
        - Creates DynamoDB table for IoT device data.
        - Creates IAM role and Lambda function to move hot data to cold storage.
        - Schedules hot-to-cold data mover via EventBridge.
    - Cold Storage:
        - Creates S3 bucket for cold storage.
        - Creates IAM role and Lambda function to move cold data to archive.
        - Schedules cold-to-archive mover via EventBridge.
    - Archive Storage:
        - Creates S3 bucket for archive storage.
    
    Returns:
        JSON message confirming L3 deployment (hot, cold, archive).
    """
    try:
        provider = provider.lower()
        core_deployer.deploy_l3_hot(provider)
        core_deployer.deploy_l3_cold(provider)
        core_deployer.deploy_l3_archive(provider)
        return {"message": "L3 deployment (Hot, Cold, Archive Storage) completed successfully."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deploy_l4", tags=["Deployment"])
def deploy_l4_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """
    Deploy Level 4 (L4) – TwinMaker Layer.

    Actions performed:
    - Creates S3 bucket for TwinMaker assets.
    - Creates IAM role for TwinMaker workspace.
    - Creates TwinMaker workspace.
    - Creates IAM role and Lambda connector for TwinMaker.
    
    Returns:
        JSON message confirming L4 deployment.
    """
    try:
        provider = provider.lower()
        core_deployer.deploy_l4(provider)
        return {"message": "L4 TwinMaker deployment completed successfully."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/deploy_l5", tags=["Deployment"])
def deploy_l5_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """
    Deploy Level 5 (L5) – Visualization Layer.

    Actions performed:
    - Creates IAM role for Grafana.
    - Creates Grafana workspace.
    - Configures CORS for TwinMaker S3 bucket to allow Grafana access.
    
    Returns:
        JSON message confirming L5 deployment.
    """
    try:
        provider = provider.lower()
        core_deployer.deploy_l5(provider)
        return {"message": "L5 Grafana deployment completed successfully."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


# --------- Check/Info Deployment Status ----------
@app.get("/check", tags=["Status"])
def check_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """
    Runs all checks (L1 to L5) for the specified provider.

    Returns:
        JSON message indicating the system check was executed.
    """
    try:
        provider = provider.lower()
        info.check(provider)
        hierarchy_deployer.info(provider),
        event_action_deployer.info(provider)
        return {"message": f"System check (all layers) completed for provider '{provider}'. See logs for detailed status."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


# Individual layer check endpoints
@app.get("/check_l1", tags=["Status"])
def check_l1_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """Check Level 1 (IoT Dispatcher Layer) for the specified provider."""
    try:
        provider = provider.lower()
        info.check_l1(provider)
        return {"message": f"Check L1 completed for provider '{provider}'."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/check_l2", tags=["Status"])
def check_l2_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """Check Level 2 (Persister & Processor Layer) for the specified provider."""
    try:
        provider = provider.lower()
        info.check_l2(provider)
        return {"message": f"Check L2 completed for provider '{provider}'."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/check_l3", tags=["Status"])
def check_l3_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """Check Level 3 (Hot, Cold, Archive Storage) for the specified provider."""
    try:
        provider = provider.lower()
        info.check_l3(provider)
        return {"message": f"Check L3 completed for provider '{provider}'."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/check_l4", tags=["Status"])
def check_l4_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """Check Level 4 (TwinMaker Layer) for the specified provider."""
    try:
        provider = provider.lower()
        info.check_l4(provider)
        return {"message": f"Check L4 completed for provider '{provider}'."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/check_l5", tags=["Status"])
def check_l5_endpoint(provider: str = Query("aws", description="Cloud provider: aws, azure, or google")):
    """Check Level 5 (Grafana / Visualization Layer) for the specified provider."""
    try:
        provider = provider.lower()
        info.check_l5(provider)
        return {"message": f"Check L5 completed for provider '{provider}'."}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


# --------- Info ----------    
@app.get("/info/config", tags=["Info"])
def get_main_config():
    """
    Retrieve the main configuration of the digital twin environment.

    Contains:
    - `digital_twin_name`: Name of the digital twin instance.
    - `layer_3_hot_to_cold_interval_days`: Number of days after which hot data is moved to cold storage.
    - `layer_3_cold_to_archive_interval_days`: Number of days after which cold data is moved to archive storage.

    Example response:
    ```json
    {
      "digital_twin_name": "digital-twin",
      "layer_3_hot_to_cold_interval_days": 30,
      "layer_3_cold_to_archive_interval_days": 90
    }
    ```

    Returns:
        JSON object containing the main configuration parameters of the digital twin.
    """
    try:
        return pretty_json(globals.config)
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/info/config_iot_devices", tags=["Info"])
def get_iot_config():
    """
    Retrieve the configuration for all IoT devices.

    Each IoT device includes:
    - `name`: Unique name of the device.
    - `properties`: List of sensor properties with names and data types.
    - `constProperties` (optional): List of constant properties with names, data types, and fixed values.

    Example response:
    ```json
    [
      {
        "name": "temperature-sensor-1",
        "properties": [{"name": "temperature", "dataType": "DOUBLE"}],
        "constProperties": [{"name": "serial-number", "dataType": "STRING", "value": "1232323"}]
      },
      {
        "name": "pressure-sensor-1",
        "properties": [
          {"name": "pressure", "dataType": "DOUBLE"},
          {"name": "density", "dataType": "DOUBLE"},
          {"name": "hardness", "dataType": "DOUBLE"}
        ]
      }
    ]
    ```

    Returns:
        JSON array of IoT device configurations.
    """
    try:
        return pretty_json(globals.config_iot_devices)
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/info/config_providers", tags=["Info"])
def get_providers_config():
    """
    Retrieve the cloud provider configuration for each deployment layer.

    Example response:
    ```json
    {
      "layer_1_provider": "aws",
      "layer_2_provider": "aws",
      "layer_3_hot_provider": "aws",
      "layer_3_cold_provider": "aws",
      "layer_3_archive_provider": "aws",
      "layer_4_provider": "aws",
      "layer_5_provider": "aws"
    }
    ```

    Returns:
        JSON object where each key represents a layer in the digital twin architecture and the value specifies the cloud provider used for that layer.
    """
    try:
        return pretty_json(globals.config_providers)
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

# @app.get("/info/config_credentials", tags=["Info"])
# def get_credentials_config():
#     """
#     Retrieve the cloud credentials configuration.

#     Contains:
#     - `aws`: AWS credentials with fields:
#         - `aws_access_key_id`: AWS access key ID.
#         - `aws_secret_access_key`: AWS secret access key.
#         - `aws_region`: Default AWS region.
#     - `azure`: Azure credentials with fields:
#         - `azure_subscription_id`: Azure subscription ID.
#         - `azure_client_id`: Azure client ID.
#         - `azure_client_secret`: Azure client secret.
#         - `azure_tenant_id`: Azure tenant ID.
#         - `azure_region`: Default Azure region.
#     - `google`: Google Cloud credentials with fields:
#         - `gcp_project_id`: Google Cloud project ID.
#         - `gcp_credentials_file`: Path to the Google Cloud credentials JSON file.
#         - `gcp_region`: Default Google Cloud region.

#     Returns:
#         JSON object containing cloud credentials used for API calls.
#     """
#     try:
#         return pretty_json(globals.config_credentials)
#     except Exception as e:
#         globals.print_stack_trace()
#         logger.error(str(e))
#         raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/info/config_hierarchy", tags=["Info"])
def get_config_hierarchy():
    """
    Retrieve the hierarchical entity configuration of the digital twin environment.

    This configuration defines how entities, machines, and IoT components are organized within the digital twin.

    Example structure:
    ```json
    [
      {
        "type": "entity",
        "id": "room-1",
        "children": [
          {
            "type": "entity",
            "id": "machine-1",
            "children": [
              {
                "type": "component",
                "name": "temperature-sensor-1",
                "componentTypeId": "digital-twin-temperature-sensor-1"
              }
            ]
          },
          {
            "type": "component",
            "name": "temperature-sensor-2",
            "iotDeviceId": "temperature-sensor-2"
          }
        ]
      }
    ]
    ```

    Returns:
        JSON array defining the full entity and component hierarchy of the digital twin.
    """
    try:
        with open("config_hierarchy.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return pretty_json(data)
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/info/config_events", tags=["Info"])
def get_config_events():
    """
    Retrieve the event-driven automation configuration of the digital twin environment.

    Each event defines a condition to monitor (e.g., sensor value thresholds) and an action to execute when the condition is met.

    Example structure:
    ```json
    [
      {
        "condition": "testEntityId.temperature-sensor-1.temperature == DOUBLE(30)",
        "action": {
          "type": "lambda",
          "functionName": "high-temperature-callback",
          "autoDeploy": true
        }
      }
    ]
    ```

    Returns:
        JSON array defining event conditions and corresponding automated actions.
    """
    try:
        with open("config_events.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return pretty_json(data)
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

# --------- Lambda Management ----------
@app.post("/lambda_update", tags=["AWS"])
def lambda_update(req: LambdaUpdateRequest):
    """
    Update an AWS Lambda function with the latest local code.

    Behavior:
    - If `local_function_name` is "default-processor", updates all processor Lambdas for each IoT device.
    - Otherwise, updates a single Lambda function by name.
    - Optionally updates the Lambda environment variables if `environment` is provided.

    Parameters:
    - local_function_name: Name of the local Lambda function to update.
    - environment: JSON string defining environment variables to set (optional).

    Returns:
        JSON message confirming the update.
    """
    try:
        if req.environment:
            lambda_manager.update_function(req.local_function_name, req.environment)
        else:
            lambda_manager.update_function(req.local_function_name)
        return {"message": f"Lambda {req.local_function_name} updated successfully"}
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/lambda_logs", tags=["AWS"])
def get_lambda_logs(req: LambdaLogsRequest = Depends()) -> List[str]:
    """
    Fetch the most recent log messages from a specified Lambda function.

    Parameters:
    - local_function_name: Name of the local Lambda function to fetch logs from.
    - n: Number of log lines to return (default 10).
    - filter_system_logs: Whether to exclude AWS system log messages (default True).

    Returns:
        List of log messages as strings.
    """
    try:
        logs = lambda_manager.fetch_logs(req.local_function_name, n=req.n, filter_system_logs=req.filter_system_logs)
        return logs
    except Exception as e:
        globals.print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
=======
import sys
import io
import subprocess
import json
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


@app.get("/api/test")
def test_get(test: str = "default"):
    return {"message": f"Test successful! You sent: {test}"}

@app.post("/api/test")
def test_post(test: str):
    return {"message": f"Test successful! You sent: {test}"}
>>>>>>> 94f88ba (add deployer init)
