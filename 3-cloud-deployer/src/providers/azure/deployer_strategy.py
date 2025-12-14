"""
Azure Deployer Strategy.

Implements DeployerStrategy protocol for Azure deployments.
Orchestrates layer-specific deployment through layer adapters.

Implemented Layers:
    - Setup Layer: Resource Group, Managed Identity, Storage Account
    - L0 (Glue): Multi-cloud receiver components
    - L1 (IoT): IoT Hub, Dispatcher, Event Grid, IoT Devices
    
Stub Layers (TODO):
    - L2-L5: Full Azure resource deployment
"""

from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from .provider import AzureProvider

logger = logging.getLogger(__name__)


class AzureDeployerStrategy:
    """
    Azure implementation of DeployerStrategy.
    
    Orchestrates Azure resource deployment through layer-specific
    adapter modules.
    """
    
    def __init__(self, provider: 'AzureProvider'):
        self._provider = provider
    
    @property
    def provider(self) -> 'AzureProvider':
        return self._provider
    
    # ==========================================
    # Setup Layer (Azure-specific)
    # ==========================================
    
    def deploy_setup(self, context: 'DeploymentContext') -> None:
        """
        Deploy foundational Azure resources.
        
        Must be called before any other deployment.
        Creates: Resource Group, Managed Identity, Storage Account.
        """
        from src.providers.azure.layers.l_setup_adapter import deploy_setup
        deploy_setup(context, self._provider)
    
    def destroy_setup(self, context: 'DeploymentContext') -> None:
        """Destroy all foundational Azure resources."""
        from src.providers.azure.layers.l_setup_adapter import destroy_setup
        destroy_setup(context, self._provider)
    
    def info_setup(self, context: 'DeploymentContext') -> dict:
        """Get status of foundational Azure resources."""
        from src.providers.azure.layers.l_setup_adapter import info_setup
        return info_setup(context, self._provider)
    
    # ==========================================
    # Layer 0: Glue (Multi-Cloud Receivers)
    # ==========================================
    
    def deploy_l0(self, context: 'DeploymentContext') -> None:
        """
        Deploy L0 multi-cloud receiver components.
        
        Only deploys where cloud boundaries exist.
        """
        from src.providers.azure.layers.l0_adapter import deploy_l0
        deploy_l0(context, self._provider)
    
    def destroy_l0(self, context: 'DeploymentContext') -> None:
        """Destroy L0 multi-cloud receiver components."""
        from src.providers.azure.layers.l0_adapter import destroy_l0
        destroy_l0(context, self._provider)
    
    def info_l0(self, context: 'DeploymentContext') -> dict:
        """Get status of L0 multi-cloud receiver components."""
        from src.providers.azure.layers.l0_adapter import info_l0
        return info_l0(context, self._provider)
    
    # ==========================================
    # Layer 1: Data Acquisition (IoT Hub)
    # ==========================================
    
    def deploy_l1(self, context: 'DeploymentContext') -> None:
        """
        Deploy L1 Data Acquisition components.
        
        Creates: IoT Hub, L1 Function App, Dispatcher, Event Grid,
        IoT Devices, and Connector (if multi-cloud).
        """
        from src.providers.azure.layers.l1_adapter import deploy_l1
        deploy_l1(context, self._provider)
    
    def destroy_l1(self, context: 'DeploymentContext') -> None:
        """Destroy all L1 Data Acquisition components."""
        from src.providers.azure.layers.l1_adapter import destroy_l1
        destroy_l1(context, self._provider)
    
    def info_l1(self, context: 'DeploymentContext') -> dict:
        """Get status of L1 Data Acquisition components."""
        from src.providers.azure.layers.l1_adapter import info_l1
        return info_l1(context, self._provider)
    
    # ==========================================
    # Layer 2: Data Processing (Azure Functions)
    # ==========================================
    
    def deploy_l2(self, context: 'DeploymentContext') -> None:
        """
        Deploy L2 Data Processing components.
        
        Creates: L2 App Service Plan, L2 Function App, Persister,
        Processors, Event Checker (optional), Logic App (optional).
        """
        from src.providers.azure.layers.l2_adapter import deploy_l2
        deploy_l2(context, self._provider)
    
    def destroy_l2(self, context: 'DeploymentContext') -> None:
        """Destroy all L2 Data Processing components."""
        from src.providers.azure.layers.l2_adapter import destroy_l2
        destroy_l2(context, self._provider)
    
    def info_l2(self, context: 'DeploymentContext') -> dict:
        """Get status of L2 Data Processing components."""
        from src.providers.azure.layers.l2_adapter import info_l2
        return info_l2(context, self._provider)
    
    # ==========================================
    # Layer 3: Storage (Cosmos DB + Blob)
    # ==========================================
    
    def deploy_l3_hot(self, context: 'DeploymentContext') -> None:
        """Deploy L3 Hot Storage (Cosmos DB) components."""
        from src.providers.azure.layers.l3_adapter import deploy_l3_hot
        deploy_l3_hot(context, self._provider)
    
    def destroy_l3_hot(self, context: 'DeploymentContext') -> None:
        """Destroy L3 Hot Storage components."""
        from src.providers.azure.layers.l3_adapter import destroy_l3_hot
        destroy_l3_hot(context, self._provider)
    
    def deploy_l3_cold(self, context: 'DeploymentContext') -> None:
        """Deploy L3 Cold Storage (Blob Cool tier) components."""
        from src.providers.azure.layers.l3_adapter import deploy_l3_cold
        deploy_l3_cold(context, self._provider)
    
    def destroy_l3_cold(self, context: 'DeploymentContext') -> None:
        """Destroy L3 Cold Storage components."""
        from src.providers.azure.layers.l3_adapter import destroy_l3_cold
        destroy_l3_cold(context, self._provider)
    
    def deploy_l3_archive(self, context: 'DeploymentContext') -> None:
        """Deploy L3 Archive Storage (Blob Archive tier) components."""
        from src.providers.azure.layers.l3_adapter import deploy_l3_archive
        deploy_l3_archive(context, self._provider)
    
    def destroy_l3_archive(self, context: 'DeploymentContext') -> None:
        """Destroy L3 Archive Storage components."""
        from src.providers.azure.layers.l3_adapter import destroy_l3_archive
        destroy_l3_archive(context, self._provider)
    
    def info_l3(self, context: 'DeploymentContext') -> dict:
        """Get status of L3 Storage components."""
        from src.providers.azure.layers.l3_adapter import info_l3
        return info_l3(context, self._provider)
    
    # ==========================================
    # Layer 4: Twin Management (Azure Digital Twins)
    # ==========================================
    
    def deploy_l4(self, context: 'DeploymentContext') -> None:
        """
        Deploy L4 Twin Management components.
        
        Creates: ADT Instance, DTDL Models, Twins, Relationships,
        L4 Function App with ADT Updater, Event Grid subscription.
        """
        from src.providers.azure.layers.l4_adapter import deploy_l4
        deploy_l4(context, self._provider)
    
    def destroy_l4(self, context: 'DeploymentContext') -> None:
        """Destroy all L4 Twin Management components."""
        from src.providers.azure.layers.l4_adapter import destroy_l4
        destroy_l4(context, self._provider)
    
    def info_l4(self, context: 'DeploymentContext') -> dict:
        """Get status of L4 Twin Management components."""
        from src.providers.azure.layers.l4_adapter import info_l4
        return info_l4(context, self._provider)
    
    # ==========================================
    # Layer 5: Visualization (Azure Managed Grafana)
    # ==========================================
    
    def deploy_l5(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L5 deployment not yet implemented")
    
    def destroy_l5(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L5 destruction not yet implemented")
