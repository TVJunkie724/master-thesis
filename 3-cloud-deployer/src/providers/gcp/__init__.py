"""
GCP Provider package.

This package provides the Google Cloud implementation of the CloudProvider protocol.
Auto-registers with ProviderRegistry on import.

Status: STUB - Minimal implementation for pattern validation.
"""

from src.core.registry import ProviderRegistry
from .provider import GCPProvider

# Auto-register this provider
ProviderRegistry.register("gcp", GCPProvider)

__all__ = ["GCPProvider"]
