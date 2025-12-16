"""
Azure CloudProvider implementation.

This module provides the Azure implementation of the CloudProvider protocol,
including SDK client initialization, resource naming, and status checks.

SDK Clients Initialized:
    - ResourceManagementClient: For Resource Group management
    - ManagedServiceIdentityClient: For User-Assigned Managed Identity
    - StorageManagementClient: For Storage Account management
    - WebSiteManagementClient: For Function App management
    - IotHubClient: For IoT Hub management
    - DigitalTwinsManagementClient: For Azure Digital Twins
    - DashboardManagementClient: For Azure Managed Grafana

Usage:
    from src.providers.azure.provider import AzureProvider
    
    provider = AzureProvider()
    provider.initialize_clients(credentials, twin_name)
    # Access clients: provider.clients["resource"], etc.
    # Check status: provider.info_l1(context), etc.
"""

from typing import Dict, Any, TYPE_CHECKING, Optional
from providers.base import BaseProvider

if TYPE_CHECKING:
    from src.providers.azure.naming import AzureNaming
    from src.core.context import DeploymentContext


class AzureProvider(BaseProvider):
    """
    Azure implementation of the CloudProvider protocol.
    
    Manages Azure SDK clients, resource naming, and status checks.
    
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
        self._location: str = ""
        self._location_iothub: str = ""
        self._location_digital_twin: str = ""
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
        """Get the Azure region for general deployments."""
        return self._location
    
    @property
    def location_iothub(self) -> str:
        """Get the Azure region for IoT Hub (may differ from general location)."""
        return self._location_iothub
    
    @property
    def location_digital_twin(self) -> str:
        """Get the Azure region for Digital Twins (may differ from general location)."""
        return self._location_digital_twin
    
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
                - azure_subscription_id: Azure subscription ID (REQUIRED)
                - azure_region: Azure region for general resources (REQUIRED)
                - azure_region_iothub: Azure region for IoT Hub (REQUIRED)
                - azure_region_digital_twin: Azure region for Digital Twins (REQUIRED)
                - azure_tenant_id: Azure AD tenant ID (optional)
                - azure_client_id: Service principal client ID (optional)
                - azure_client_secret: Service principal secret (optional)
            twin_name: Digital twin name for resource naming
        
        Raises:
            ValueError: If required credentials are missing
        """
        from src.providers.azure.naming import AzureNaming
        
        self._twin_name = twin_name
        
        # Fail-fast: Required credentials MUST be provided
        if "azure_subscription_id" not in credentials or not credentials["azure_subscription_id"]:
            raise ValueError(
                "Missing required credential 'azure_subscription_id'. "
                "Azure subscription ID must be provided in config_credentials.json."
            )
        self._subscription_id = credentials["azure_subscription_id"]
        
        if "azure_region" not in credentials or not credentials["azure_region"]:
            raise ValueError(
                "Missing required credential 'azure_region'. "
                "Azure region (e.g., 'italynorth') must be provided in config_credentials.json."
            )
        self._location = credentials["azure_region"]
        
        if "azure_region_iothub" not in credentials or not credentials["azure_region_iothub"]:
            raise ValueError(
                "Missing required credential 'azure_region_iothub'. "
                "IoT Hub region (e.g., 'westeurope') must be provided in config_credentials.json."
            )
        self._location_iothub = credentials["azure_region_iothub"]
        
        if "azure_region_digital_twin" not in credentials or not credentials["azure_region_digital_twin"]:
            raise ValueError(
                "Missing required credential 'azure_region_digital_twin'. "
                "Digital Twins region (e.g., 'westeurope') must be provided in config_credentials.json."
            )
        self._location_digital_twin = credentials["azure_region_digital_twin"]
        
        # Initialize naming
        self._naming = AzureNaming(twin_name)
        
        # Get credentials and initialize SDK clients
        credential = self._get_credential(credentials)
        self._initialize_sdk_clients(credential)
        
        self._initialized = True
    
    def _get_credential(self, credentials: dict) -> Any:
        """Get Azure credential for SDK clients."""
        from azure.identity import DefaultAzureCredential, ClientSecretCredential
        
        client_id = credentials.get("azure_client_id")
        client_secret = credentials.get("azure_client_secret")
        tenant_id = credentials.get("azure_tenant_id")
        
        if client_id and client_secret and tenant_id:
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        else:
            return DefaultAzureCredential()
    
    def _initialize_sdk_clients(self, credential: Any) -> None:
        """Initialize all required Azure SDK clients."""
        from azure.mgmt.resource import ResourceManagementClient
        from azure.mgmt.storage import StorageManagementClient
        from azure.mgmt.web import WebSiteManagementClient
        from azure.mgmt.msi import ManagedServiceIdentityClient
        from azure.mgmt.iothub import IotHubClient
        from azure.mgmt.eventgrid import EventGridManagementClient
        from azure.mgmt.authorization import AuthorizationManagementClient
        from azure.mgmt.dashboard import DashboardManagementClient
        from azure.mgmt.cosmosdb import CosmosDBManagementClient
        from azure.mgmt.digitaltwins import AzureDigitalTwinsManagementClient
        
        subscription_id = self._subscription_id
        
        self._clients["resource"] = ResourceManagementClient(credential=credential, subscription_id=subscription_id)
        self._clients["storage"] = StorageManagementClient(credential=credential, subscription_id=subscription_id)
        self._clients["web"] = WebSiteManagementClient(credential=credential, subscription_id=subscription_id)
        self._clients["msi"] = ManagedServiceIdentityClient(credential=credential, subscription_id=subscription_id)
        self._clients["iothub"] = IotHubClient(credential=credential, subscription_id=subscription_id)
        self._clients["eventgrid"] = EventGridManagementClient(credential=credential, subscription_id=subscription_id)
        self._clients["authorization"] = AuthorizationManagementClient(credential=credential, subscription_id=subscription_id)
        self._clients["dashboard"] = DashboardManagementClient(credential=credential, subscription_id=subscription_id)
        self._clients["cosmos"] = CosmosDBManagementClient(credential=credential, subscription_id=subscription_id)
        self._clients["digitaltwins"] = AzureDigitalTwinsManagementClient(credential=credential, subscription_id=subscription_id)
    
    # ==========================================
    # Status Checks (Used by API)
    # ==========================================
    
    def info_l1(self, context: 'DeploymentContext') -> dict:
        """Get status of L1 Data Acquisition components."""
        from src.providers.azure.layers.layer_1_iot import info_l1
        return info_l1(context, self)
    
    def info_l4(self, context: 'DeploymentContext') -> dict:
        """Get status of L4 Twin Management components."""
        from src.providers.azure.layers.layer_4_adt import info_l4
        return info_l4(context, self)
    
    def info_l5(self, context: 'DeploymentContext') -> dict:
        """Get status of L5 Visualization components."""
        from src.providers.azure.layers.layer_5_grafana import info_l5
        return info_l5(context, self)
