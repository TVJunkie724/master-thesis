"""
Core Deployer - Multi-Cloud Deployment Orchestration.

This module provides the main entry points for deploying and destroying
cloud resources across all supported providers (AWS, Azure, GCP).

Architecture:
    - Uses DeploymentContext for all configuration and state
    - Uses ProviderRegistry to get provider implementations
    - Terraform is the primary deployment mechanism

Usage:
    context = create_deployment_context("my-project")
    deploy_all(context, "aws")  # Uses Terraform
"""

from typing import TYPE_CHECKING
from logger import logger

if TYPE_CHECKING:
    from src.core.context import DeploymentContext


def _get_strategy(context: 'DeploymentContext', provider_name: str):
    """
    Get the provider for status checks.
    
    Note: For backwards compatibility, returns the provider directly.
    The provider now has info_l* methods directly (no separate strategy).
    """
    if provider_name not in context.providers:
        raise ValueError(
            f"Provider '{provider_name}' not initialized in context. "
            f"Available: {list(context.providers.keys())}"
        )
    return context.providers[provider_name]


# ==========================================
# Full Deployment (Terraform)
# ==========================================

def deploy_all(context: 'DeploymentContext', provider: str) -> None:
    """
    Deploy all layers using Terraform (primary approach).
    
    This function uses Terraform for infrastructure provisioning,
    with Python handling code deployment and post-deployment operations.
    
    Args:
        context: Deployment context with config and credentials
        provider: Cloud provider name (aws, azure, gcp)
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
# Terraform Deployment (Alternative Entry Point)
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
