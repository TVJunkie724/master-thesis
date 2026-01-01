"""
Azure Provider package.

This package provides the Azure implementation of the CloudProvider protocol.
Auto-registers with ProviderRegistry on import.

Status: STUB - Minimal implementation for pattern validation.
"""

from src.core.registry import ProviderRegistry
from .provider import AzureProvider
from .cleanup import cleanup_azure_resources

# Auto-register this provider
ProviderRegistry.register("azure", AzureProvider)

__all__ = ["AzureProvider", "cleanup_azure_resources"]
