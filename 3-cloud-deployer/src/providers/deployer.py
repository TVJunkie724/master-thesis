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
    """Deploy all layers for a provider."""
    deploy_l1(context, provider)
    deploy_l2(context, provider)
    deploy_l3(context, provider)
    deploy_l4(context, provider)
    deploy_l5(context, provider)


def destroy_all(context: 'DeploymentContext', provider: str) -> None:
    """Destroy all layers for a provider (reverse order)."""
    destroy_l5(context, provider)
    destroy_l4(context, provider)
    destroy_l3(context, provider)
    destroy_l2(context, provider)
    destroy_l1(context, provider)


# ==========================================
# Legacy Compatibility Wrapper
# (Temporarily bridges old globals-based calls)
# ==========================================

def _create_legacy_context():
    """Create a DeploymentContext from legacy globals for backward compatibility."""
    # Import here to avoid circular imports during transition
    import globals
    from pathlib import Path
    from src.core.context import DeploymentContext, ProjectConfig
    from src.core.registry import ProviderRegistry
    
    # Build config from globals
    config = ProjectConfig(
        digital_twin_name=globals.config.get("digital_twin_name", ""),
        hot_storage_size_in_days=globals.config.get("hot_storage_size_in_days", 7),
        cold_storage_size_in_days=globals.config.get("cold_storage_size_in_days", 30),
        mode=globals.config.get("mode", "DEBUG"),
        iot_devices=globals.config_iot_devices,
        events=globals.config_events,
        hierarchy=globals.config_hierarchy,
        providers=globals.config_providers,
        optimization=globals.config_optimization,
        inter_cloud=globals.config_inter_cloud,
    )
    
    # Create context
    context = DeploymentContext(
        project_name=globals.CURRENT_PROJECT,
        project_path=Path(globals.get_project_upload_path()),
        config=config,
    )
    
    # Initialize providers
    for provider_name in {"aws", "azure", "gcp"}:
        try:
            provider = ProviderRegistry.get(provider_name)
            creds = getattr(globals, f"config_credentials_{provider_name}", None)
            if creds:
                provider.initialize_clients(creds, config.digital_twin_name)
                context.providers[provider_name] = provider
        except (KeyError, AttributeError):
            pass
    
    return context


# Legacy entry points (for backward compatibility)
def deploy(provider: str) -> None:
    """Legacy deploy function - creates context from globals."""
    context = _create_legacy_context()
    deploy_all(context, provider)


def destroy(provider: str) -> None:
    """Legacy destroy function - creates context from globals."""
    context = _create_legacy_context()
    destroy_all(context, provider)
