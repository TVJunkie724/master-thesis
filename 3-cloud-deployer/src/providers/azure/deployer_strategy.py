"""
Azure Deployer Strategy.

Implements DeployerStrategy protocol for Azure deployments.
Orchestrates layer-specific deployment through layer adapters.

Implemented Layers:
    - Setup Layer: Resource Group, Managed Identity, Storage Account
    - L0 (Glue): Multi-cloud receiver components
    
Stub Layers (TODO):
    - L1-L5: Full Azure resource deployment
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
        raise NotImplementedError("Azure L1 deployment not yet implemented")
    
    def destroy_l1(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L1 destruction not yet implemented")
    
    # ==========================================
    # Layer 2: Data Processing (Azure Functions)
    # ==========================================
    
    def deploy_l2(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L2 deployment not yet implemented")
    
    def destroy_l2(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L2 destruction not yet implemented")
    
    # ==========================================
    # Layer 3: Storage (Cosmos DB + Blob)
    # ==========================================
    
    def deploy_l3_hot(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L3 hot deployment not yet implemented")
    
    def destroy_l3_hot(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L3 hot destruction not yet implemented")
    
    def deploy_l3_cold(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L3 cold deployment not yet implemented")
    
    def destroy_l3_cold(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L3 cold destruction not yet implemented")
    
    def deploy_l3_archive(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L3 archive deployment not yet implemented")
    
    def destroy_l3_archive(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L3 archive destruction not yet implemented")
    
    # ==========================================
    # Layer 4: Twin Management (Azure Digital Twins)
    # ==========================================
    
    def deploy_l4(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L4 deployment not yet implemented")
    
    def destroy_l4(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L4 destruction not yet implemented")
    
    # ==========================================
    # Layer 5: Visualization (Azure Managed Grafana)
    # ==========================================
    
    def deploy_l5(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L5 deployment not yet implemented")
    
    def destroy_l5(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L5 destruction not yet implemented")
