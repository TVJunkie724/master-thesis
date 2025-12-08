"""
Provider implementations package.

This package contains cloud provider implementations for AWS, Azure, and GCP.
Each provider is a self-contained module that implements the CloudProvider
protocol from core.protocols.

Auto-Registration:
    Importing this package triggers registration of all providers with
    the ProviderRegistry. This happens because each provider's __init__.py
    calls ProviderRegistry.register() when imported.

Package Structure:
    providers/
    ├── __init__.py         # This file - imports all providers
    ├── base.py             # Shared base classes and utilities
    ├── aws/                # AWS implementation
    │   ├── __init__.py     # Registers AWSProvider
    │   ├── provider.py     # AWSProvider class
    │   ├── clients.py      # boto3 client initialization
    │   ├── naming.py       # Resource naming functions
    │   └── layers/         # Layer-specific deployment
    ├── azure/              # Azure implementation (stub)
    └── gcp/                # GCP implementation (stub)

Usage:
    # Import this package to register all providers
    import providers
    
    # Now providers are available in the registry
    from core import ProviderRegistry
    provider = ProviderRegistry.get("aws")
"""

# Import provider modules to trigger auto-registration
# Each module's __init__.py calls ProviderRegistry.register()
from . import aws
from . import azure
from . import gcp

