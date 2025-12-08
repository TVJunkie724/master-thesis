"""
Deployment context and configuration classes.

This module replaces the global state in globals.py with explicit
dependency injection. Instead of importing global variables, functions
receive a DeploymentContext containing all needed configuration.

Design Pattern: Dependency Injection
    - All configuration is loaded into ProjectConfig at startup
    - DeploymentContext wraps config + initialized providers
    - Context is passed explicitly to all deployment functions

Benefits:
    - Testability: Easy to mock/stub configuration
    - Clarity: Dependencies are explicit, not hidden
    - Concurrency: Multiple deployments can run with different configs
    - Debugging: State is traceable, not scattered across globals
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from .protocols import CloudProvider


@dataclass
class ProjectConfig:
    """
    Parsed project configuration from JSON files.
    
    This dataclass holds all configuration loaded from the project's
    config files (config.json, config_iot_devices.json, etc.).
    
    Attributes:
        digital_twin_name: Prefix for all cloud resources
        hot_storage_size_in_days: Days to keep data in hot storage
        cold_storage_size_in_days: Days to keep data in cold storage
        mode: Deployment mode (e.g., "DEBUG", "PRODUCTION")
        iot_devices: List of IoT device configurations
        events: List of event definitions for anomaly detection
        hierarchy: Entity hierarchy for TwinMaker
        providers: Mapping of layers to provider names
        optimization: Feature flags (useEventChecking, etc.)
        inter_cloud: Cross-cloud connection configuration
    """
    
    # Core settings from config.json
    digital_twin_name: str
    hot_storage_size_in_days: int
    cold_storage_size_in_days: int
    mode: str
    
    # From config_iot_devices.json
    iot_devices: list[dict] = field(default_factory=list)
    
    # From config_events.json
    events: list[dict] = field(default_factory=list)
    
    # From config_hierarchy.json
    hierarchy: list[dict] = field(default_factory=list)
    
    # From config_providers.json
    # Maps layer keys to provider names
    # e.g., {"layer_1_provider": "aws", "layer_2_provider": "azure"}
    providers: Dict[str, str] = field(default_factory=dict)
    
    # From config_optimization.json
    # Feature flags for optional components
    # e.g., {"useEventChecking": true, "triggerNotificationWorkflow": false}
    optimization: Dict[str, Any] = field(default_factory=dict)
    
    # From config_inter_cloud.json
    # Cross-cloud connection configuration
    # e.g., {"connections": {"aws_l1_to_azure_l2": {"url": "...", "token": "..."}}}
    inter_cloud: Dict[str, Any] = field(default_factory=dict)
    
    def get_provider_for_layer(self, layer: int | str) -> str:
        """
        Get the provider name for a specific layer.
        
        Args:
            layer: Layer number (1-5) or string like "3_hot", "3_cold", "3_archive"
        
        Returns:
            Provider name (e.g., "aws", "azure", "gcp")
        
        Raises:
            KeyError: If no provider is configured for the layer
        
        Example:
            >>> config.get_provider_for_layer(1)
            "aws"
            >>> config.get_provider_for_layer("3_hot")
            "azure"
        """
        # Normalize layer to config key format
        if isinstance(layer, int):
            if layer == 3:
                # Default L3 refers to hot storage
                layer_key = "layer_3_hot_provider"
            else:
                layer_key = f"layer_{layer}_provider"
        else:
            # Already a string like "3_hot"
            layer_key = f"layer_{layer}_provider"
        
        if layer_key not in self.providers:
            raise KeyError(f"No provider configured for {layer_key}")
        
        return self.providers[layer_key]
    
    def is_optimization_enabled(self, flag_name: str) -> bool:
        """
        Check if an optimization feature is enabled.
        
        Args:
            flag_name: Name of the optimization flag (e.g., "useEventChecking")
        
        Returns:
            True if the flag is enabled, False otherwise (default)
        
        Example:
            >>> config.is_optimization_enabled("useEventChecking")
            True
        """
        return self.optimization.get(flag_name, False)


@dataclass
class DeploymentContext:
    """
    Encapsulates all state needed for a deployment operation.
    
    This replaces global variables and is explicitly passed to all
    deployer functions, making dependencies clear and testing easy.
    
    Lifecycle:
        1. Created at the start of a deployment (CLI/API request)
        2. Config is loaded from project files
        3. Providers are initialized with credentials
        4. Passed to all deploy/destroy functions
        5. Garbage collected after request completes
    
    Attributes:
        project_name: Name of the project being deployed
        project_path: Path to the project directory
        config: Parsed ProjectConfig
        providers: Initialized CloudProvider instances by name
        credentials: Raw credentials by provider name
        active_layer: Currently deploying layer (for logging)
    
    Example Usage:
        # Create context
        context = DeploymentContext(
            project_name="factory-twin",
            project_path=Path("/app/upload/factory-twin"),
            config=loaded_config,
        )
        
        # Initialize providers based on config
        for provider_name in {"aws", "azure"}:
            provider = ProviderRegistry.get(provider_name)
            provider.initialize_clients(
                credentials[provider_name],
                context.config.digital_twin_name
            )
            context.providers[provider_name] = provider
        
        # Deploy
        deploy_l1(context)
    """
    
    # Project identification
    project_name: str
    project_path: Path
    
    # Parsed configuration (from load_project_config)
    config: ProjectConfig
    
    # Initialized provider instances, keyed by provider name
    # e.g., {"aws": AWSProvider(), "azure": AzureProvider()}
    providers: Dict[str, 'CloudProvider'] = field(default_factory=dict)
    
    # Raw credentials by provider name (used for provider initialization)
    # e.g., {"aws": {"aws_access_key_id": "...", ...}}
    credentials: Dict[str, dict] = field(default_factory=dict)
    
    # Currently active layer (for logging context)
    active_layer: Optional[int | str] = None
    
    def get_provider_for_layer(self, layer: int | str) -> 'CloudProvider':
        """
        Get the initialized CloudProvider for a specific layer.
        
        This is the core routing mechanism for multi-cloud deployments.
        It uses the config to determine which provider handles a layer,
        then returns the initialized provider instance.
        
        Args:
            layer: Layer number (1-5) or string like "3_hot", "3_cold"
        
        Returns:
            The initialized CloudProvider instance for that layer.
        
        Raises:
            KeyError: If no provider is configured for the layer
            ValueError: If the provider is configured but not initialized
        
        Example:
            >>> provider = context.get_provider_for_layer(1)
            >>> provider.name
            "aws"
            >>> strategy = provider.get_deployer_strategy()
            >>> strategy.deploy_l1(context)
        """
        # Get provider name from config
        provider_name = self.config.get_provider_for_layer(layer)
        
        # Get initialized provider instance
        if provider_name not in self.providers:
            raise ValueError(
                f"Provider '{provider_name}' is configured for layer {layer} "
                f"but has not been initialized. Call initialize_providers() first."
            )
        
        return self.providers[provider_name]
    
    def get_upload_path(self, *subpaths: str) -> Path:
        """
        Get a path within the project upload directory.
        
        This is a convenience method for constructing paths to
        project assets like Lambda functions, config files, etc.
        
        Args:
            *subpaths: Path components to join after the project path
        
        Returns:
            Path object for the requested location
        
        Example:
            >>> context.get_upload_path("lambda_functions", "dispatcher")
            Path("/app/upload/factory-twin/lambda_functions/dispatcher")
        """
        return self.project_path.joinpath(*subpaths)
    
    def set_active_layer(self, layer: int | str) -> None:
        """
        Set the currently active layer for logging context.
        
        Args:
            layer: The layer number or name being deployed/destroyed
        """
        self.active_layer = layer
    
    def get_inter_cloud_connection(self, source_layer: str, target_layer: str) -> dict:
        """
        Get inter-cloud connection configuration.
        
        Used when deploying connectors between clouds (e.g., AWS L1 → Azure L2).
        
        Args:
            source_layer: Source layer identifier (e.g., "aws_l1")
            target_layer: Target layer identifier (e.g., "azure_l2")
        
        Returns:
            Connection config with "url" and "token" keys
        
        Raises:
            KeyError: If no connection is configured for this route
        """
        conn_id = f"{source_layer}_to_{target_layer}"
        connections = self.config.inter_cloud.get("connections", {})
        
        if conn_id not in connections:
            raise KeyError(
                f"No inter-cloud connection configured for '{conn_id}'. "
                f"Check config_inter_cloud.json"
            )
        
        return connections[conn_id]
