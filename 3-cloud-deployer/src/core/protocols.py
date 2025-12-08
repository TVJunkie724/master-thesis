"""
Protocol definitions for the multi-cloud deployer.

This module defines the abstract interfaces (Protocols) that all cloud providers
must implement. Using Python's Protocol (structural subtyping) allows for
duck-typing while still providing IDE support and type checking.

Design Pattern: Strategy Pattern + Abstract Factory
    - CloudProvider: Abstract Factory that creates provider-specific objects
    - DeployerStrategy: Strategy interface for deployment operations

Why Protocols instead of ABC?
    - No explicit inheritance required (duck typing)
    - Better compatibility with existing code during migration
    - Runtime checking with @runtime_checkable decorator
"""

from typing import Protocol, runtime_checkable, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid circular imports - only import for type hints
    from .context import DeploymentContext


@runtime_checkable
class CloudProvider(Protocol):
    """
    Protocol defining the interface for a cloud provider.
    
    Each cloud (AWS, Azure, GCP) must implement this interface.
    The @runtime_checkable decorator allows isinstance() checks at runtime.
    
    Responsibilities:
        - Initialize and manage SDK clients (boto3, azure-sdk, google-cloud)
        - Generate consistent resource names with twin prefix
        - Provide the DeployerStrategy for deployment operations
    
    Example Implementation:
        class AWSProvider:
            name = "aws"
            
            def initialize_clients(self, credentials):
                self._clients = {
                    "iam": boto3.client("iam", ...),
                    "lambda": boto3.client("lambda", ...),
                }
            
            @property
            def clients(self):
                return self._clients
            
            def get_resource_name(self, resource_type, suffix=""):
                return f"{self._twin_name}-{resource_type}-{suffix}"
            
            def get_deployer_strategy(self):
                return AWSDeployerStrategy(self)
    """
    
    @property
    def name(self) -> str:
        """
        Return the provider identifier.
        
        This is used for logging, error messages, and registry lookup.
        Must be one of: "aws", "azure", "gcp"
        
        Returns:
            str: The provider identifier
        """
        ...
    
    @property
    def clients(self) -> Dict[str, Any]:
        """
        Return initialized SDK clients.
        
        These clients are created by initialize_clients() and used by
        the layer deployment functions to interact with cloud APIs.
        
        Returns:
            Dict mapping service names to client instances.
            
        Example (AWS):
            {
                "iam": boto3.client("iam"),
                "lambda": boto3.client("lambda"),
                "dynamodb": boto3.client("dynamodb"),
                "iot": boto3.client("iot"),
                "twinmaker": boto3.client("iottwinmaker"),
                "grafana": boto3.client("grafana"),
            }
        """
        ...
    
    def initialize_clients(self, credentials: dict, twin_name: str) -> None:
        """
        Initialize SDK clients for this provider.
        
        This must be called before any deployment operations. It creates
        authenticated clients for all cloud services needed by this provider.
        
        Args:
            credentials: Provider-specific credential dictionary.
                AWS: {
                    "aws_access_key_id": str,
                    "aws_secret_access_key": str,
                    "aws_region": str
                }
                Azure: {
                    "subscription_id": str,
                    "tenant_id": str,
                    "client_id": str,
                    "client_secret": str,
                    "region": str
                }
                GCP: {
                    "project_id": str,
                    "credentials_file": str,
                    "region": str
                }
            twin_name: The digital twin name prefix for resource naming.
        
        Raises:
            ConfigurationError: If credentials are invalid or incomplete.
        """
        ...
    
    def get_resource_name(self, resource_type: str, suffix: str = "") -> str:
        """
        Generate a namespaced resource name.
        
        All cloud resources are prefixed with the digital twin name to
        create isolated namespaces and enable easy identification/cleanup.
        
        Args:
            resource_type: Type of resource (e.g., "dispatcher", "hot-table")
            suffix: Optional suffix (e.g., device ID for per-device resources)
        
        Returns:
            Formatted name like "{twin_name}-{resource_type}[-{suffix}]"
            
        Example:
            >>> provider.get_resource_name("dispatcher")
            "my-twin-dispatcher"
            >>> provider.get_resource_name("processor", "sensor-001")
            "my-twin-processor-sensor-001"
        """
        ...
    
    def get_deployer_strategy(self) -> 'DeployerStrategy':
        """
        Return the deployment strategy for this provider.
        
        The strategy encapsulates all layer-specific deployment logic
        for this cloud provider.
        
        Returns:
            An object implementing the DeployerStrategy protocol.
        """
        ...


