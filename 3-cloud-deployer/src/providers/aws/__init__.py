"""
AWS Provider package.

This package implements the CloudProvider protocol for Amazon Web Services.
It wraps the existing AWS deployment code from src/aws/ in the new pattern.

Auto-Registration:
    Importing this package registers AWSProvider with the ProviderRegistry.
    This happens automatically when the providers package is imported.

Package Structure:
    aws/
    ├── __init__.py           # This file - registers provider
    ├── provider.py           # AWSProvider class
    ├── clients.py            # boto3 client initialization
    ├── naming.py             # Resource naming conventions
    ├── deployer_strategy.py  # AWSDeployerStrategy
    └── layers/               # Layer-specific deployment (Phase 2)
        ├── l1_iot.py
        ├── l2_compute.py
        ├── l3_storage.py
        ├── l4_twinmaker.py
        └── l5_grafana.py

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
