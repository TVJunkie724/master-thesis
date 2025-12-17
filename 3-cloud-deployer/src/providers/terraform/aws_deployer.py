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
    """
    Create TwinMaker entities and component types via AWS SDK.
    
    The workspace is created by Terraform, but entities and component types
    are created here because they depend on IoT device configuration.
    
    Component types are essential for data visualization - they define
    the data schema and link to Lambda connectors for fetching data.
    """
    logger.info("  Creating TwinMaker entities and component types...")
    
    try:
        import boto3
        import time
        
        aws_creds = load_credentials_fn().get("aws", {})
        region = aws_creds.get("aws_region", "eu-central-1")
        workspace_id = terraform_outputs.get("aws_twinmaker_workspace_id")
        
        if not workspace_id:
            logger.warning("  TwinMaker workspace not found, skipping entity creation")
            return
        
        twinmaker = boto3.client(
            'iottwinmaker',
            aws_access_key_id=aws_creds["aws_access_key_id"],
            aws_secret_access_key=aws_creds["aws_secret_access_key"],
            region_name=region
        )
        
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=aws_creds["aws_access_key_id"],
            aws_secret_access_key=aws_creds["aws_secret_access_key"],
            region_name=region
        )
        
        # Load config
        config_file = project_path / "config.json"
        devices_file = project_path / "config_iot_devices.json"
        
        if not config_file.exists():
            logger.warning("  config.json not found, skipping entity creation")
            return
            
        with open(config_file) as f:
            config = json.load(f)
        digital_twin_name = config.get("digital_twin_name")
        
        if not devices_file.exists():
            logger.info("  No config_iot_devices.json, skipping entity creation")
            return
            
        with open(devices_file) as f:
            devices = json.load(f)
        
        # Handle both array format and {devices: [...]} format
        if isinstance(devices, dict):
            devices = devices.get("devices", [])
        
        if not devices:
            logger.info("  No devices configured, skipping entity creation")
            return
        
        # Get Lambda connector ARNs from Terraform outputs
        connector_arn = terraform_outputs.get("aws_l4_connector_function_arn")
        connector_last_entry_arn = terraform_outputs.get("aws_l4_connector_last_entry_function_arn")
        
        # Fall back to Lambda lookup if not in outputs
        if not connector_arn:
            connector_name = f"{digital_twin_name}-l4-connector"
            try:
                resp = lambda_client.get_function(FunctionName=connector_name)
                connector_arn = resp["Configuration"]["FunctionArn"]
            except Exception:
                logger.info(f"  L4 connector Lambda not found, skipping component types")
        
        if not connector_last_entry_arn:
            connector_last_entry_name = f"{digital_twin_name}-l4-connector-last-entry"
            try:
                resp = lambda_client.get_function(FunctionName=connector_last_entry_name)
                connector_last_entry_arn = resp["Configuration"]["FunctionArn"]
            except Exception:
                # Fall back to same Lambda if last-entry variant doesn't exist
                if connector_arn:
                    connector_last_entry_arn = connector_arn
        
        for device in devices:
            device_id = device.get("id")
            if not device_id:
                continue
            
            # 1. Create entity
            try:
                twinmaker.create_entity(
                    workspaceId=workspace_id,
                    entityId=device_id,
                    entityName=device.get("name", device_id),
                    description=f"Twin entity for {device_id}"
                )
                logger.info(f"  ✓ Entity created: {device_id}")
            except twinmaker.exceptions.ConflictException:
                logger.info(f"  Entity already exists: {device_id}")
            except Exception as e:
                logger.warning(f"  Entity creation failed for {device_id}: {e}")
            
            # 2. Create component type (if Lambda connectors exist)
            if connector_arn:
                component_type_id = f"{digital_twin_name}-{device_id}"
                
                try:
                    # Build property definitions from device config
                    property_definitions = {}
                    
                    for prop in device.get("properties", []):
                        property_definitions[prop["name"]] = {
                            "dataType": {"type": prop.get("dataType", "STRING")},
                            "isTimeSeries": True,
                            "isStoredExternally": True
                        }
                    
                    # Add const properties if present
                    for const_prop in device.get("constProperties", []):
                        data_type = const_prop.get("dataType", "STRING")
                        property_definitions[const_prop["name"]] = {
                            "dataType": {"type": data_type},
                            "defaultValue": {
                                f"{data_type.lower()}Value": const_prop.get("value")
                            },
                            "isTimeSeries": False,
                            "isStoredExternally": False
                        }
                    
                    # Define functions connecting to Lambda
                    functions = {
                        "dataReader": {
                            "implementedBy": {
                                "lambda": {"arn": connector_arn}
                            }
                        }
                    }
                    
                    if connector_last_entry_arn:
                        functions["attributePropertyValueReaderByEntity"] = {
                            "implementedBy": {
                                "lambda": {"arn": connector_last_entry_arn}
                            }
                        }
                    
                    # Create component type
                    twinmaker.create_component_type(
                        workspaceId=workspace_id,
                        componentTypeId=component_type_id,
                        propertyDefinitions=property_definitions,
                        functions=functions
                    )
                    logger.info(f"  ✓ Component type created: {component_type_id}")
                    
                    # Wait for component type to become active
                    for _ in range(30):
                        resp = twinmaker.get_component_type(
                            workspaceId=workspace_id,
                            componentTypeId=component_type_id
                        )
                        if resp["status"]["state"] == "ACTIVE":
                            break
                        time.sleep(1)
                    
                except twinmaker.exceptions.ConflictException:
                    logger.info(f"  Component type already exists: {component_type_id}")
                except Exception as e:
                    logger.warning(f"  Component type creation failed for {device_id}: {e}")
                    
    except ImportError:
        logger.warning("  boto3 not available, skipping TwinMaker entity creation")
    except Exception as e:
        logger.warning(f"  TwinMaker entity creation failed: {e}")


