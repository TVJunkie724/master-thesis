"""
Core abstractions for the multi-cloud deployer.

This package provides the foundational interfaces and utilities for supporting
multiple cloud providers (AWS, Azure, GCP) in the Digital Twin deployment system.

Modules:
    protocols: Interface definitions (CloudProvider)
    context: DeploymentContext for dependency injection
    registry: ProviderRegistry for dynamic provider lookup
    config_loader: Configuration loading utilities
    exceptions: Custom exception types for deployment operations

Usage:
    from core import CloudProvider, DeploymentContext
    from core import ProviderRegistry
    
    # Get a provider by name
    provider = ProviderRegistry.get("aws")
    
    # Create deployment context
    context = DeploymentContext(...)
    
    # Check status using the provider directly
    status = provider.info_l1(context)
"""

from .protocols import CloudProvider, DeployerStrategy
from .context import DeploymentContext, ProjectConfig
from .registry import ProviderRegistry
from .exceptions import DeploymentError, ProviderNotFoundError, ConfigurationError

__all__ = [
    # Protocols
    "CloudProvider",
    "DeployerStrategy",
    # Context
    "DeploymentContext",
    "ProjectConfig",
    # Registry
    "ProviderRegistry",
    # Exceptions
    "DeploymentError",
    "ProviderNotFoundError",
    "ConfigurationError",
]
