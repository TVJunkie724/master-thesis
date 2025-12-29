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
    context: 'DeploymentContext',
    project_path: Path,
    providers_config: dict,
    terraform_outputs: dict
) -> None:
    """
    Deploy Azure Function code via Kudu ZIP deploy.
    
    NOTE: System functions (L0-L3) are now deployed via Terraform's zip_deploy_file.
    This function only deploys USER functions (event actions, processors, feedback).
    
    Args:
        context: DeploymentContext with initialized Azure provider
        project_path: Path to project directory
        providers_config: Layer provider configuration
        terraform_outputs: Terraform output values
    """
    # User functions deployment
    if providers_config.get("layer_2_provider") == "azure":
        _deploy_user_functions(context, project_path, providers_config, terraform_outputs)


def _deploy_user_functions(
    context: 'DeploymentContext',
    project_path: Path,
    providers_config: dict,
    terraform_outputs: dict
) -> None:
    """Deploy user-customizable functions (event actions, processors) via Kudu."""
    from src.providers.terraform.package_builder import build_azure_user_bundle
    
    app_name = terraform_outputs.get("azure_user_functions_app_name")
    
    if not app_name:
        logger.info("  No user functions app deployed, skipping user function deployment")
        return
    
    logger.info("  Building and deploying user functions...")
    
    try:
        # Build combined user package (all event actions, processors, feedback)
        combined_zip_path = build_azure_user_bundle(project_path, providers_config)
        
        if not combined_zip_path or not combined_zip_path.exists():
            logger.info("  No user functions to deploy")
            return
        
        # Read ZIP and deploy
        with open(combined_zip_path, "rb") as f:
            zip_bytes = f.read()
        
        _deploy_to_azure_app(context, app_name, zip_bytes, "User Functions", terraform_outputs)
        
        logger.info("  ✓ User functions deployed successfully")
        
    except Exception as e:
        logger.error(f"  User function deployment failed: {e}")
        raise


def _deploy_to_azure_app(
    context: 'DeploymentContext',
    app_name: str,
    zip_bytes: bytes,
    label: str,
    terraform_outputs: dict
) -> None:
    """Deploy ZIP bytes to an Azure Function App via Kudu."""
    from src.providers.azure.layers.deployment_helpers import (
        deploy_to_kudu,
        get_publishing_credentials_with_retry,
    )
    
    logger.info(f"  Deploying {label} to {app_name}...")
    
    # Get provider from context (already initialized)
    provider = context.providers.get("azure")
    if provider is None:
        logger.error("  ✗ Azure provider not initialized in context.providers")
        raise RuntimeError("Azure provider not initialized - cannot deploy function code")
    
    rg_name = terraform_outputs.get("azure_resource_group_name")
    
    if not rg_name:
        logger.warning(f"  Resource group not found, skipping {label}")
        return
    
    try:
        # Use pre-initialized client from provider
        web_client = provider.clients["web"]
        
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
        if provider is None:
            logger.error("  ✗ Azure provider not initialized in context.providers")
            raise RuntimeError("Azure provider not initialized - cannot upload DTDL models")
        _upload(provider, context.config, str(project_path))
        logger.info("  ✓ DTDL models uploaded")
    except ImportError:
        logger.warning("  layer_4_adt not available, skipping DTDL upload")
    except Exception as e:
        logger.error(f"  ✗ DTDL upload failed: {e}")
        raise


def register_azure_iot_devices(context: 'DeploymentContext', project_path: Path) -> None:
    """Register IoT devices via Azure IoT Hub SDK."""
    logger.info("  Registering Azure IoT devices...")
    try:
        from src.providers.azure.layers.layer_1_iot import register_iot_devices
        provider = context.providers.get("azure")
        if provider is None:
            logger.error("  ✗ Azure provider not initialized in context.providers")
            raise RuntimeError("Azure provider not initialized - cannot register IoT devices")
        register_iot_devices(provider, context.config, str(project_path))
        logger.info("  ✓ Azure IoT devices registered")
    except ImportError:
        logger.warning("  layer_1_iot not available, skipping device registration")
    except Exception as e:
        logger.error(f"  ✗ Azure IoT device registration failed: {e}")
        raise


def configure_azure_grafana(context: 'DeploymentContext', terraform_outputs: dict) -> None:
    """Configure Azure Grafana datasources."""
    logger.info("  Configuring Azure Grafana...")
    try:
        from src.providers.azure.layers.layer_5_grafana import configure_grafana_datasource
        provider = context.providers.get("azure")
        if provider is None:
            logger.error("  ✗ Azure provider not initialized in context.providers")
            raise RuntimeError("Azure provider not initialized - cannot configure Grafana")
        hot_reader_url = terraform_outputs.get("azure_l3_hot_reader_url")
        if hot_reader_url:
            configure_grafana_datasource(provider, hot_reader_url)
            logger.info("  ✓ Azure Grafana configured")
        else:
            logger.warning("  No hot_reader_url in terraform outputs, skipping Grafana config")
    except ImportError:
        logger.warning("  layer_5_grafana not available, skipping config")
    except Exception as e:
        logger.error(f"  ✗ Azure Grafana config failed: {e}")
        raise