def register_aws_iot_devices(
    project_path: Path,
    load_credentials_fn,
    terraform_outputs: dict = None
) -> None:
    """
    Register IoT devices via AWS IoT Core SDK.
    
    Creates IoT Things, certificates, policies, and generates
    config_generated.json for the simulator.
    
    Args:
        project_path: Path to project directory
        load_credentials_fn: Function to load credentials
        terraform_outputs: Optional Terraform outputs (for IoT endpoint)
    """
    logger.info("  Registering AWS IoT devices...")
    
    try:
        import boto3
        import os
        
        aws_creds = load_credentials_fn().get("aws", {})
        region = aws_creds.get("aws_region", "eu-central-1")
        
        iot = boto3.client(
            'iot',
            aws_access_key_id=aws_creds["aws_access_key_id"],
            aws_secret_access_key=aws_creds["aws_secret_access_key"],
            region_name=region
        )
        
        # Load config
        config_file = project_path / "config.json"
        devices_file = project_path / "config_iot_devices.json"
        
        if not config_file.exists():
            logger.warning("  config.json not found, skipping device registration")
            return
            
        with open(config_file) as f:
            config = json.load(f)
        digital_twin_name = config.get("digital_twin_name")
        
        if not devices_file.exists():
            logger.info("  No config_iot_devices.json, skipping device registration")
            return
            
        with open(devices_file) as f:
            devices = json.load(f)
        
        # Handle both array format and {devices: [...]} format
        if isinstance(devices, dict):
            devices = devices.get("devices", [])
        
        if not devices:
            logger.info("  No devices configured, skipping device registration")
            return
        
        # Get IoT endpoint for simulator config
        try:
            endpoint_response = iot.describe_endpoint(endpointType='iot:Data-ATS')
            iot_endpoint = endpoint_response['endpointAddress']
        except Exception as e:
            logger.warning(f"  Could not get IoT endpoint: {e}")
            iot_endpoint = None
        
        for device in devices:
            device_id = device.get("id")
            if not device_id:
                continue
                
            thing_name = f"{digital_twin_name}-{device_id}"
            policy_name = f"{thing_name}-policy"
            
            try:
                # 1. Create IoT Thing
                try:
                    iot.create_thing(thingName=thing_name)
                    logger.info(f"  ✓ IoT Thing created: {thing_name}")
                except iot.exceptions.ResourceAlreadyExistsException:
                    logger.info(f"  IoT Thing already exists: {thing_name}")
                
                # 2. Create Certificate
                cert_dir = project_path / "iot_devices_auth" / device_id
                cert_dir.mkdir(parents=True, exist_ok=True)
                
                cert_path = cert_dir / "certificate.pem.crt"
                key_path = cert_dir / "private.pem.key"
                
                # Check if certificates already exist
                if cert_path.exists() and key_path.exists():
                    logger.info(f"  Certificates already exist for: {device_id}")
                else:
                    cert_response = iot.create_keys_and_certificate(setAsActive=True)
                    certificate_arn = cert_response['certificateArn']
                    
                    # Save certificates
                    with open(cert_path, "w") as f:
                        f.write(cert_response["certificatePem"])
                    with open(key_path, "w") as f:
                        f.write(cert_response["keyPair"]["PrivateKey"])
                    with open(cert_dir / "public.pem.key", "w") as f:
                        f.write(cert_response["keyPair"]["PublicKey"])
                    
                    logger.info(f"  ✓ Certificate created for: {device_id}")
                    
                    # 3. Create IoT Policy
                    policy_document = {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Action": ["iot:*"],
                            "Resource": "*"
                        }]
                    }
                    
                    try:
                        iot.create_policy(
                            policyName=policy_name,
                            policyDocument=json.dumps(policy_document)
                        )
                        logger.info(f"  ✓ IoT Policy created: {policy_name}")
                    except iot.exceptions.ResourceAlreadyExistsException:
                        logger.info(f"  IoT Policy already exists: {policy_name}")
                    
                    # 4. Attach certificate to Thing and Policy
                    try:
                        iot.attach_thing_principal(
                            thingName=thing_name,
                            principal=certificate_arn
                        )
                        logger.info(f"  ✓ Certificate attached to Thing")
                    except Exception as e:
                        logger.warning(f"  Could not attach certificate to Thing: {e}")
                    
                    try:
                        iot.attach_policy(
                            policyName=policy_name,
                            target=certificate_arn
                        )
                        logger.info(f"  ✓ Policy attached to Certificate")
                    except Exception as e:
                        logger.warning(f"  Could not attach policy to certificate: {e}")
                
                # 5. Generate simulator config
                if iot_endpoint:
                    _generate_aws_simulator_config(
                        project_path, device, digital_twin_name, iot_endpoint
                    )
                    
            except Exception as e:
                logger.warning(f"  IoT device setup failed for {device_id}: {e}")
                    
    except ImportError:
        logger.warning("  boto3 not available, skipping AWS IoT device registration")
    except Exception as e:
        logger.warning(f"  AWS IoT device registration failed: {e}")


