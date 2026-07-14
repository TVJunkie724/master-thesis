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
