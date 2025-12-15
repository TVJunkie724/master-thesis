"""
AWS Layers package.

This package provides adapters that bridge the new pattern-based approach
with the existing layer deployment code in src/aws/deployer_layers/.

Migration Strategy:
    Rather than rewriting all layer code immediately, we create thin adapters
    that allow the new DeployerStrategy to call the existing functions.
    This enables gradual migration while maintaining full functionality.

Package Structure:
    layers/
    ├── __init__.py         # This file - exports all layer functions
    ├── l_setup_adapter.py  # Adapter for Setup Layer (Resource Grouping)
    ├── l0_adapter.py       # Adapter for Layer 0 (Glue/Multi-Cloud)
    ├── l1_adapter.py       # Adapter for Layer 1 (IoT)
    ├── l2_adapter.py       # Adapter for Layer 2 (Compute)
    ├── l3_adapter.py       # Adapter for Layer 3 (Storage)
    ├── l4_adapter.py       # Adapter for Layer 4 (TwinMaker)
    └── l5_adapter.py       # Adapter for Layer 5 (Grafana)

Usage:
    from providers.aws.layers import deploy_setup, destroy_setup
    from providers.aws.layers import deploy_l1, destroy_l1
    
    deploy_setup(context, provider)  # Setup before any layers
    deploy_l1(context, provider)     # Then deploy layers
"""

# Setup Layer (Resource Grouping)
from .l_setup_adapter import deploy_setup, destroy_setup, info_setup

# Layer adapters will be imported as they are created
# from .l1_adapter import deploy_l1, destroy_l1
# from .l2_adapter import deploy_l2, destroy_l2
# etc.
