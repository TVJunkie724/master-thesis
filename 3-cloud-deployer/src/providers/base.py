"""
Shared base classes and utilities for provider implementations.

This module contains code shared across all cloud providers to avoid
duplication. Individual provider modules can inherit from or use
these utilities.

Contents:
    - BaseProvider: Optional base class with common functionality
    - Resource naming utilities
    - Logging helpers
"""

from typing import Optional
from logger import logger


class BaseProvider:
    """
    Optional base class for cloud provider implementations.
    
    This provides common functionality that all providers need.
    Providers can inherit from this or implement CloudProvider directly.
    
    Common Functionality:
        - Twin name storage and validation
        - Logging context
        - Error handling helpers
    
    Note:
        This is an optional base class. Providers are only required
        to implement the CloudProvider protocol. They can inherit from
        BaseProvider for convenience or implement everything themselves.
    """
    
    def __init__(self):
        """Initialize base provider state."""
        self._twin_name: Optional[str] = None
        self._clients: dict = {}
        self._initialized: bool = False
    
    @property
    def twin_name(self) -> str:
        """Get the digital twin name used for resource naming."""
        if not self._twin_name:
            raise RuntimeError(
                "Provider not initialized. Call initialize_clients() first."
            )
        return self._twin_name
    
    @property
    def clients(self) -> dict:
        """Return initialized SDK clients."""
        if not self._initialized:
            raise RuntimeError(
                "Provider not initialized. Call initialize_clients() first."
            )
        return self._clients
    
    def _log_resource_creation(self, resource_type: str, resource_name: str) -> None:
        """
        Log a resource creation event.
        
        Provides consistent logging format across all providers.
        
        Args:
            resource_type: Type of resource (e.g., "IAM Role", "Lambda Function")
            resource_name: Name of the resource being created
        """
        logger.info(f"Creating {resource_type}: {resource_name}")
    
    def _log_resource_deletion(self, resource_type: str, resource_name: str) -> None:
        """
        Log a resource deletion event.
        
        Args:
            resource_type: Type of resource
            resource_name: Name of the resource being deleted
        """
        logger.info(f"Deleting {resource_type}: {resource_name}")
    
    def _log_resource_exists(self, resource_type: str, resource_name: str) -> None:
        """
        Log that a resource already exists (for idempotent operations).
        
        Args:
            resource_type: Type of resource
            resource_name: Name of the existing resource
        """
        logger.info(f"{resource_type} already exists: {resource_name}")
    
    def _log_resource_not_found(self, resource_type: str, resource_name: str) -> None:
        """
        Log that a resource was not found (during deletion).
        
        Args:
            resource_type: Type of resource
            resource_name: Name of the resource that wasn't found
        """
        logger.info(f"{resource_type} not found (already deleted?): {resource_name}")


def generate_resource_name(
    twin_name: str,
    resource_type: str,
    suffix: Optional[str] = None
) -> str:
    """
    Generate a consistent resource name with twin prefix.
    
    All cloud resources are prefixed with the digital twin name to
    create isolated namespaces. This utility ensures consistent naming
    across all providers.
    
    Args:
        twin_name: The digital twin name (e.g., "factory-twin")
        resource_type: Type of resource (e.g., "dispatcher", "hot-table")
        suffix: Optional suffix (e.g., device ID)
    
    Returns:
        Formatted name like "{twin_name}-{resource_type}[-{suffix}]"
    
    Example:
        >>> generate_resource_name("dt", "dispatcher")
        "dt-dispatcher"
        >>> generate_resource_name("dt", "processor", "sensor-001")
        "dt-processor-sensor-001"
    """
    if suffix:
        return f"{twin_name}-{resource_type}-{suffix}"
    return f"{twin_name}-{resource_type}"