@runtime_checkable
class DeployerStrategy(Protocol):
    """
    Protocol defining the deployment strategy interface.
    
    Each provider implements this to handle layer-by-layer deployment.
    This is the Strategy pattern - the algorithm (deployment) varies
    by provider while the interface remains consistent.
    
    Layer Responsibilities:
        L1 (Data Acquisition): IoT connectivity, message routing, dispatcher
        L2 (Processing): Processor functions, persister, event checker
        L3 (Storage): Hot/Cold/Archive storage, data movers, reader APIs
        L4 (Twin Management): TwinMaker/Digital Twins, entity hierarchy
        L5 (Visualization): Grafana workspace, dashboards
    
    Note on L3:
        Layer 3 is split into hot/cold/archive because these can be
        on different providers in a multi-cloud deployment.
    
    Example Implementation:
        class AWSDeployerStrategy:
            def __init__(self, provider: AWSProvider):
                self._provider = provider
            
            def deploy_l1(self, context: DeploymentContext) -> None:
                # Create IAM role
                # Create Lambda function
                # Create IoT rule
                ...
    """
    
    # ==========================================
    # Layer 1: Data Acquisition
    # ==========================================
    
    def deploy_l1(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 1 (Data Acquisition) components.
        
        Creates:
            - IoT service configuration (IoT Core / IoT Hub / Pub/Sub)
            - Dispatcher function (routes messages to processors)
            - IAM roles and policies
            - Message routing rules
        
        Args:
            context: The deployment context with config and credentials.
        """
        ...
    
    def destroy_l1(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 1 resources in reverse order of creation."""
        ...
    
    # ==========================================
    # Layer 2: Data Processing
    # ==========================================
    
    def deploy_l2(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 2 (Processing) components.
        
        Creates:
            - Processor functions (one per IoT device type)
            - Persister function (writes to hot storage)
            - Event checker function (optional, for anomaly detection)
            - State machine / workflow (optional, for event actions)
            - Event feedback function (optional, for device commands)
        
        Args:
            context: The deployment context with config and credentials.
        """
        ...
    
    def destroy_l2(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 2 resources in reverse order of creation."""
        ...
    
    # ==========================================
    # Layer 3: Storage (Split by tier)
    # ==========================================
    
    def deploy_l3_hot(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 3 Hot Storage components.
        
        Creates:
            - Hot storage database (DynamoDB / Cosmos DB / Firestore)
            - Hot reader function (for TwinMaker queries)
            - Optional: API Gateway for cross-cloud access
        
        Args:
            context: The deployment context with config and credentials.
        """
        ...
    
    def destroy_l3_hot(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 3 Hot Storage resources."""
        ...
    
    def deploy_l3_cold(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 3 Cold Storage components.
        
        Creates:
            - Cold storage bucket (S3 IA / Blob Cool / GCS Nearline)
            - Hot-to-Cold mover function (scheduled)
            - EventBridge / Scheduler rule
        
        Args:
            context: The deployment context with config and credentials.
        """
        ...
    
    def destroy_l3_cold(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 3 Cold Storage resources."""
        ...
    
    def deploy_l3_archive(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 3 Archive Storage components.
        
        Creates:
            - Archive storage bucket (Glacier / Blob Archive / GCS Archive)
            - Cold-to-Archive mover function (scheduled)
            - EventBridge / Scheduler rule
        
        Args:
            context: The deployment context with config and credentials.
        """
        ...
    
    def destroy_l3_archive(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 3 Archive Storage resources."""
        ...
    
    # ==========================================
    # Layer 4: Twin Management
    # ==========================================
    
    def deploy_l4(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 4 (Twin Management) components.
        
        Creates:
            - TwinMaker workspace / Digital Twins instance
            - Component types (one per IoT device type)
            - Entity hierarchy (based on config_hierarchy.json)
            - S3/Blob bucket for 3D assets
        
        Args:
            context: The deployment context with config and credentials.
        """
        ...
    
    def destroy_l4(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 4 resources in reverse order of creation."""
        ...
    
    # ==========================================
    # Layer 5: Visualization
    # ==========================================
    
    def deploy_l5(self, context: 'DeploymentContext') -> None:
        """
        Deploy Layer 5 (Visualization) components.
        
        Creates:
            - Grafana workspace (managed or self-hosted)
            - IAM role for Grafana data source access
            - Data source configurations
        
        Args:
            context: The deployment context with config and credentials.
        """
        ...
    
    def destroy_l5(self, context: 'DeploymentContext') -> None:
        """Destroy Layer 5 resources in reverse order of creation."""
        ...
    
    # ==========================================
    # Convenience Methods
    # ==========================================
    
    def deploy_all(self, context: 'DeploymentContext') -> None:
        """
        Deploy all layers in order (L1 → L5).
        
        This is a convenience method that calls all deploy_lX methods
        in the correct order, handling dependencies between layers.
        """
        ...
    
    def destroy_all(self, context: 'DeploymentContext') -> None:
        """
        Destroy all layers in reverse order (L5 → L1).
        
        Resources must be destroyed in reverse order to respect
        dependencies (e.g., can't delete IAM role while Lambda uses it).
        """
        ...
