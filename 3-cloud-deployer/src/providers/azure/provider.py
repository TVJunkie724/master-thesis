"""
Azure CloudProvider implementation (Stub).

This is a minimal stub to validate the multi-cloud pattern.
Full implementation will be added in a future phase.
"""

from typing import Dict, Any, TYPE_CHECKING
from providers.base import BaseProvider

if TYPE_CHECKING:
    from src.core.protocols import DeployerStrategy


class AzureProvider(BaseProvider):
    """
    Azure implementation of the CloudProvider protocol.
    
    Status: STUB - Methods raise NotImplementedError.
    """
    
    name: str = "azure"
    
    def __init__(self):
        """Initialize Azure provider."""
        super().__init__()
        self._subscription_id: str = ""
        self._resource_group: str = ""
    
    @property
    def subscription_id(self) -> str:
        """Get the Azure subscription ID."""
        return self._subscription_id
    
    @property
    def resource_group(self) -> str:
        """Get the Azure resource group name."""
        return self._resource_group
    
    def initialize_clients(self, credentials: dict, twin_name: str) -> None:
        """
        Initialize Azure SDK clients.
        
        Args:
            credentials: Azure credentials (subscription_id, tenant_id, etc.)
            twin_name: Digital twin name for resource naming
        """
        self._twin_name = twin_name
        self._subscription_id = credentials.get("subscription_id", "")
        self._resource_group = credentials.get("resource_group", "")
        
        # TODO: Initialize azure-mgmt clients
        self._clients = {}
        self._initialized = True
    
    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """Generate an Azure resource name."""
        if suffix:
            return f"{self.twin_name}-{resource_type}-{suffix}"
        return f"{self.twin_name}-{resource_type}"
    
    def get_deployer_strategy(self) -> 'DeployerStrategy':
        """Return the Azure deployment strategy."""
        from .deployer_strategy import AzureDeployerStrategy
        return AzureDeployerStrategy(self)
