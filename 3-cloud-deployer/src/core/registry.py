"""
Provider registry for dynamic provider lookup.

This module implements the Registry pattern, providing a central place
to register and retrieve cloud provider implementations by name.

Design Pattern: Registry Pattern
    - Providers register themselves when their module is imported
    - Lookup is done by string name (e.g., "aws", "azure", "gcp")
    - Enables runtime provider selection based on configuration

How Registration Works:
    Each provider module (e.g., providers/aws/__init__.py) imports this
    registry and calls register() when the module loads:
    
        # In providers/aws/__init__.py
        from core.registry import ProviderRegistry
        from .provider import AWSProvider
        ProviderRegistry.register("aws", AWSProvider)
    
    Then, to trigger registration, the main providers/__init__.py imports
    all provider modules:
    
        # In providers/__init__.py
        from . import aws  # Triggers aws registration
        from . import azure  # Triggers azure registration
"""

from typing import Dict, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .protocols import CloudProvider

from .exceptions import ProviderNotFoundError


class ProviderRegistry:
    """
    Central registry for cloud provider implementations.
    
    This class uses class-level state (not instance state) because
    providers register themselves at import time, before any instances
    are created.
    
    Thread Safety:
        Registration happens at module import time, which is inherently
        single-threaded in Python. Lookups are read-only and thread-safe.
    
    Example Usage:
        # Registration (done by provider modules at import)
        ProviderRegistry.register("aws", AWSProvider)
        
        # Lookup (done by deployers at runtime)
        provider = ProviderRegistry.get("aws")
        provider.initialize_clients(credentials, twin_name)
        
        # List available providers
        available = ProviderRegistry.list_providers()  # ["aws", "azure", "gcp"]
    """
    
    # Class-level storage for registered providers
    # Key: provider name (e.g., "aws")
    # Value: provider class (not instance)
    _providers: Dict[str, Type['CloudProvider']] = {}
    
    @classmethod
    def register(cls, name: str, provider_class: Type['CloudProvider']) -> None:
        """
        Register a provider class under a name.
        
        This is typically called by provider modules when they are imported.
        Registration is idempotent - registering the same name twice with
        the same class is allowed; different classes will raise an error.
        
        Args:
            name: Provider identifier (e.g., "aws", "azure", "gcp")
            provider_class: The CloudProvider implementation class
        
        Raises:
            ValueError: If name is already registered with a different class
        
        Example:
            # In providers/aws/__init__.py
            from core.registry import ProviderRegistry
            from .provider import AWSProvider
            ProviderRegistry.register("aws", AWSProvider)
        """
        if name in cls._providers:
            existing_class = cls._providers[name]
            if existing_class is not provider_class:
                raise ValueError(
                    f"Provider '{name}' is already registered with {existing_class.__name__}. "
                    f"Cannot re-register with {provider_class.__name__}."
                )
            # Same class registered twice is OK (idempotent)
            return
        
        cls._providers[name] = provider_class
    
    @classmethod
    def get(cls, name: str) -> 'CloudProvider':
        """
        Get a new instance of the named provider.
        
        Creates a fresh instance each time - providers are not singletons.
        This allows multiple deployments with different configurations
        to run concurrently.
        
        Args:
            name: Provider identifier (e.g., "aws", "azure", "gcp")
        
        Returns:
            A new instance of the requested CloudProvider.
        
        Raises:
            ProviderNotFoundError: If no provider is registered with that name.
        
        Example:
            provider = ProviderRegistry.get("aws")
            provider.initialize_clients(credentials, "my-twin")
        """
        if name not in cls._providers:
            raise ProviderNotFoundError(name, list(cls._providers.keys()))
        
        provider_class = cls._providers[name]
        return provider_class()
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """
        List all registered provider names.
        
        Returns:
            List of registered provider names, sorted alphabetically.
        
        Example:
            >>> ProviderRegistry.list_providers()
            ['aws', 'azure', 'gcp']
        """
        return sorted(cls._providers.keys())
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a provider is registered.
        
        Args:
            name: Provider identifier to check
        
        Returns:
            True if the provider is registered, False otherwise.
        """
        return name in cls._providers
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered providers.
        
        This is primarily used for testing to reset state between tests.
        Should not be called in production code.
        """
        cls._providers.clear()
