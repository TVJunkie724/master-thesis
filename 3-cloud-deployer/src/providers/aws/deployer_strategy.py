"""
AWS Deployer Strategy implementation.

This module implements the DeployerStrategy protocol for AWS, providing
the layer-by-layer deployment logic for AWS resources.

Design Pattern: Strategy Pattern
    AWSDeployerStrategy encapsulates AWS-specific deployment algorithms.
    The core deployer calls strategy.deploy_l1(context) without knowing
    the specific AWS implementation details.

Integration with Existing Code:
    This strategy wraps the existing code in src/aws/deployer_layers/,
    calling those functions internally while providing a unified interface.
    
Phase 2 Work:
    Currently, this is a stub that will be completed in Phase 2 when
    we integrate the existing AWS deployment code.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.context import DeploymentContext
    from .provider import AWSProvider


class AWSDeployerStrategy:
    """
    AWS implementation of the DeployerStrategy protocol.
    
    This class contains the deployment logic for AWS resources,
    organized by Digital Twin layer (L1-L5).
    
    Architecture:
        Each deploy_lX method handles a complete layer:
        - Creates required IAM roles/policies
        - Creates compute resources (Lambda, Step Functions)
        - Creates storage resources (DynamoDB, S3)
        - Creates triggers and integrations
    
    Example Usage:
        provider = AWSProvider()
        provider.initialize_clients(credentials, "my-twin")
        
        strategy = provider.get_deployer_strategy()
        strategy.deploy_l1(context)  # Deploy IoT layer
        strategy.deploy_l2(context)  # Deploy Processing layer
        # ... etc
    
    Note:
        In Phase 2, these methods will be implemented by wrapping
        the existing code in src/aws/deployer_layers/.
    """
    
    def __init__(self, provider: 'AWSProvider'):
        """
        Initialize the strategy with a reference to the provider.
        
        Args:
            provider: The initialized AWSProvider instance.
                     Must have clients ready before deployment calls.
        """
        self._provider = provider
    
    @property
    def provider(self) -> 'AWSProvider':
        """Get the provider associated with this strategy."""
        return self._provider
    
    # ==========================================
    # Setup Layer: Resource Grouping
    # ==========================================
    
    def deploy_setup(self, context: 'DeploymentContext') -> None:
        """
        Deploy Setup Layer (Resource Grouping) for AWS.
        
        Creates:
            1. AWS Resource Group (tag-based query for all twin resources)
        
        Note:
            This should be called BEFORE any other layer deployment.
            All subsequent layers will tag their resources for inclusion.
        """
        from .layers.l_setup_adapter import deploy_setup as _deploy_setup
        _deploy_setup(context, self._provider)
    
    def destroy_setup(self, context: 'DeploymentContext') -> None:
        """
        Destroy Setup Layer resources.
        
        Note:
            This should be called AFTER all other layers are destroyed.
            Deleting the Resource Group does NOT delete the resources.
        """
        from .layers.l_setup_adapter import destroy_setup as _destroy_setup
        _destroy_setup(context, self._provider)
    
    def info_setup(self, context: 'DeploymentContext') -> dict:
        """Check status of Setup Layer (Resource Grouping)."""
        from .layers.l_setup_adapter import info_setup as _info_setup
        return _info_setup(context, self._provider)
    
    # ==========================================
    # Layer 0: Glue (Cross-Cloud HTTP Receivers)
    # ==========================================
    
    def deploy_l0(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 0 (Glue) - cross-cloud HTTP receivers.
        
        Creates (conditionally):
            1. Ingestion Lambda + Function URL (if L1 ≠ L2)
            2. Hot Writer Lambda + Function URL (if L2 ≠ L3)
            3. Cold/Archive Writers (if storage tiers span clouds)
            4. Hot Reader Function URLs (if L3 ≠ L4)
        """
        from .layers.l0_adapter import deploy_l0 as _deploy_l0
        _deploy_l0(context, self._provider)
    
    def destroy_l0(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 0 resources."""
        from .layers.l0_adapter import destroy_l0 as _destroy_l0
        _destroy_l0(context, self._provider)
    
    # ==========================================
    # Layer 1: Data Acquisition (IoT)
    # ==========================================
    
    def deploy_l1(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 1 (Data Acquisition) components for AWS.
        
        Creates:
            1. Dispatcher IAM Role (allows Lambda to write logs, invoke other Lambdas)
            2. Dispatcher Lambda Function (routes IoT messages to processors)
            3. IoT Topic Rule (triggers dispatcher on telemetry messages)
        
        Args:
            context: Deployment context with config and credentials
        """
        from .layers.l1_adapter import deploy_l1 as _deploy_l1
        _deploy_l1(context, self._provider)
    
    def destroy_l1(self, context: 'DeploymentContext') -> None:
        """
        Destroy Layer 1 resources in reverse order.
        
        Args:
            context: Deployment context with config and credentials
        """
        from .layers.l1_adapter import destroy_l1 as _destroy_l1
        _destroy_l1(context, self._provider)
    
    # ==========================================
    # Layer 2: Data Processing
    # ==========================================
    
    def deploy_l2(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 2 (Processing) components for AWS.
        
        Creates:
            1. Persister Lambda + IAM Role (writes to DynamoDB)
            2. Event Checker Lambda (optional, anomaly detection)
            3. Step Function State Machine (optional, event workflow)
            4. Event Feedback Lambda (optional, device commands)
        """
        from .layers.l2_adapter import deploy_l2 as _deploy_l2
        _deploy_l2(context, self._provider)
    
    def destroy_l2(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 2 resources in reverse order."""
        from .layers.l2_adapter import destroy_l2 as _destroy_l2
        _destroy_l2(context, self._provider)
    
    # ==========================================
    # Layer 3: Storage (Split by tier)
    # ==========================================
    
    def deploy_l3_hot(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 3 Hot Storage components for AWS.
        
        Creates:
            1. DynamoDB Table (hot storage for recent data)
            2. Hot Reader Lambda (queries for TwinMaker)
            3. Hot Reader IAM Role
            4. API Gateway (optional, for cross-cloud access)
        """
        from .layers.l3_adapter import deploy_l3_hot as _deploy_l3_hot
        _deploy_l3_hot(context, self._provider)
    
    def destroy_l3_hot(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 3 Hot Storage resources."""
        from .layers.l3_adapter import destroy_l3_hot as _destroy_l3_hot
        _destroy_l3_hot(context, self._provider)
    
    def deploy_l3_cold(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 3 Cold Storage components for AWS.
        
        Creates:
            1. S3 Bucket (Infrequent Access tier)
            2. Hot-to-Cold Mover Lambda + IAM Role
            3. EventBridge Rule (scheduled trigger)
        """
        from .layers.l3_adapter import deploy_l3_cold as _deploy_l3_cold
        _deploy_l3_cold(context, self._provider)
    
    def destroy_l3_cold(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 3 Cold Storage resources."""
        from .layers.l3_adapter import destroy_l3_cold as _destroy_l3_cold
        _destroy_l3_cold(context, self._provider)
    
    def deploy_l3_archive(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 3 Archive Storage components for AWS.
        
        Creates:
            1. S3 Bucket (Glacier tier)
            2. Cold-to-Archive Mover Lambda + IAM Role
            3. EventBridge Rule (scheduled trigger)
        """
        from .layers.l3_adapter import deploy_l3_archive as _deploy_l3_archive
        _deploy_l3_archive(context, self._provider)
    
    def destroy_l3_archive(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 3 Archive Storage resources."""
        from .layers.l3_adapter import destroy_l3_archive as _destroy_l3_archive
        _destroy_l3_archive(context, self._provider)
    
    # ==========================================
    # Layer 4: Twin Management
    # ==========================================
    
    def deploy_l4(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 4 (Twin Management) components for AWS.
        
        Creates:
            1. TwinMaker Workspace
            2. Component Types (one per device type)
            3. Entity Hierarchy
            4. S3 Bucket for 3D assets
        """
        from .layers.l4_adapter import deploy_l4 as _deploy_l4
        _deploy_l4(context, self._provider)
    
    def destroy_l4(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 4 resources in reverse order."""
        from .layers.l4_adapter import destroy_l4 as _destroy_l4
        _destroy_l4(context, self._provider)
    
    # ==========================================
    # Layer 5: Visualization
    # ==========================================
    
    def deploy_l5(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 5 (Visualization) components for AWS.
        
        Creates:
            1. Grafana Workspace (Amazon Managed Grafana)
            2. IAM Role for Grafana data source access
        """
        from .layers.l5_adapter import deploy_l5 as _deploy_l5
        _deploy_l5(context, self._provider)
    
    def destroy_l5(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 5 resources in reverse order."""
        from .layers.l5_adapter import destroy_l5 as _destroy_l5
        _destroy_l5(context, self._provider)
    
    # ==========================================
    # Convenience Methods
    # ==========================================
    
    def deploy_all(self, context: 'DeploymentContext') -> None:
        """Deploy all layers in order (Setup → L0 → L5)."""
        self.deploy_setup(context)
        self.deploy_l0(context)
        self.deploy_l1(context)
        self.deploy_l2(context)
        self.deploy_l3_hot(context)
        self.deploy_l3_cold(context)
        self.deploy_l3_archive(context)
        self.deploy_l4(context)
        self.deploy_l5(context)
    
    def destroy_all(self, context: 'DeploymentContext') -> None:
        """Destroy all layers in reverse order (L5 → L0 → Setup)."""
        self.destroy_l5(context)
        self.destroy_l4(context)
        self.destroy_l3_archive(context)
        self.destroy_l3_cold(context)
        self.destroy_l3_hot(context)
        self.destroy_l2(context)
        self.destroy_l1(context)
        self.destroy_l0(context)
        self.destroy_setup(context)

    # ==========================================
    # Info / Status Checks
    # ==========================================

    def info_l0(self, context: 'DeploymentContext') -> None:
        """Check status of Layer 0 (Glue)."""
        from .layers.l0_adapter import info_l0 as _info_l0
        _info_l0(context, self._provider)

    def info_l1(self, context: 'DeploymentContext') -> None:
        """Check status of Layer 1 (IoT)."""
        from .layers.l1_adapter import info_l1 as _info_l1
        _info_l1(context, self._provider)

    def info_l2(self, context: 'DeploymentContext') -> None:
        """Check status of Layer 2 (Compute)."""
        from .layers.l2_adapter import info_l2 as _info_l2
        _info_l2(context, self._provider)

    def info_l3_hot(self, context: 'DeploymentContext') -> None:
        """Check status of Layer 3 Hot Storage."""
        from .layers.l3_adapter import info_l3_hot as _info_l3_hot
        _info_l3_hot(context, self._provider)

    def info_l3_cold(self, context: 'DeploymentContext') -> None:
        """Check status of Layer 3 Cold Storage."""
        from .layers.l3_adapter import info_l3_cold as _info_l3_cold
        _info_l3_cold(context, self._provider)

    def info_l3_archive(self, context: 'DeploymentContext') -> None:
        """Check status of Layer 3 Archive Storage."""
        from .layers.l3_adapter import info_l3_archive as _info_l3_archive
        _info_l3_archive(context, self._provider)
        
    def info_l4(self, context: 'DeploymentContext') -> None:
        """Check status of Layer 4 (TwinMaker)."""
        from .layers.l4_adapter import info_l4 as _info_l4
        _info_l4(context, self._provider)

    def info_l5(self, context: 'DeploymentContext') -> None:
        """Check status of Layer 5 (Grafana)."""
        from .layers.l5_adapter import info_l5 as _info_l5
        _info_l5(context, self._provider)

    def info_all(self, context: 'DeploymentContext') -> None:
        """Check status of all layers."""
        self.info_l0(context)
        self.info_l1(context)
        self.info_l2(context)
        self.info_l3_hot(context)
        self.info_l3_cold(context)
        self.info_l3_archive(context)
        self.info_l4(context)
        self.info_l5(context)
