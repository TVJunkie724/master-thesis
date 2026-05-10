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

from pathlib import Path
from typing import TYPE_CHECKING
from logger import logger
from src.core.workspace import deployment_workspace

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


def create_terraform_strategy(
    context: 'DeploymentContext',
    terraform_dir: str | None = None,
    project_path: str | None = None,
):
    """Create the canonical Terraform strategy for deploy/destroy operations."""
    from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy

    resolved_terraform_dir = terraform_dir or str(Path(__file__).parent.parent / "terraform")
    resolved_project_path = project_path or str(context.project_path)

    return TerraformDeployerStrategy(
        terraform_dir=resolved_terraform_dir,
        project_path=resolved_project_path,
    )


# ==========================================
# Full Deployment (Terraform)
# ==========================================

def deploy_all(context: 'DeploymentContext', provider: str) -> dict:
    """
    Deploy all layers using Terraform (primary approach).
    
    This function uses Terraform for infrastructure provisioning,
    with Python handling code deployment and post-deployment operations.
    
    Args:
        context: Deployment context with config and credentials
        provider: Cloud provider name (aws, azure, gcp)
    
    Returns:
        Dictionary of Terraform outputs
    """
    logger.info(f"Deploying all layers via Terraform for provider: {provider}")

    with deployment_workspace(context) as (runtime_context, _workspace):
        strategy = create_terraform_strategy(runtime_context)
        return strategy.deploy_all(runtime_context)


def destroy_all(context: 'DeploymentContext', provider: str) -> None:
    """
    Destroy all layers using Terraform, then run SDK cleanup as fallback.
    
    This two-phase approach ensures resources are cleaned up even when:
    - Terraform state is corrupted or lost
    - Terraform destroy fails partially
    - Resources were created via SDK (not in Terraform state)
    
    Args:
        context: Deployment context with config and credentials
        provider: Cloud provider name
    """
    # ==========================================
    # PHASE 1: TERRAFORM DESTROY
    # ==========================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("  PHASE 1: TERRAFORM DESTROY")
    logger.info("=" * 60)
    logger.info(f"Destroying all layers via Terraform for provider: {provider}")
    
    terraform_error = None
    with deployment_workspace(context) as (runtime_context, _workspace):
        strategy = create_terraform_strategy(runtime_context)

        try:
            strategy.destroy_all(runtime_context)
        except Exception as e:
            terraform_error = e
            logger.warning(f"Terraform destroy failed/partial: {e}")
            # Continue to SDK cleanup regardless

        # ==========================================
        # PHASE 2: SDK FALLBACK CLEANUP
        # ==========================================
        logger.info("")
        logger.info("=" * 60)
        logger.info("  PHASE 2: SDK FALLBACK CLEANUP")
        logger.info("=" * 60)

        _run_sdk_cleanup(runtime_context)
    
    if terraform_error:
        logger.info("Destroy completed with Terraform errors (SDK cleanup ran as fallback)")


