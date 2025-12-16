"""
AWS-specific deployment functions for Terraform.

This module handles AWS Lambda code deployment via boto3,
TwinMaker entity creation, IoT Core device registration, and Grafana configuration.
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)

# Mapping from Terraform output keys to Lambda function directories
# Uses hyphenated names as they exist in lambda_functions/
LAMBDA_FUNCTION_MAP = {
    "aws_l1_dispatcher_function_name": "dispatcher",
    "aws_l2_persister_function_name": "persister",
    "aws_l2_event_checker_function_name": "event-checker",
    "aws_l3_hot_reader_function_name": "hot-reader",
    "aws_l3_hot_to_cold_mover_function_name": "hot-to-cold-mover",
    "aws_l3_cold_to_archive_mover_function_name": "cold-to-archive-mover",
    "aws_l0_ingestion_function_name": "ingestion",
    "aws_l0_hot_writer_function_name": "hot-writer",
    "aws_l0_hot_reader_function_name": "hot-reader",
    "aws_l0_cold_writer_function_name": "cold-writer",
    "aws_l0_archive_writer_function_name": "archive-writer",
    "aws_l4_connector_function_name": "digital-twin-data-connector",
}


def deploy_aws_lambda_code(
    project_path: Path,
    providers_config: dict,
    terraform_outputs: dict,
    load_credentials_fn
) -> None:
    """
    Deploy AWS Lambda code via boto3.
    
    Args:
        project_path: Path to project directory
        providers_config: Layer provider configuration
        terraform_outputs: Terraform output values
        load_credentials_fn: Function to load credentials
    """
    # Check if any layer uses AWS
    aws_layers = ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider", 
                  "layer_4_provider", "layer_5_provider"]
    has_aws = any(providers_config.get(layer) == "aws" for layer in aws_layers)
    
    if not has_aws:
        logger.info("  No AWS layers configured, skipping Lambda deployment")
        return
    
    try:
        import boto3
    except ImportError:
        logger.warning("  boto3 not available, skipping AWS Lambda deployment")
        return
    
    aws_creds = load_credentials_fn().get("aws", {})
    if not aws_creds.get("aws_access_key_id"):
        logger.warning("  AWS credentials not found, skipping Lambda deployment")
        return
    
    lambda_client = boto3.client(
        'lambda',
        aws_access_key_id=aws_creds["aws_access_key_id"],
        aws_secret_access_key=aws_creds["aws_secret_access_key"],
        region_name=aws_creds.get("aws_region", "eu-central-1")
    )
    
    # Deploy each AWS Lambda function found in outputs
    for output_key, function_dir_name in LAMBDA_FUNCTION_MAP.items():
        function_name = terraform_outputs.get(output_key)
        if function_name:
            _deploy_to_aws_lambda(
                lambda_client, function_name, function_dir_name, project_path
            )


def _deploy_to_aws_lambda(
    lambda_client,
    function_name: str,
    function_dir_name: str,
    project_path: Path
) -> None:
    """Deploy ZIP code to an AWS Lambda function."""
    logger.info(f"  Deploying {function_dir_name} to {function_name}...")
    
    try:
        # Lambda functions are in providers/aws/lambda_functions/
        lambda_functions_dir = Path(__file__).parent.parent / "aws" / "lambda_functions"
        function_dir = lambda_functions_dir / function_dir_name
        
        if not function_dir.exists():
            logger.warning(f"  Lambda function directory not found: {function_dir}")
            return
        
        # Create deployment package
        zip_bytes = _create_lambda_zip(function_dir, project_path)
        
        lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_bytes
        )
        logger.info(f"  ✓ {function_dir_name} deployed")
        
    except Exception as e:
        logger.warning(f"  {function_dir_name} deployment failed: {e}")


def _create_lambda_zip(function_dir: Path, project_path: Path) -> bytes:
    """Create a ZIP deployment package for Lambda."""
    import io
    import zipfile
    
    buffer = io.BytesIO()
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add all files from function directory
        for file_path in function_dir.rglob('*'):
            if file_path.is_file() and '__pycache__' not in str(file_path):
                arcname = file_path.relative_to(function_dir)
                zf.write(file_path, arcname)
        
        # Add shared modules from _shared directory
        shared_dir = function_dir.parent / "_shared"
        if shared_dir.exists():
            for file_path in shared_dir.rglob('*'):
                if file_path.is_file() and '__pycache__' not in str(file_path):
                    arcname = file_path.relative_to(shared_dir)
                    zf.write(file_path, arcname)
    
    buffer.seek(0)
    return buffer.read()


def create_twinmaker_entities(
    project_path: Path,
    terraform_outputs: dict,
    load_credentials_fn
) -> None:
    """Create TwinMaker entities via AWS SDK (workspace created by Terraform)."""
    logger.info("  Creating TwinMaker entities...")
    
    try:
        import boto3
        
        aws_creds = load_credentials_fn().get("aws", {})
        workspace_id = terraform_outputs.get("aws_twinmaker_workspace_id")
        
        if not workspace_id:
            logger.warning("  TwinMaker workspace not found, skipping entity creation")
            return
        
        twinmaker = boto3.client(
            'iottwinmaker',
            aws_access_key_id=aws_creds["aws_access_key_id"],
            aws_secret_access_key=aws_creds["aws_secret_access_key"],
            region_name=aws_creds.get("aws_region", "eu-central-1")
        )
        
        # Load IoT devices from config
        devices_file = project_path / "config_iot_devices.json"
        if devices_file.exists():
            with open(devices_file) as f:
                devices = json.load(f).get("devices", [])
            
            for device in devices:
                try:
                    twinmaker.create_entity(
                        workspaceId=workspace_id,
                        entityId=device["id"],
                        entityName=device.get("name", device["id"]),
                        description=f"Twin entity for {device['id']}"
                    )
                    logger.info(f"  ✓ Entity created: {device['id']}")
                except twinmaker.exceptions.ConflictException:
                    logger.info(f"  Entity already exists: {device['id']}")
                except Exception as e:
                    logger.warning(f"  Entity creation failed for {device['id']}: {e}")
                    
    except ImportError:
        logger.warning("  boto3 not available, skipping TwinMaker entity creation")
    except Exception as e:
        logger.warning(f"  TwinMaker entity creation failed: {e}")


def register_aws_iot_devices(
    project_path: Path,
    load_credentials_fn
) -> None:
    """Register IoT devices via AWS IoT Core SDK."""
    logger.info("  Registering AWS IoT devices...")
    
    try:
        import boto3
        
        aws_creds = load_credentials_fn().get("aws", {})
        iot = boto3.client(
            'iot',
            aws_access_key_id=aws_creds["aws_access_key_id"],
            aws_secret_access_key=aws_creds["aws_secret_access_key"],
            region_name=aws_creds.get("aws_region", "eu-central-1")
        )
        
        # Load IoT devices from config
        devices_file = project_path / "config_iot_devices.json"
        if devices_file.exists():
            with open(devices_file) as f:
                devices = json.load(f).get("devices", [])
            
            for device in devices:
                try:
                    iot.create_thing(thingName=device["id"])
                    logger.info(f"  ✓ IoT Thing created: {device['id']}")
                except iot.exceptions.ResourceAlreadyExistsException:
                    logger.info(f"  IoT Thing already exists: {device['id']}")
                except Exception as e:
                    logger.warning(f"  IoT Thing creation failed for {device['id']}: {e}")
                    
    except ImportError:
        logger.warning("  boto3 not available, skipping AWS IoT device registration")
    except Exception as e:
        logger.warning(f"  AWS IoT device registration failed: {e}")


def configure_aws_grafana(
    terraform_outputs: dict,
    load_credentials_fn
) -> None:
    """Configure AWS Grafana datasources via Grafana API."""
    logger.info("  Configuring AWS Grafana...")
    
    try:
        import requests
        
        grafana_endpoint = terraform_outputs.get("aws_grafana_endpoint")
        api_key = terraform_outputs.get("aws_grafana_api_key")
        hot_reader_url = terraform_outputs.get("aws_l3_hot_reader_url")
        
        if not all([grafana_endpoint, api_key, hot_reader_url]):
            logger.warning("  Missing Grafana config (endpoint/api_key/hot_reader), skipping")
            return
        
        # Configure JSON API datasource
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        datasource = {
            "name": "Hot Storage API",
            "type": "marcusolsson-json-datasource",
            "url": hot_reader_url,
            "access": "proxy",
            "isDefault": True
        }
        
        response = requests.post(
            f"{grafana_endpoint}/api/datasources",
            headers=headers,
            json=datasource,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            logger.info("  ✓ AWS Grafana datasource configured")
        elif response.status_code == 409:
            logger.info("  Grafana datasource already exists")
        else:
            logger.warning(f"  Grafana datasource config failed: {response.text}")
            
    except ImportError:
        logger.warning("  requests not available, skipping Grafana config")
    except Exception as e:
        logger.warning(f"  AWS Grafana config failed: {e}")
