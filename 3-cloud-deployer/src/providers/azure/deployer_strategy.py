"""
Azure Deployer Strategy (Stub).

Minimal stub implementing DeployerStrategy protocol for Azure.
All methods raise NotImplementedError until full implementation.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from .provider import AzureProvider


class AzureDeployerStrategy:
    """Azure implementation of DeployerStrategy (Stub)."""
    
    def __init__(self, provider: 'AzureProvider'):
        self._provider = provider
    
    @property
    def provider(self) -> 'AzureProvider':
        return self._provider
    
    def deploy_l1(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L1 deployment not yet implemented")
    
    def destroy_l1(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L1 destruction not yet implemented")
    
    def deploy_l2(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L2 deployment not yet implemented")
    
    def destroy_l2(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L2 destruction not yet implemented")
    
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
    
    def deploy_l4(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L4 deployment not yet implemented")
    
    def destroy_l4(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L4 destruction not yet implemented")
    
    def deploy_l5(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L5 deployment not yet implemented")
    
    def destroy_l5(self, context: 'DeploymentContext') -> None:
        raise NotImplementedError("Azure L5 destruction not yet implemented")
