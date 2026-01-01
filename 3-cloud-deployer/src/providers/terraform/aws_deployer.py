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

from src.function_registry import get_terraform_output_map

# Dynamically generated from function registry
# Maps Terraform output keys to Lambda function directory names
LAMBDA_FUNCTION_MAP = get_terraform_output_map("aws")
# NOTE: Lambda code is now deployed via Terraform's filename property.
# ZIPs are built in Step 2 by package_builder.build_aws_lambda_packages()
# and deployed in Step 5 via Terraform apply.


def create_twinmaker_entities(
    context: 'DeploymentContext',
    project_path: Path,
    terraform_outputs: dict
) -> None:
    """
    Create TwinMaker entities and component types via AWS SDK.
    
    The workspace is created by Terraform, but entities and component types
    are created here using the hierarchy from aws_hierarchy.json.
    
    Component types are essential for data visualization - they define
    the data schema and link to Lambda connectors for fetching data.
    
    Args:
        context: DeploymentContext with initialized AWS provider
        project_path: Path to project directory (unused, kept for API consistency)
        terraform_outputs: Terraform output values
    """
    logger.info("  Creating TwinMaker entities and component types...")
    
    # PRESERVED: Provider validation
    provider = context.providers.get("aws")
    if provider is None:
        logger.error("  ✗ AWS provider not initialized in context.providers")
        raise RuntimeError("AWS provider not initialized - cannot create TwinMaker entities")
    
    # PRESERVED: boto3 ImportError and general exception handling
    try:
        import time
        
        workspace_id = terraform_outputs.get("aws_twinmaker_workspace_id")
        
        if not workspace_id:
            logger.warning("  TwinMaker workspace not found, skipping entity creation")
            return
        
        # Use pre-initialized clients from provider
        twinmaker = provider.clients["twinmaker"]
        lambda_client = provider.clients["lambda"]
        
        # Use pre-loaded config from context (not file I/O)
        digital_twin_name = context.config.digital_twin_name
        hierarchy = context.config.hierarchy
        
        if not hierarchy:
            logger.info("  No hierarchy configured, skipping entity creation")
            return
        
        if not isinstance(hierarchy, list):
            logger.warning("  AWS hierarchy must be a list, skipping entity creation")
            return
        
        # PRESERVED: Get Lambda connector ARNs from Terraform outputs
        connector_arn = terraform_outputs.get("aws_l4_connector_function_arn")
        connector_last_entry_arn = terraform_outputs.get("aws_l4_connector_last_entry_function_arn")
        
        # PRESERVED: Fall back to Lambda lookup if not in outputs
        if not connector_arn:
            connector_name = f"{digital_twin_name}-l4-connector"
            try:
                resp = lambda_client.get_function(FunctionName=connector_name)
                connector_arn = resp["Configuration"]["FunctionArn"]
            except Exception:
                logger.info("  L4 connector Lambda not found, skipping component types")
        
        if not connector_last_entry_arn:
            connector_last_entry_name = f"{digital_twin_name}-l4-connector-last-entry"
            try:
                resp = lambda_client.get_function(FunctionName=connector_last_entry_name)
                connector_last_entry_arn = resp["Configuration"]["FunctionArn"]
            except Exception:
                # Fall back to same Lambda if last-entry variant doesn't exist
                if connector_arn:
                    connector_last_entry_arn = connector_arn
        
        def create_recursive(node: dict, parent_id: str = None):
            """Recursively create entities with parent-child relationships."""
            if node.get("type") == "entity":
                entity_id = node.get("id")
                if not entity_id:
                    return
                
                # Create entity with optional parentEntityId
                try:
                    params = {
                        "workspaceId": workspace_id,
                        "entityId": entity_id,
                        "entityName": entity_id,
                        "description": f"Twin entity for {entity_id}"
                    }
                    if parent_id:
                        params["parentEntityId"] = parent_id
                    
                    twinmaker.create_entity(**params)
                    logger.info(f"  ✓ Entity: {entity_id}" + (f" (parent: {parent_id})" if parent_id else ""))
                except twinmaker.exceptions.ConflictException:
                    logger.info(f"  Entity already exists: {entity_id}")
                except Exception as e:
                    logger.warning(f"  Entity creation failed for {entity_id}: {e}")
                
                # Recursively create children
                for child in node.get("children", []):
                    create_recursive(child, entity_id)
            
            elif node.get("type") == "component" and connector_arn:
                # PRESERVED: Component type creation with Lambda wiring
                component_name = node.get("name", node.get("componentTypeId", "unknown"))
                component_type_id = f"{digital_twin_name}-{component_name}"
                
                try:
                    # Build property definitions from node
                    property_definitions = {}
                    
                    for prop in node.get("properties", []):
                        property_definitions[prop["name"]] = {
                            "dataType": {"type": prop.get("dataType", "STRING")},
                            "isTimeSeries": True,
                            "isStoredExternally": True
                        }
                    
                    # Add const properties if present
                    for const_prop in node.get("constProperties", []):
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
                    logger.info(f"  ✓ Component type: {component_type_id}")
                    
                    # PRESERVED: Wait for component type to become active
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
                    logger.warning(f"  Component type creation failed for {component_name}: {e}")
                    return  # Don't try to attach if creation failed
                
                # Attach component to parent entity
                if parent_id:
                    try:
                        twinmaker.update_entity(
                            workspaceId=workspace_id,
                            entityId=parent_id,
                            componentUpdates={
                                component_name: {
                                    "componentTypeId": component_type_id
                                }
                            }
                        )
                        logger.info(f"  ✓ Component attached: {component_name} → {parent_id}")
                    except twinmaker.exceptions.ConflictException:
                        logger.info(f"  Component already attached: {component_name}")
                    except Exception as e:
                        logger.warning(f"  Component attachment failed: {e}")
        
        # Process all root nodes in hierarchy
        for root_node in hierarchy:
            create_recursive(root_node)
                    
    except ImportError:
        logger.warning("  boto3 not available, skipping TwinMaker entity creation")
    except Exception as e:
        logger.warning(f"  TwinMaker entity creation failed: {e}")


