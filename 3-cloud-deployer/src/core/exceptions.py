"""
Custom exceptions for the multi-cloud deployer.

This module defines a hierarchy of exceptions used throughout the deployment
system to provide clear, actionable error messages.

Exception Hierarchy:
    DeploymentError (base)
    ├── ProviderNotFoundError - Unknown provider name requested
    ├── ConfigurationError - Invalid or missing configuration
    ├── ResourceCreationError - Failed to create cloud resource
    └── ResourceDeletionError - Failed to delete cloud resource
"""

from typing import Optional


class DeploymentError(Exception):
    """
    Base exception for all deployment-related errors.
    
    All custom exceptions in the deployer inherit from this class,
    allowing broad exception handling when needed.
    
    Attributes:
        message: Human-readable error description
        provider: Optional provider name where error occurred
        layer: Optional layer number (1-5) where error occurred
    """
    
    def __init__(
        self, 
        message: str, 
        provider: Optional[str] = None, 
        layer: Optional[int] = None
    ):
        self.message = message
        self.provider = provider
        self.layer = layer
        
        # Build detailed message with context
        details = []
        if provider:
            details.append(f"provider={provider}")
        if layer:
            details.append(f"layer=L{layer}")
        
        if details:
            full_message = f"{message} [{', '.join(details)}]"
        else:
            full_message = message
            
        super().__init__(full_message)


class ProviderNotFoundError(DeploymentError):
    """
    Raised when an unknown provider name is requested.
    
    This typically occurs when:
    - A typo in config_providers.json (e.g., "azur" instead of "azure")
    - Requesting a provider that hasn't been registered
    - The provider module failed to import
    
    Example:
        >>> ProviderRegistry.get("unknown")
        ProviderNotFoundError: Provider 'unknown' not found. Available: ['aws', 'azure', 'gcp']
    """
    
    def __init__(self, provider_name: str, available_providers: list[str]):
        self.provider_name = provider_name
        self.available_providers = available_providers
        message = (
            f"Provider '{provider_name}' not found. "
            f"Available: {available_providers}"
        )
        super().__init__(message, provider=provider_name)


class ConfigurationError(DeploymentError):
    """
    Raised when configuration is invalid or missing required fields.
    
    This typically occurs when:
    - Required config file is missing
    - Config file has invalid JSON
    - Required field is missing from config
    - Field value fails validation
    
    Example:
        >>> load_config("nonexistent.json")
        ConfigurationError: Config file not found: nonexistent.json
    """
    
    def __init__(self, message: str, config_file: Optional[str] = None):
        self.config_file = config_file
        if config_file:
            message = f"{message} (file: {config_file})"
        super().__init__(message)


class ResourceCreationError(DeploymentError):
    """
    Raised when a cloud resource fails to create.
    
    This wraps cloud SDK errors with additional context about
    what resource was being created and in which layer.
    
    Attributes:
        resource_type: Type of resource (e.g., "lambda_function", "dynamodb_table")
        resource_name: Name of the resource that failed
        original_error: The underlying SDK exception
    """
    
    def __init__(
        self,
        resource_type: str,
        resource_name: str,
        provider: str,
        layer: int,
        original_error: Optional[Exception] = None
    ):
        self.resource_type = resource_type
        self.resource_name = resource_name
        self.original_error = original_error
        
        message = f"Failed to create {resource_type} '{resource_name}'"
        if original_error:
            message += f": {str(original_error)}"
            
        super().__init__(message, provider=provider, layer=layer)


class ResourceDeletionError(DeploymentError):
    """
    Raised when a cloud resource fails to delete.
    
    This wraps cloud SDK errors with additional context about
    what resource was being deleted and in which layer.
    
    Attributes:
        resource_type: Type of resource (e.g., "lambda_function", "dynamodb_table")
        resource_name: Name of the resource that failed
        original_error: The underlying SDK exception
    """
    
    def __init__(
        self,
        resource_type: str,
        resource_name: str,
        provider: str,
        layer: int,
        original_error: Optional[Exception] = None
    ):
        self.resource_type = resource_type
        self.resource_name = resource_name
        self.original_error = original_error
        
        message = f"Failed to delete {resource_type} '{resource_name}'"
        if original_error:
            message += f": {str(original_error)}"
            
        super().__init__(message, provider=provider, layer=layer)
