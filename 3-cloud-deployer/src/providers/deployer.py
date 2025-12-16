"""
Core Deployer - Multi-Cloud Deployment Orchestration.

This module provides the main entry points for deploying and destroying
cloud resources across all supported providers (AWS, Azure, GCP).

Architecture:
    - Uses DeploymentContext for all configuration and state
    - Uses ProviderRegistry to get provider implementations
    - Each provider's DeployerStrategy handles layer-specific logic

Usage:
    context = create_deployment_context("my-project")
    deploy_l1(context, "aws")
    deploy_l2(context, "aws")
    ...
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext


def _get_strategy(context: 'DeploymentContext', provider_name: str):
    """Get the deployer strategy for a provider."""
    if provider_name not in context.providers:
        raise ValueError(
            f"Provider '{provider_name}' not initialized in context. "
            f"Available: {list(context.providers.keys())}"
        )
    provider = context.providers[provider_name]
    return provider.get_deployer_strategy()


# ==========================================
# Layer 0 - Glue (Cross-Cloud HTTP Receivers)
# ==========================================

def deploy_l0(context: 'DeploymentContext', provider: str) -> None:
    """Deploy Layer 0 (Glue) - cross-cloud HTTP receivers.
    
    Must run BEFORE other layers to ensure URLs are available.
    """
    logger.info(f"[L0] Deploying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.deploy_l0(context)


def destroy_l0(context: 'DeploymentContext', provider: str) -> None:
    """Destroy Layer 0 (Glue) components."""
    logger.info(f"[L0] Destroying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.destroy_l0(context)


# ==========================================
# Layer 1 - Data Acquisition
# ==========================================

def deploy_l1(context: 'DeploymentContext', provider: str) -> None:
    """Deploy Layer 1 (Data Acquisition) components."""
    logger.info(f"[L1] Deploying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.deploy_l1(context)


def destroy_l1(context: 'DeploymentContext', provider: str) -> None:
    """Destroy Layer 1 (Data Acquisition) components."""
    logger.info(f"[L1] Destroying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.destroy_l1(context)


# ==========================================
# Layer 2 - Data Processing
# ==========================================

def deploy_l2(context: 'DeploymentContext', provider: str) -> None:
    """Deploy Layer 2 (Data Processing) components."""
    logger.info(f"[L2] Deploying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.deploy_l2(context)


def destroy_l2(context: 'DeploymentContext', provider: str) -> None:
    """Destroy Layer 2 (Data Processing) components."""
    logger.info(f"[L2] Destroying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.destroy_l2(context)


# ==========================================
# Layer 3 - Data Storage
# ==========================================

def deploy_l3_hot(context: 'DeploymentContext', provider: str) -> None:
    """Deploy Layer 3 Hot Storage components."""
    logger.info(f"[L3-Hot] Deploying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.deploy_l3_hot(context)


def destroy_l3_hot(context: 'DeploymentContext', provider: str) -> None:
    """Destroy Layer 3 Hot Storage components."""
    logger.info(f"[L3-Hot] Destroying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.destroy_l3_hot(context)


def deploy_l3_cold(context: 'DeploymentContext', provider: str) -> None:
    """Deploy Layer 3 Cold Storage components."""
    logger.info(f"[L3-Cold] Deploying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.deploy_l3_cold(context)


def destroy_l3_cold(context: 'DeploymentContext', provider: str) -> None:
    """Destroy Layer 3 Cold Storage components."""
    logger.info(f"[L3-Cold] Destroying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.destroy_l3_cold(context)


def deploy_l3_archive(context: 'DeploymentContext', provider: str) -> None:
    """Deploy Layer 3 Archive Storage components."""
    logger.info(f"[L3-Archive] Deploying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.deploy_l3_archive(context)


def destroy_l3_archive(context: 'DeploymentContext', provider: str) -> None:
    """Destroy Layer 3 Archive Storage components."""
    logger.info(f"[L3-Archive] Destroying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.destroy_l3_archive(context)


def deploy_l3(context: 'DeploymentContext', provider: str) -> None:
    """Deploy all L3 storage tiers (hot, cold, archive)."""
    deploy_l3_hot(context, provider)
    deploy_l3_cold(context, provider)
    deploy_l3_archive(context, provider)


def destroy_l3(context: 'DeploymentContext', provider: str) -> None:
    """Destroy all L3 storage tiers."""
    destroy_l3_archive(context, provider)
    destroy_l3_cold(context, provider)
    destroy_l3_hot(context, provider)


# ==========================================
# Layer 4 - Digital Twin
# ==========================================

def deploy_l4(context: 'DeploymentContext', provider: str) -> None:
    """Deploy Layer 4 (Digital Twin) components."""
    logger.info(f"[L4] Deploying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.deploy_l4(context)


def destroy_l4(context: 'DeploymentContext', provider: str) -> None:
    """Destroy Layer 4 (Digital Twin) components."""
    logger.info(f"[L4] Destroying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.destroy_l4(context)


# ==========================================
# Layer 5 - Visualization
# ==========================================

def deploy_l5(context: 'DeploymentContext', provider: str) -> None:
    """Deploy Layer 5 (Visualization) components."""
    logger.info(f"[L5] Deploying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.deploy_l5(context)


def destroy_l5(context: 'DeploymentContext', provider: str) -> None:
    """Destroy Layer 5 (Visualization) components."""
    logger.info(f"[L5] Destroying for {provider}...")
    strategy = _get_strategy(context, provider)
    strategy.destroy_l5(context)


# ==========================================
# Full Deployment
# ==========================================

def deploy_all(context: 'DeploymentContext', provider: str) -> None:
    """
    Deploy all layers using Terraform (primary approach).
    
    This function uses Terraform for infrastructure provisioning,
    with Python handling code deployment and post-deployment operations.
    
    Args:
        context: Deployment context with config and credentials
        provider: Cloud provider name (aws, azure, gcp)
    
    Note:
        For SDK-only deployment (deprecated), use deploy_all_sdk().
    """
    logger.info(f"Deploying all layers via Terraform for provider: {provider}")
    
    from pathlib import Path
    from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
    
    terraform_dir = str(Path(__file__).parent.parent / "terraform")
    
    strategy = TerraformDeployerStrategy(
        terraform_dir=terraform_dir,
        project_path=str(context.project_path)
    )
    
    strategy.deploy_all(context)


def destroy_all(context: 'DeploymentContext', provider: str) -> None:
    """
    Destroy all layers using Terraform.
    
    Args:
        context: Deployment context with config and credentials
        provider: Cloud provider name
    """
    logger.info(f"Destroying all layers via Terraform for provider: {provider}")
    
    from pathlib import Path
    from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
    
    terraform_dir = str(Path(__file__).parent.parent / "terraform")
    
    strategy = TerraformDeployerStrategy(
        terraform_dir=terraform_dir,
        project_path=str(context.project_path)
    )
    
    strategy.destroy_all(context)


# ==========================================
# SDK Deployment (DEPRECATED)
# ==========================================

def deploy_all_sdk(context: 'DeploymentContext', provider: str) -> None:
    """
    [DEPRECATED] Deploy all layers using Python SDK.
    
    Use deploy_all() instead, which uses Terraform.
    """
    import warnings
    warnings.warn(
        "deploy_all_sdk() is deprecated. Use deploy_all() with Terraform instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Pre-deployment safety check
    if provider in context.providers:
        provider_instance = context.providers[provider]
        if hasattr(provider_instance, 'check_if_twin_exists'):
            if provider_instance.check_if_twin_exists():
                raise ValueError(
                    f"Digital Twin '{context.config.digital_twin_name}' already exists "
                    f"for provider '{provider}'. Destroy it first or use a different name."
                )
    
    deploy_l0(context, provider)
    deploy_l1(context, provider)
    deploy_l2(context, provider)
    deploy_l3(context, provider)
    deploy_l4(context, provider)
    deploy_l5(context, provider)


def destroy_all_sdk(context: 'DeploymentContext', provider: str) -> None:
    """
    [DEPRECATED] Destroy all layers using Python SDK.
    
    Use destroy_all() instead, which uses Terraform.
    """
    import warnings
    warnings.warn(
        "destroy_all_sdk() is deprecated. Use destroy_all() with Terraform instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    destroy_l5(context, provider)
    destroy_l4(context, provider)
    destroy_l3(context, provider)
    destroy_l2(context, provider)
    destroy_l1(context, provider)
    destroy_l0(context, provider)


# ==========================================
# Terraform Deployment (Alternative)
# ==========================================

def deploy_all_terraform(context: 'DeploymentContext', terraform_dir: str = None) -> dict:
    """
    Deploy all infrastructure using Terraform (hybrid approach).
    
    Terraform handles infrastructure provisioning, Python handles:
    - Function code deployment (Kudu ZIP)
    - DTDL model upload (Azure SDK)
    - IoT device registration (Azure SDK)
    - Grafana datasource configuration (API)
    
    Args:
        context: Deployment context with project config
        terraform_dir: Path to Terraform directory (defaults to src/terraform/)
    
    Returns:
        Dictionary of Terraform outputs
    
    Raises:
        TerraformError: If Terraform apply fails
    """
    from pathlib import Path
    from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
    
    if terraform_dir is None:
        terraform_dir = str(Path(__file__).parent.parent / "terraform")
    
    logger.info(f"Starting Terraform deployment for {context.project_name}")
    
    strategy = TerraformDeployerStrategy(
        terraform_dir=terraform_dir,
        project_path=str(context.project_path)
    )
    
    return strategy.deploy_all(context)


def destroy_all_terraform(context: 'DeploymentContext', terraform_dir: str = None) -> None:
    """
    Destroy all Terraform-managed infrastructure.
    
    Args:
        context: Deployment context with project config
        terraform_dir: Path to Terraform directory
    """
    from pathlib import Path
    from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
    
    if terraform_dir is None:
        terraform_dir = str(Path(__file__).parent.parent / "terraform")
    
    logger.info(f"Starting Terraform destroy for {context.project_name}")
    
    strategy = TerraformDeployerStrategy(
        terraform_dir=terraform_dir,
        project_path=str(context.project_path)
    )
    
    strategy.destroy_all()

# ==========================================
# Specialized Operations
# ==========================================

def redeploy_event_checker(context: 'DeploymentContext', provider: str) -> None:
    """Redeploy the event checker function (AWS specific for now)."""
    if provider != "aws":
        raise NotImplementedError("Event checker redeployment only supported for AWS.")
    
    if "aws" not in context.providers:
        raise ValueError("AWS provider not initialized in context.")
        
    aws_provider = context.providers["aws"]
    
    # helper import until generalized
    from providers.aws.layers import layer_2_compute
    
    logger.info("[L2] Redeploying Event Checker Lambda...")
    try:
        layer_2_compute.destroy_event_checker_lambda_function(aws_provider)
    except Exception as e:
        logger.warning(f"Failed to destroy event checker (might not exist): {e}")
        
    layer_2_compute.create_event_checker_lambda_function(aws_provider, context.config, context.project_path)


# ==========================================
# Info / Status Checks
# ==========================================

def info_l0(context: 'DeploymentContext', provider: str) -> None:
    """Check status of Layer 0 (Glue) components."""
    strategy = _get_strategy(context, provider)
    strategy.info_l0(context)


def info_l1(context: 'DeploymentContext', provider: str) -> None:
    """Check status of Layer 1 (Data Acquisition) components."""
    strategy = _get_strategy(context, provider)
    strategy.info_l1(context)


def info_l2(context: 'DeploymentContext', provider: str) -> None:
    """Check status of Layer 2 (Data Processing) components."""
    strategy = _get_strategy(context, provider)
    strategy.info_l2(context)


def info_l3_hot(context: 'DeploymentContext', provider: str) -> None:
    """Check status of Layer 3 Hot Storage components."""
    strategy = _get_strategy(context, provider)
    strategy.info_l3_hot(context)


def info_l3_cold(context: 'DeploymentContext', provider: str) -> None:
    """Check status of Layer 3 Cold Storage components."""
    strategy = _get_strategy(context, provider)
    strategy.info_l3_cold(context)


def info_l3_archive(context: 'DeploymentContext', provider: str) -> None:
    """Check status of Layer 3 Archive Storage components."""
    strategy = _get_strategy(context, provider)
    strategy.info_l3_archive(context)


def info_l3(context: 'DeploymentContext', provider: str) -> None:
    """Check status of all L3 storage tiers."""
    info_l3_hot(context, provider)
    info_l3_cold(context, provider)
    info_l3_archive(context, provider)


def info_l4(context: 'DeploymentContext', provider: str) -> None:
    """Check status of Layer 4 (Digital Twin) components."""
    strategy = _get_strategy(context, provider)
    strategy.info_l4(context)


def info_l5(context: 'DeploymentContext', provider: str) -> None:
    """Check status of Layer 5 (Visualization) components."""
    strategy = _get_strategy(context, provider)
    strategy.info_l5(context)


def info_all(context: 'DeploymentContext', provider: str) -> None:
    """Check status of all layers."""
    info_l0(context, provider)
    info_l1(context, provider)
    info_l2(context, provider)
    info_l3(context, provider)
    info_l4(context, provider)
    info_l5(context, provider)


