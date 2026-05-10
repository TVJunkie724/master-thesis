"""
Core abstractions for the multi-cloud deployer.

This package provides the foundational interfaces and utilities for supporting
multiple cloud providers (AWS, Azure, GCP) in the Digital Twin deployment system.

Modules:
    protocols: Interface definitions (CloudProvider)
    context: DeploymentContext for dependency injection
    workspace: Ephemeral workspace preparation
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
from .paths import DeploymentPaths, resolve_deployment_paths
from .observability import OperationContext, operation_step, redact_sensitive
from .workspace import (
    EphemeralWorkspace,
    create_ephemeral_workspace,
    deployment_workspace,
    ephemeral_workspace,
    sync_runtime_outputs,
)
from .registry import ProviderRegistry
from .exceptions import DeploymentError, ProviderNotFoundError, ConfigurationError

__all__ = [
    # Protocols
    "CloudProvider",
    "DeployerStrategy",
    # Context
    "DeploymentContext",
    "DeploymentPaths",
    "EphemeralWorkspace",
    "OperationContext",
    "ProjectConfig",
    "create_ephemeral_workspace",
    "deployment_workspace",
    "ephemeral_workspace",
    "operation_step",
    "redact_sensitive",
    "resolve_deployment_paths",
    "sync_runtime_outputs",
    # Registry
    "ProviderRegistry",
    # Exceptions
    "DeploymentError",
    "ProviderNotFoundError",
    "ConfigurationError",
]
