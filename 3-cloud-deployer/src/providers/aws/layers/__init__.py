"""
AWS Layers package.

This package provides adapters that bridge the pattern-based approach
with the existing layer code. Now only exports info functions since
deployment is handled by Terraform.

Note:
    deploy_* and destroy_* functions have been removed.
    Deployment is now handled by Terraform (TerraformDeployerStrategy).
    Only L1, L4, L5 info functions are used by API.
"""

# Layer 1 info (used by API)
from .l1_adapter import info_l1

# Layer 4 info (used by API)
from .l4_adapter import info_l4

# Layer 5 info (used by API)
from .l5_adapter import info_l5
