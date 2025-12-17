"""
Azure-specific deployment functions for Terraform.

This module handles Azure Function App code deployment via Kudu,
DTDL model upload, IoT device registration, and Grafana configuration.
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)


def deploy_azure_function_code(
    project_path: Path,
    providers_config: dict,
    terraform_outputs: dict,
    load_credentials_fn
) -> None:
    """
    Deploy Azure Function code via Kudu ZIP deploy.
    
    NOTE: System functions (L0-L3) are now deployed via Terraform's zip_deploy_file.
    This function only deploys USER functions (event actions, processors, feedback).
    
    Args:
        project_path: Path to project directory
        providers_config: Layer provider configuration
        terraform_outputs: Terraform output values
        load_credentials_fn: Function to load credentials
    """
    # User functions deployment
    if providers_config.get("layer_2_provider") == "azure":
        _deploy_user_functions(
            project_path, providers_config, terraform_outputs, load_credentials_fn
        )


def _deploy_user_functions(
    project_path: Path,
    providers_config: dict,
    terraform_outputs: dict,
    load_credentials_fn
) -> None:
    """Deploy user-customizable functions (event actions, processors) via Kudu."""
    from src.providers.terraform.package_builder import (
        build_combined_user_package,
        get_combined_user_package_path,
    )
    
    app_name = terraform_outputs.get("azure_user_functions_app_name")
    
    if not app_name:
        logger.info("  No user functions app deployed, skipping user function deployment")
        return
    
    logger.info("  Building and deploying user functions...")
    
    try:
        # Build combined user package (all event actions, processors, feedback)
        combined_zip_path = build_combined_user_package(project_path, providers_config)
        
        if not combined_zip_path or not combined_zip_path.exists():
            logger.info("  No user functions to deploy")
            return
        
        # Read ZIP and deploy
        with open(combined_zip_path, "rb") as f:
            zip_bytes = f.read()
        
        _deploy_to_azure_app(
            app_name, zip_bytes, "User Functions",
            terraform_outputs, load_credentials_fn
        )
        
        logger.info("  ✓ User functions deployed successfully")
        
    except Exception as e:
        logger.error(f"  User function deployment failed: {e}")
        raise


def _deploy_to_azure_app(
    app_name: str,
    zip_bytes: bytes,
    label: str,
    terraform_outputs: dict,
    load_credentials_fn
) -> None:
    """Deploy ZIP bytes to an Azure Function App via Kudu."""
    from azure.identity import ClientSecretCredential
    from azure.mgmt.web import WebSiteManagementClient
    from src.providers.azure.layers.deployment_helpers import (
        deploy_to_kudu,
        get_publishing_credentials_with_retry,
    )
    
    logger.info(f"  Deploying {label} to {app_name}...")
    
    azure_creds = load_credentials_fn().get("azure", {})
    rg_name = terraform_outputs.get("azure_resource_group_name")
    
    if not rg_name:
        logger.warning(f"  Resource group not found, skipping {label}")
        return
    
    try:
        # Create Azure SDK client from credentials
        credential = ClientSecretCredential(
            tenant_id=azure_creds["azure_tenant_id"],
            client_id=azure_creds["azure_client_id"],
            client_secret=azure_creds["azure_client_secret"]
        )
        web_client = WebSiteManagementClient(
            credential=credential,
            subscription_id=azure_creds["azure_subscription_id"]
        )
        
        creds = get_publishing_credentials_with_retry(
            web_client=web_client,
            resource_group=rg_name,
            app_name=app_name
        )
        
        deploy_to_kudu(
            app_name=app_name,
            zip_content=zip_bytes,
            publish_username=creds.publishing_user_name,
            publish_password=creds.publishing_password
        )
        logger.info(f"  ✓ {label} deployed")
    except Exception as e:
        logger.error(f"  ✗ {label} deployment failed: {e}")
        raise


def upload_dtdl_models(context: 'DeploymentContext', project_path: Path) -> None:
    """Upload DTDL models to Azure Digital Twins."""
    logger.info("  Uploading DTDL models...")
    try:
        from src.providers.azure.layers.layer_4_adt import upload_dtdl_models as _upload
        provider = context.providers.get("azure")
        if provider:
            _upload(provider, context.config, str(project_path))
            logger.info("  ✓ DTDL models uploaded")
    except ImportError:
        logger.warning("  layer_4_adt not available, skipping DTDL upload")
    except Exception as e:
        logger.warning(f"  DTDL upload failed: {e}")


def register_azure_iot_devices(context: 'DeploymentContext', project_path: Path) -> None:
    """Register IoT devices via Azure IoT Hub SDK."""
    logger.info("  Registering Azure IoT devices...")
    try:
        from src.providers.azure.layers.layer_1_iot import register_iot_devices
        provider = context.providers.get("azure")
        if provider:
            register_iot_devices(provider, context.config, str(project_path))
            logger.info("  ✓ Azure IoT devices registered")
    except ImportError:
        logger.warning("  layer_1_iot not available, skipping device registration")
    except Exception as e:
        logger.warning(f"  Azure IoT device registration failed: {e}")


def configure_azure_grafana(context: 'DeploymentContext', terraform_outputs: dict) -> None:
    """Configure Azure Grafana datasources."""
    logger.info("  Configuring Azure Grafana...")
    try:
        from src.providers.azure.layers.layer_5_grafana import configure_grafana_datasource
        provider = context.providers.get("azure")
        if provider:
            hot_reader_url = terraform_outputs.get("azure_l3_hot_reader_url")
            if hot_reader_url:
                configure_grafana_datasource(provider, hot_reader_url)
                logger.info("  ✓ Azure Grafana configured")
    except ImportError:
        logger.warning("  layer_5_grafana not available, skipping config")
    except Exception as e:
        logger.warning(f"  Azure Grafana config failed: {e}")
