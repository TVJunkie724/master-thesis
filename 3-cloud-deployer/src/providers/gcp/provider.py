"""
GCP CloudProvider implementation (Stub).

This is a minimal stub to validate the multi-cloud pattern.
Full implementation will be added in a future phase.
"""

from typing import Dict, Any, TYPE_CHECKING
from providers.base import BaseProvider

if TYPE_CHECKING:
    from src.core.protocols import DeployerStrategy


class GCPProvider(BaseProvider):
    """
    GCP implementation of the CloudProvider protocol.
    
    Status: STUB - Methods raise NotImplementedError.
    """
    
    name: str = "gcp"
    
    def __init__(self):
        """Initialize GCP provider."""
        super().__init__()
        self._project_id: str = ""
        self._region: str = ""
    
    @property
    def project_id(self) -> str:
        """Get the GCP project ID."""
        return self._project_id
    
    @property
    def region(self) -> str:
        """Get the GCP region."""
        return self._region
    
    def initialize_clients(self, credentials: dict, twin_name: str) -> None:
        """
        Initialize GCP SDK clients.
        
        Args:
            credentials: GCP credentials (project_id, credentials_path, etc.)
            twin_name: Digital twin name for resource naming
        """
        self._twin_name = twin_name
        self._project_id = credentials.get("project_id", "")
        self._region = credentials.get("region", "us-central1")
        
        # TODO: Initialize google-cloud clients
        self._clients = {}
        self._initialized = True
    
    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """Generate a GCP resource name."""
        if suffix:
            return f"{self.twin_name}-{resource_type}-{suffix}"
        return f"{self.twin_name}-{resource_type}"
    
    def get_deployer_strategy(self) -> 'DeployerStrategy':
        """Return the GCP deployment strategy."""
        from .deployer_strategy import GCPDeployerStrategy
        return GCPDeployerStrategy(self)
