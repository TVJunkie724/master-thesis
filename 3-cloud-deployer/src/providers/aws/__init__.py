"""
AWS Provider package.

This package implements the CloudProvider protocol for Amazon Web Services.
AWS deployment behavior is owned by the canonical provider/Terraform path.

Auto-Registration:
    Importing this package registers AWSProvider with the ProviderRegistry.
    This happens automatically when the providers package is imported.

Package Structure:
    aws/
    ├── __init__.py           # This file - registers provider
    ├── provider.py           # AWSProvider class
    ├── clients.py            # boto3 client initialization
    ├── naming.py             # Resource naming conventions
    ├── cleanup.py            # AWS SDK cleanup fallback
    └── layers/               # Provider-specific info helpers
        ├── layer_1_iot.py
        ├── layer_4_twinmaker.py
        └── layer_5_grafana.py

Usage:
    # Provider is auto-registered when providers package is imported
    import providers
    
    # Get AWS provider from registry
    from core import ProviderRegistry
    provider = ProviderRegistry.get("aws")
    provider.initialize_clients(credentials, "my-twin")
"""

from src.core.registry import ProviderRegistry
from .provider import AWSProvider
from .cleanup import cleanup_aws_resources

# Auto-register this provider when the module is imported
ProviderRegistry.register("aws", AWSProvider)

__all__ = ["AWSProvider", "cleanup_aws_resources"]
