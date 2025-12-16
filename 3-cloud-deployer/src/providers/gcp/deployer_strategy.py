"""
GCP Deployer Strategy (Stub).

Minimal stub implementing DeployerStrategy protocol for Google Cloud.
GCP deployment will be Terraform-only when implemented.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from .provider import GCPProvider


class GCPDeployerStrategy:
    """
    GCP implementation of DeployerStrategy (Stub).
    
    Note:
        GCP deployment will be Terraform-only when implemented.
        This strategy provides stub info_* methods for status checks.
    """
    
    def __init__(self, provider: 'GCPProvider'):
        self._provider = provider
    
    @property
    def provider(self) -> 'GCPProvider':
        return self._provider
    
    # ==========================================
    # Info / Status Checks (Stubs)
    # ==========================================
    
    def info_l1(self, context: 'DeploymentContext') -> dict:
        """Check status of L1 (GCP - not yet implemented)."""
        return {"status": "not_implemented", "layer": "L1", "provider": "gcp"}
    
    def info_l2(self, context: 'DeploymentContext') -> dict:
        """Check status of L2 (GCP - not yet implemented)."""
        return {"status": "not_implemented", "layer": "L2", "provider": "gcp"}
    
    def info_l3(self, context: 'DeploymentContext') -> dict:
        """Check status of L3 (GCP - not yet implemented)."""
        return {"status": "not_implemented", "layer": "L3", "provider": "gcp"}
    
    def info_l4(self, context: 'DeploymentContext') -> dict:
        """Check status of L4 (GCP - not yet implemented)."""
        return {"status": "not_implemented", "layer": "L4", "provider": "gcp"}
    
    def info_l5(self, context: 'DeploymentContext') -> dict:
        """Check status of L5 (GCP - not yet implemented)."""
        return {"status": "not_implemented", "layer": "L5", "provider": "gcp"}
    
    def info_all(self, context: 'DeploymentContext') -> None:
        """Check status of all layers (GCP - not yet implemented)."""
        pass