def _run_sdk_cleanup(context: 'DeploymentContext') -> None:
    """
    Run SDK cleanup for all providers as fallback after terraform destroy.
    
    This catches orphaned resources that Terraform may have missed due to:
    - State corruption
    - Partial destroy failures
    - Resources created via SDK (not in Terraform state)
    - Control-plane timing issues (TwinMaker, Firestore)
    """
    # Get prefix from config
    prefix = _config_value(context.config, "digital_twin_name", "")
    
    # CRITICAL: Fail-safe guard against empty prefix
    # An empty prefix would match ALL resources in the account!
    if not prefix or len(prefix) < 3:
        logger.error(f"Invalid prefix '{prefix}' for cleanup - skipping SDK cleanup to prevent accidental deletion")
        return
    
    credentials = context.credentials
    
    logger.info(f"[SDK Cleanup] Running fallback cleanup for prefix: {prefix}")
    
    # Import cleanup functions
    from src.providers.aws.cleanup import cleanup_aws_resources
    from src.providers.azure.cleanup import cleanup_azure_resources
    from src.providers.gcp.cleanup import cleanup_gcp_resources
    
    # AWS cleanup (best-effort)
    if credentials.get("aws"):
        logger.info("[SDK Cleanup] AWS...")
        try:
            cleanup_aws_resources(
                credentials, prefix,
                cleanup_identity_user=False,
                platform_user_email="",
                dry_run=False
            )
        except Exception as e:
            logger.warning(f"[SDK Cleanup] AWS cleanup failed: {e}")
    else:
        logger.info("[SDK Cleanup] AWS - skipped (no credentials)")
    
    # Azure cleanup (best-effort)
    if credentials.get("azure"):
        logger.info("[SDK Cleanup] Azure...")
        try:
            cleanup_azure_resources(
                credentials, prefix,
                cleanup_entra_user=False,
                platform_user_email="",
                dry_run=False
            )
        except Exception as e:
            logger.warning(f"[SDK Cleanup] Azure cleanup failed: {e}")
    else:
        logger.info("[SDK Cleanup] Azure - skipped (no credentials)")
    
    # GCP cleanup (best-effort)
    if credentials.get("gcp"):
        logger.info("[SDK Cleanup] GCP...")
        try:
            cleanup_gcp_resources(credentials, prefix, dry_run=False)
        except Exception as e:
            logger.warning(f"[SDK Cleanup] GCP cleanup failed: {e}")
    else:
        logger.info("[SDK Cleanup] GCP - skipped (no credentials)")
    
    logger.info("[SDK Cleanup] Fallback cleanup complete")


def _config_value(config, key: str, default=None):
    """Read a project config value from either a dataclass or legacy dict."""
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


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
    logger.info(f"Starting Terraform deployment for {context.project_name}")
    with deployment_workspace(context) as (runtime_context, _workspace):
        strategy = create_terraform_strategy(
            runtime_context,
            terraform_dir=terraform_dir,
            project_path=str(runtime_context.project_path),
        )
        return strategy.deploy_all(runtime_context)


def destroy_all_terraform(context: 'DeploymentContext', terraform_dir: str = None) -> None:
    """
    Destroy all Terraform-managed infrastructure.
    
    Args:
        context: Deployment context with project config
        terraform_dir: Path to Terraform directory
    """
    logger.info(f"Starting Terraform destroy for {context.project_name}")
    with deployment_workspace(context) as (runtime_context, _workspace):
        strategy = create_terraform_strategy(
            runtime_context,
            terraform_dir=terraform_dir,
            project_path=str(runtime_context.project_path),
        )
        strategy.destroy_all(runtime_context)


async def deploy_all_stream(
    context: 'DeploymentContext',
    strategy=None,
    terraform_dir: str | None = None,
    project_path: str | None = None,
    output_sink: dict | None = None,
):
    """Stream canonical Terraform deployment log lines."""
    if strategy is not None:
        async for line in strategy.deploy_all_async(context):
            yield line
        if output_sink is not None:
            output_sink["outputs"] = strategy.get_outputs()
        return

    with deployment_workspace(context) as (runtime_context, _workspace):
        runtime_strategy = create_terraform_strategy(
            runtime_context,
            terraform_dir=terraform_dir,
            project_path=str(runtime_context.project_path),
        )
        async for line in runtime_strategy.deploy_all_async(runtime_context):
            yield line
        if output_sink is not None:
            output_sink["outputs"] = runtime_strategy.get_outputs()


async def destroy_all_stream(
    context: 'DeploymentContext',
    strategy=None,
    terraform_dir: str | None = None,
    project_path: str | None = None,
):
    """Stream canonical Terraform destroy log lines."""
    if strategy is not None:
        async for line in strategy.destroy_all_async(context):
            yield line
        return

    with deployment_workspace(context) as (runtime_context, _workspace):
        runtime_strategy = create_terraform_strategy(
            runtime_context,
            terraform_dir=terraform_dir,
            project_path=str(runtime_context.project_path),
        )
        async for line in runtime_strategy.destroy_all_async(runtime_context):
            yield line


def get_terraform_outputs(strategy) -> dict:
    """Return Terraform outputs from a canonical strategy instance."""
    return strategy.get_outputs()

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
