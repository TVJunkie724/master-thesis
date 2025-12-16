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
    
    Args:
        project_path: Path to project directory
        providers_config: Layer provider configuration
        terraform_outputs: Terraform output values
        load_credentials_fn: Function to load credentials
    """
    from src.providers.azure.layers.function_bundler import (
        bundle_l0_functions,
        bundle_l1_functions,
        bundle_l2_functions,
        bundle_l3_functions,
    )
    
    # Deploy L0 glue functions (if needed)
    l0_zip, l0_funcs = bundle_l0_functions(str(project_path), providers_config)
    if l0_zip and l0_funcs:
        app_name = terraform_outputs.get("azure_l0_function_app_name")
        if app_name:
            _deploy_to_azure_app(
                app_name, l0_zip, f"L0 ({len(l0_funcs)} functions)",
                terraform_outputs, load_credentials_fn
            )
    
    # Deploy L1 functions
    if providers_config.get("layer_1_provider") == "azure":
        app_name = terraform_outputs.get("azure_l1_function_app_name")
        if app_name:
            l1_zip = bundle_l1_functions(str(project_path))
            _deploy_to_azure_app(app_name, l1_zip, "L1", terraform_outputs, load_credentials_fn)
    
    # Deploy L2 functions
    if providers_config.get("layer_2_provider") == "azure":
        app_name = terraform_outputs.get("azure_l2_function_app_name")
        if app_name:
            l2_zip = bundle_l2_functions(str(project_path))
            _deploy_to_azure_app(app_name, l2_zip, "L2", terraform_outputs, load_credentials_fn)
    
    # Deploy L3 functions
    if providers_config.get("layer_3_hot_provider") == "azure":
        app_name = terraform_outputs.get("azure_l3_function_app_name")
        if app_name:
            l3_zip = bundle_l3_functions(str(project_path))
            _deploy_to_azure_app(app_name, l3_zip, "L3", terraform_outputs, load_credentials_fn)


def _deploy_to_azure_app(
    app_name: str,
    zip_bytes: bytes,
    label: str,
    terraform_outputs: dict,
    load_credentials_fn
) -> None:
    """Deploy ZIP bytes to an Azure Function App via Kudu."""
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
        creds = get_publishing_credentials_with_retry(
            resource_group=rg_name,
            app_name=app_name,
            credentials=azure_creds
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
