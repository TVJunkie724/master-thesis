"""
Azure-specific deployment functions for Terraform.

This module handles SDK-owned DTDL model upload, IoT device registration,
and Grafana configuration after Terraform has published function packages.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.deployment_access.runtime_evidence import (
    SUPPORTED_DEPLOYMENT_ACCESS_PROFILES,
)

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)


def _is_active_phase8_profile(context: "DeploymentContext") -> bool:
    graph = getattr(context, "resolved_deployment_graph", None)
    profile_ref = getattr(graph, "profile_ref", {}) if graph is not None else {}
    return (
        profile_ref.get("id"),
        str(profile_ref.get("version")),
    ) in SUPPORTED_DEPLOYMENT_ACCESS_PROFILES


def _active_phase8_profile(context: "DeploymentContext") -> str:
    graph = getattr(context, "resolved_deployment_graph", None)
    profile_ref = getattr(graph, "profile_ref", {}) if graph is not None else {}
    profile = (profile_ref.get("id"), str(profile_ref.get("version")))
    if profile not in SUPPORTED_DEPLOYMENT_ACCESS_PROFILES:
        raise RuntimeError("Active Phase 8 architecture profile is required")
    return f"{profile[0]}@{profile[1]}"


def upload_dtdl_models(context: "DeploymentContext", project_path: Path) -> None:
    """Upload DTDL models to Azure Digital Twins."""
    logger.info("  Uploading DTDL models...")
    from src.providers.azure.layers.layer_4_adt import upload_dtdl_models as _upload

    provider = _require_azure_provider(context)
    _upload(
        provider,
        context.config,
        str(project_path),
        ensure_v2_seed=_is_active_phase8_profile(context),
    )
    logger.info("  DTDL models uploaded")


def register_azure_iot_devices(
    context: "DeploymentContext", project_path: Path
) -> None:
    """Register IoT devices via Azure IoT Hub SDK."""
    logger.info("  Registering Azure IoT devices...")
    from src.providers.azure.layers.layer_1_iot import register_iot_devices

    provider = _require_azure_provider(context)
    register_iot_devices(provider, context.config, str(project_path))
    logger.info("  Azure IoT devices registered")


def configure_azure_grafana(
    context: "DeploymentContext", terraform_outputs: dict
) -> None:
    """Configure Azure Grafana datasources."""
    logger.info("  Configuring Azure Grafana...")
    from src.providers.azure.layers.layer_5_grafana import (
        configure_five_layer_v2_grafana,
        configure_grafana_datasource,
    )

    provider = _require_azure_provider(context)
    if _is_active_phase8_profile(context):
        bundle = terraform_outputs.get("azure_component_visualization_output")
        if not isinstance(bundle, dict):
            raise RuntimeError(
                "Terraform output azure_component_visualization_output is required"
            )
        required = {
            "workspace_name",
            "access_url",
            "workspace_url",
            "reader_url",
            "reader_function_name",
        }
        missing = sorted(key for key in required if not bundle.get(key))
        if missing:
            raise RuntimeError(
                "Azure visualization output is missing: " + ", ".join(missing)
            )
        device_id, metric = _default_v2_dashboard_series(context.config)
        configure_five_layer_v2_grafana(
            provider,
            workspace_name=str(bundle["workspace_name"]),
            grafana_url=str(bundle["workspace_url"]).rstrip("/"),
            hot_reader_url=str(bundle["reader_url"]),
            function_app_name=str(bundle["reader_function_name"]),
            device_id=device_id,
            metric=metric,
            architecture_profile=_active_phase8_profile(context),
        )
        logger.info("  Azure Grafana configured")
        return
    hot_reader_url = terraform_outputs.get("azure_l3_hot_reader_url")
    if not hot_reader_url:
        raise RuntimeError("Terraform output azure_l3_hot_reader_url is required")
    configure_grafana_datasource(provider, hot_reader_url)
    logger.info("  Azure Grafana configured")


def _default_v2_dashboard_series(config) -> tuple[str, str]:
    devices = config.iot_devices if isinstance(config.iot_devices, list) else []
    device = devices[0] if devices and isinstance(devices[0], dict) else {}
    device_id = str(device.get("id") or device.get("device_id") or "poc-device-001")
    properties = device.get("properties", [])
    first_property = (
        properties[0]
        if isinstance(properties, list)
        and properties
        and isinstance(properties[0], dict)
        else {}
    )
    metric = str(first_property.get("name") or "temperature")
    return device_id, metric


def _require_azure_provider(context: "DeploymentContext"):
    provider = context.providers.get("azure")
    if provider is None:
        raise RuntimeError("Azure provider not initialized")
    return provider