def register_aws_iot_devices(
    context: 'DeploymentContext',
    project_path: Path,
    terraform_outputs: dict = None
) -> None:
    """
    Register IoT devices via AWS IoT Core SDK.
    
    Creates IoT Things, certificates, policies, and generates
    config_generated.json for the simulator.
    
    Args:
        context: DeploymentContext with initialized AWS provider
        project_path: Path to project directory
        terraform_outputs: Optional Terraform outputs (for IoT endpoint)
    """
    logger.info("  Registering AWS IoT devices...")
    
    # Get provider from context (already initialized)
    provider = context.providers.get("aws")
    if provider is None:
        logger.error("  ✗ AWS provider not initialized in context.providers")
        raise RuntimeError("AWS provider not initialized - cannot register IoT devices")
    
    try:
        import os
        
        # Use pre-initialized client from provider
        iot = provider.clients["iot"]
        
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
    context: 'DeploymentContext',
    terraform_outputs: dict
) -> None:
    """
    Configure AWS Grafana datasources via Grafana API.
    
    Args:
        context: DeploymentContext with initialized AWS provider
        terraform_outputs: Terraform output values
        
    Note: This function uses the Grafana HTTP API (requests library),
    not boto3 clients. The context is passed for consistency and
    potential future use (e.g., accessing provider.region).
    """
    logger.info("  Configuring AWS Grafana...")
    
    # Validate provider is initialized (consistent pattern)
    if context.providers.get("aws") is None:
        logger.error("  ✗ AWS provider not initialized in context.providers")
        raise RuntimeError("AWS provider not initialized - cannot configure Grafana")
    
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
