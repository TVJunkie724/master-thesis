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
from src.core.observability import OperationContext, operation_step
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

def deploy_all(
    context: 'DeploymentContext',
    provider: str,
    operation_context: OperationContext | None = None,
) -> dict:
    """
    Deploy all layers using Terraform (primary approach).
    
    This function uses Terraform for infrastructure and function packages,
    with Python handling explicitly SDK-owned post-deployment operations.
    
    Args:
        context: Deployment context with config and credentials
        provider: Cloud provider name (aws, azure, gcp)
    
    Returns:
        Dictionary of Terraform outputs
    """
    logger.info(
        "Deploying all layers via Terraform for provider: %s",
        provider,
        extra=_log_extra(operation_context, "deployer_entry"),
    )

    with deployment_workspace(context, operation_context=operation_context) as (runtime_context, _workspace):
        strategy = create_terraform_strategy(runtime_context)
        if operation_context:
            with operation_step(logger, operation_context, "terraform_deploy"):
                return strategy.deploy_all(runtime_context)
        return strategy.deploy_all(runtime_context)


def destroy_all(
    context: 'DeploymentContext',
    provider: str,
    operation_context: OperationContext | None = None,
) -> None:
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
    logger.info(
        "Destroying all layers via Terraform for provider: %s",
        provider,
        extra=_log_extra(operation_context, "deployer_entry"),
    )

    with deployment_workspace(context, operation_context=operation_context) as (runtime_context, _workspace):
        strategy = create_terraform_strategy(runtime_context)
        if operation_context:
            with operation_step(logger, operation_context, "terraform_destroy"):
                result = strategy.destroy_all(runtime_context)
        else:
            result = strategy.destroy_all(runtime_context)

    failed_providers = sorted(
        provider_name
        for provider_name, success in result.sdk_fallback_results.items()
        if not success
    )
    if failed_providers:
        raise RuntimeError(
            "Provider fallback cleanup failed: " + ", ".join(failed_providers)
        )
    if not result.terraform_success:
        logger.info(
            "Destroy completed with Terraform errors (SDK cleanup ran as fallback)",
            extra=_log_extra(operation_context, "destroy_complete"),
        )


def _log_extra(
    operation_context: OperationContext | None,
    phase: str,
) -> dict | None:
    if operation_context is None:
        return None
    return operation_context.log_extra(phase=phase)


# ==========================================
# Terraform Deployment (Alternative Entry Point)
# ==========================================

def deploy_all_terraform(
    context: 'DeploymentContext',
    terraform_dir: str = None,
    operation_context: OperationContext | None = None,
) -> dict:
    """
    Deploy all infrastructure using the canonical Terraform approach.

    Terraform handles infrastructure and function packages. Python handles:
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
    logger.info(
        "Starting Terraform deployment for %s",
        context.project_name,
        extra=_log_extra(operation_context, "deployer_entry"),
    )
    with deployment_workspace(context, operation_context=operation_context) as (runtime_context, _workspace):
        strategy = create_terraform_strategy(
            runtime_context,
            terraform_dir=terraform_dir,
            project_path=str(runtime_context.project_path),
        )
        if operation_context:
            with operation_step(logger, operation_context, "terraform_deploy"):
                return strategy.deploy_all(runtime_context)
        return strategy.deploy_all(runtime_context)


def destroy_all_terraform(
    context: 'DeploymentContext',
    terraform_dir: str = None,
    operation_context: OperationContext | None = None,
) -> None:
    """
    Destroy all Terraform-managed infrastructure.
    
    Args:
        context: Deployment context with project config
        terraform_dir: Path to Terraform directory
    """
    logger.info(
        "Starting Terraform destroy for %s",
        context.project_name,
        extra=_log_extra(operation_context, "deployer_entry"),
    )
    with deployment_workspace(context, operation_context=operation_context) as (runtime_context, _workspace):
        strategy = create_terraform_strategy(
            runtime_context,
            terraform_dir=terraform_dir,
            project_path=str(runtime_context.project_path),
        )
        if operation_context:
            with operation_step(logger, operation_context, "terraform_destroy"):
                strategy.destroy_all(runtime_context)
        else:
            strategy.destroy_all(runtime_context)


async def deploy_all_stream(
    context: 'DeploymentContext',
    strategy=None,
    terraform_dir: str | None = None,
    project_path: str | None = None,
    output_sink: dict | None = None,
    operation_context: OperationContext | None = None,
):
    """Stream canonical Terraform deployment log lines."""
    if strategy is not None:
        async for line in strategy.deploy_all_async(context):
            yield line
        if output_sink is not None:
            output_sink["outputs"] = strategy.get_outputs()
        return

    with deployment_workspace(context, operation_context=operation_context) as (runtime_context, _workspace):
        runtime_strategy = create_terraform_strategy(
            runtime_context,
            terraform_dir=terraform_dir,
            project_path=str(runtime_context.project_path),
        )
        if operation_context:
            with operation_step(logger, operation_context, "terraform_deploy_stream"):
                async for line in runtime_strategy.deploy_all_async(runtime_context):
                    yield line
        else:
            async for line in runtime_strategy.deploy_all_async(runtime_context):
                yield line
        if output_sink is not None:
            output_sink["outputs"] = runtime_strategy.get_outputs()


async def destroy_all_stream(
    context: 'DeploymentContext',
    strategy=None,
    terraform_dir: str | None = None,
    project_path: str | None = None,
    operation_context: OperationContext | None = None,
):
    """Stream canonical Terraform destroy log lines."""
    if strategy is not None:
        async for line in strategy.destroy_all_async(context):
            yield line
        return

    with deployment_workspace(context, operation_context=operation_context) as (runtime_context, _workspace):
        runtime_strategy = create_terraform_strategy(
            runtime_context,
            terraform_dir=terraform_dir,
            project_path=str(runtime_context.project_path),
        )
        if operation_context:
            with operation_step(logger, operation_context, "terraform_destroy_stream"):
                async for line in runtime_strategy.destroy_all_async(runtime_context):
                    yield line
        else:
            async for line in runtime_strategy.destroy_all_async(runtime_context):
                yield line


def get_terraform_outputs(strategy) -> dict:
    """Return Terraform outputs from a canonical strategy instance."""
    return strategy.get_outputs()