def _generate_aws_simulator_config(
    project_path: Path,
    iot_device: dict,
    digital_twin_name: str,
    iot_endpoint: str
) -> None:
    """
    Generate config_generated.json for the AWS IoT device simulator.
    
    Note: Unlike GCP which uses Terraform's local_file resource, AWS config
    generation MUST be done via SDK because:
    1. The iot_endpoint is obtained from describe_endpoint() at runtime
    2. The certificate paths reference files created during device registration
    3. Device registration creates certificates that must exist before config
    
    These values are only known AFTER registering the device in IoT Core
    and cannot be predicted at Terraform plan time.
    
    Args:
        project_path: Path to project directory
        iot_device: Device configuration dict with 'id'
        digital_twin_name: Name of the digital twin
        iot_endpoint: AWS IoT endpoint address
    """
    import os
    
    device_id = iot_device['id']
    
    # Topic format matches IoT Topic Rule: dt/{twin}/+/telemetry
    topic = f"dt/{digital_twin_name}/{device_id}/telemetry"
    
    # Paths relative to simulator directory
    config_data = {
        "endpoint": iot_endpoint,
        "topic": topic,
        "device_id": device_id,
        "cert_path": f"../../iot_devices_auth/{device_id}/certificate.pem.crt",
        "key_path": f"../../iot_devices_auth/{device_id}/private.pem.key",
        "root_ca_path": str(Path(__file__).parent.parent / "aws" / "AmazonRootCA1.pem"),
        "payload_path": "payloads.json"
    }
    
    # Write to upload/{project}/iot_device_simulator/aws/
    sim_dir = project_path / "iot_device_simulator" / "aws"
    sim_dir.mkdir(parents=True, exist_ok=True)
    config_path = sim_dir / "config_generated.json"
    
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    
    logger.info(f"  ✓ Generated simulator config: {config_path}")


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
