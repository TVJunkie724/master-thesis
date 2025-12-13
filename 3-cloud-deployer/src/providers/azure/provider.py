"""
Azure CloudProvider implementation.

This module provides the Azure implementation of the CloudProvider protocol,
including SDK client initialization and resource naming.

SDK Clients Initialized:
    - ResourceManagementClient: For Resource Group management
    - ManagedServiceIdentityClient: For User-Assigned Managed Identity
    - StorageManagementClient: For Storage Account management
    - WebSiteManagementClient: For Function App management

Usage:
    from src.providers.azure.provider import AzureProvider
    
    provider = AzureProvider()
    provider.initialize_clients(credentials, twin_name)
    # Now ready to use provider.clients["resource"], etc.
"""

from typing import Dict, Any, TYPE_CHECKING, Optional
from providers.base import BaseProvider

if TYPE_CHECKING:
    from src.core.protocols import DeployerStrategy
    from src.providers.azure.naming import AzureNaming


class AzureProvider(BaseProvider):
    """
    Azure implementation of the CloudProvider protocol.
    
    Manages Azure SDK clients and provides resource naming conventions.
    
    Attributes:
        name: Provider identifier ("azure")
        naming: AzureNaming instance for consistent resource names
        clients: Dictionary of initialized Azure SDK clients
        location: Azure region for deployments
    """
    
    name: str = "azure"
    
    def __init__(self):
        """Initialize Azure provider."""
        super().__init__()
        self._subscription_id: str = ""
        self._resource_group: str = ""
        self._location: str = "westeurope"
        self._naming: Optional['AzureNaming'] = None
        self._clients: Dict[str, Any] = {}
    
    @property
    def subscription_id(self) -> str:
        """Get the Azure subscription ID."""
        return self._subscription_id
    
    @property
    def resource_group(self) -> str:
        """Get the Azure resource group name (from naming)."""
        if self._naming:
            return self._naming.resource_group()
        return self._resource_group
    
    @property
    def location(self) -> str:
        """Get the Azure region for deployments."""
        return self._location
    
    @property
    def naming(self) -> 'AzureNaming':
        """Get the Azure naming instance."""
        if not self._naming:
            raise RuntimeError("Provider not initialized. Call initialize_clients first.")
        return self._naming
    
    @property
    def clients(self) -> Dict[str, Any]:
        """Get the dictionary of Azure SDK clients."""
        return self._clients
    
    def initialize_clients(self, credentials: dict, twin_name: str) -> None:
        """
        Initialize Azure SDK clients.
        
        Args:
            credentials: Azure credentials dictionary with:
                - azure_subscription_id: Azure subscription ID
                - azure_tenant_id: Azure AD tenant ID (optional)
                - azure_client_id: Service principal client ID (optional)
                - azure_client_secret: Service principal secret (optional)
                - azure_region: Azure region (optional, default: westeurope)
            twin_name: Digital twin name for resource naming
        
        Note:
            If azure_client_id/azure_client_secret are not provided, uses DefaultAzureCredential
            which supports managed identity, Azure CLI, environment variables, etc.
        """
        from src.providers.azure.naming import AzureNaming
        
        self._twin_name = twin_name
        self._subscription_id = credentials.get("azure_subscription_id", "")
        self._location = credentials.get("azure_region", "westeurope")
        
        # Initialize naming
        self._naming = AzureNaming(twin_name)
        
        # Get credentials
        credential = self._get_credential(credentials)
        
        # Initialize SDK clients
        self._initialize_sdk_clients(credential)
        
        self._initialized = True
    
    def _get_credential(self, credentials: dict) -> Any:
        """
        Get Azure credential for SDK clients.
        
        Uses ServicePrincipalCredential if client_id/secret provided,
        otherwise uses DefaultAzureCredential for flexible auth.
        """
        from azure.identity import DefaultAzureCredential, ClientSecretCredential
        
        client_id = credentials.get("azure_client_id")
        client_secret = credentials.get("azure_client_secret")
        tenant_id = credentials.get("azure_tenant_id")
        
        if client_id and client_secret and tenant_id:
            # Use service principal credentials
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        else:
            # Use default credential chain (managed identity, CLI, env vars)
            return DefaultAzureCredential()
    
    def _initialize_sdk_clients(self, credential: Any) -> None:
        """
        Initialize all required Azure SDK clients.
        
        Args:
            credential: Azure credential object
        """
        from azure.mgmt.resource import ResourceManagementClient
        from azure.mgmt.storage import StorageManagementClient
        from azure.mgmt.web import WebSiteManagementClient
        from azure.mgmt.msi import ManagedServiceIdentityClient
        
        subscription_id = self._subscription_id
        
        # Resource Management - for Resource Groups
        self._clients["resource"] = ResourceManagementClient(
            credential=credential,
            subscription_id=subscription_id
        )
        
        # Storage Management - for Storage Accounts
        self._clients["storage"] = StorageManagementClient(
            credential=credential,
            subscription_id=subscription_id
        )
        
        # Web Site Management - for Function Apps
        self._clients["web"] = WebSiteManagementClient(
            credential=credential,
            subscription_id=subscription_id
        )
        
        # Managed Service Identity - for User-Assigned Managed Identity
        self._clients["msi"] = ManagedServiceIdentityClient(
            credential=credential,
            subscription_id=subscription_id
        )
    
    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """
        Generate an Azure resource name.
        
        Deprecated: Use provider.naming methods instead.
        """
        if suffix:
            return f"{self.twin_name}-{resource_type}-{suffix}"
        return f"{self.twin_name}-{resource_type}"
    
    def get_deployer_strategy(self) -> 'DeployerStrategy':
        """Return the Azure deployment strategy."""
        from .deployer_strategy import AzureDeployerStrategy
        return AzureDeployerStrategy(self)
