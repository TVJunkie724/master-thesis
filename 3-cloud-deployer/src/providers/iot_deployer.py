"""
IoT Deployer - Per-Device Resource Deployment.

This module handles deployment of IoT device-specific resources:
- L1: IoT Things (per device)
- L2: Processor Lambdas (per device)
- L4: TwinMaker Component Types (per device)

These are separate from core layer resources because they scale
with the number of IoT devices defined in config_iot_devices.json.
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext


def _get_aws_iot_deployer():
    """Get AWS IoT deployer module (lazy import)."""
    import aws.iot_deployer_aws as iot_deployer_aws
    return iot_deployer_aws


# ==========================================
# Layer 1 - IoT Things (Per Device)
# ==========================================

def deploy_l1(context: 'DeploymentContext', provider: str) -> None:
    """Deploy IoT Things for all devices."""
    if provider == "aws":
        iot_aws = _get_aws_iot_deployer()
        for iot_device in context.config.iot_devices:
            logger.info(f"[L1-IoT] Creating IoT Thing: {iot_device.get('name', 'unknown')}")
            iot_aws.create_iot_thing(iot_device)
    elif provider in ("azure", "gcp"):
        raise NotImplementedError(f"{provider.upper()} IoT deployment not implemented yet.")
    else:
        raise ValueError(f"Unsupported provider: '{provider}'")


def destroy_l1(context: 'DeploymentContext', provider: str) -> None:
    """Destroy IoT Things for all devices."""
    if provider == "aws":
        iot_aws = _get_aws_iot_deployer()
        for iot_device in context.config.iot_devices:
            logger.info(f"[L1-IoT] Destroying IoT Thing: {iot_device.get('name', 'unknown')}")
            iot_aws.destroy_iot_thing(iot_device)
    elif provider in ("azure", "gcp"):
        raise NotImplementedError(f"{provider.upper()} IoT deployment not implemented yet.")
    else:
        raise ValueError(f"Unsupported provider: '{provider}'")


# ==========================================
# Layer 2 - Processor Lambdas (Per Device)
# ==========================================

def deploy_l2(context: 'DeploymentContext', provider: str) -> None:
    """Deploy Processor Lambdas for all devices."""
    if provider == "aws":
        iot_aws = _get_aws_iot_deployer()
        for iot_device in context.config.iot_devices:
            logger.info(f"[L2-IoT] Creating Processor for: {iot_device.get('name', 'unknown')}")
            iot_aws.create_processor_iam_role(iot_device)
            iot_aws.create_processor_lambda_function(iot_device)
        
        # Ingestion function for multi-cloud L1 → L2
        iot_aws.create_ingestion_lambda_function()
    elif provider in ("azure", "gcp"):
        raise NotImplementedError(f"{provider.upper()} IoT deployment not implemented yet.")
    else:
        raise ValueError(f"Unsupported provider: '{provider}'")


def destroy_l2(context: 'DeploymentContext', provider: str) -> None:
    """Destroy Processor Lambdas for all devices."""
    if provider == "aws":
        iot_aws = _get_aws_iot_deployer()
        for iot_device in context.config.iot_devices:
            logger.info(f"[L2-IoT] Destroying Processor for: {iot_device.get('name', 'unknown')}")
            iot_aws.destroy_processor_lambda_function(iot_device)
            iot_aws.destroy_processor_iam_role(iot_device)
        
        iot_aws.destroy_ingestion_lambda_function()
    elif provider in ("azure", "gcp"):
        raise NotImplementedError(f"{provider.upper()} IoT deployment not implemented yet.")
    else:
        raise ValueError(f"Unsupported provider: '{provider}'")


# ==========================================
# Layer 4 - TwinMaker Component Types (Per Device)
# ==========================================

def deploy_l4(context: 'DeploymentContext', provider: str) -> None:
    """Deploy TwinMaker Component Types for all devices."""
    if provider == "aws":
        iot_aws = _get_aws_iot_deployer()
        for iot_device in context.config.iot_devices:
            logger.info(f"[L4-IoT] Creating Component Type for: {iot_device.get('name', 'unknown')}")
            iot_aws.create_twinmaker_component_type(iot_device)
    elif provider in ("azure", "gcp"):
        raise NotImplementedError(f"{provider.upper()} IoT deployment not implemented yet.")
    else:
        raise ValueError(f"Unsupported provider: '{provider}'")


def destroy_l4(context: 'DeploymentContext', provider: str) -> None:
    """Destroy TwinMaker Component Types for all devices."""
    if provider == "aws":
        iot_aws = _get_aws_iot_deployer()
        for iot_device in context.config.iot_devices:
            logger.info(f"[L4-IoT] Destroying Component Type for: {iot_device.get('name', 'unknown')}")
            iot_aws.destroy_twinmaker_component_type(iot_device)
    elif provider in ("azure", "gcp"):
        raise NotImplementedError(f"{provider.upper()} IoT deployment not implemented yet.")
    else:
        raise ValueError(f"Unsupported provider: '{provider}'")


# ==========================================
# Full IoT Deployment
# ==========================================

def deploy(context: 'DeploymentContext', provider: str) -> None:
    """Deploy all IoT resources (L1, L2, L4)."""
    deploy_l1(context, provider)
    deploy_l2(context, provider)
    deploy_l4(context, provider)


def destroy(context: 'DeploymentContext', provider: str) -> None:
    """Destroy all IoT resources (reverse order)."""
    destroy_l4(context, provider)
    destroy_l2(context, provider)
    destroy_l1(context, provider)



