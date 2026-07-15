"""
Azure-specific deployment functions for Terraform.

This module handles SDK-owned DTDL model upload, IoT device registration,
and Grafana configuration after Terraform has published function packages.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)


def upload_dtdl_models(context: 'DeploymentContext', project_path: Path) -> None:
    """Upload DTDL models to Azure Digital Twins."""
    logger.info("  Uploading DTDL models...")
    from src.providers.azure.layers.layer_4_adt import upload_dtdl_models as _upload

    provider = _require_azure_provider(context)
    _upload(provider, context.config, str(project_path))
    logger.info("  DTDL models uploaded")


def register_azure_iot_devices(context: 'DeploymentContext', project_path: Path) -> None:
    """Register IoT devices via Azure IoT Hub SDK."""
    logger.info("  Registering Azure IoT devices...")
    from src.providers.azure.layers.layer_1_iot import register_iot_devices

    provider = _require_azure_provider(context)
    register_iot_devices(provider, context.config, str(project_path))
    logger.info("  Azure IoT devices registered")


def configure_azure_grafana(context: 'DeploymentContext', terraform_outputs: dict) -> None:
    """Configure Azure Grafana datasources."""
    logger.info("  Configuring Azure Grafana...")
    from src.providers.azure.layers.layer_5_grafana import configure_grafana_datasource

    provider = _require_azure_provider(context)
    hot_reader_url = terraform_outputs.get("azure_l3_hot_reader_url")
    if not hot_reader_url:
        raise RuntimeError("Terraform output azure_l3_hot_reader_url is required")
    configure_grafana_datasource(provider, hot_reader_url)
    logger.info("  Azure Grafana configured")


def _require_azure_provider(context: 'DeploymentContext'):
    provider = context.providers.get("azure")
    if provider is None:
        raise RuntimeError("Azure provider not initialized")
    return provider
