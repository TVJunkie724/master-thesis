"""
Factory Pattern: Price Fetcher Factory
=======================================
Provides centralized creation of price fetcher instances.

This module provides:
- PriceFetcher: Protocol (interface) for price fetcher implementations
- PriceFetcherFactory: Factory class for creating fetcher instances

Usage:
    from backend.fetch_data.factory import PriceFetcherFactory
    
    # Create a specific fetcher
    aws_fetcher = PriceFetcherFactory.create("aws")
    prices = aws_fetcher.fetch_price("iotCore", "us-east-1", ...)
    
    # Get all fetchers
    for fetcher in PriceFetcherFactory.get_all():
        print(f"Fetcher: {fetcher.name}")
"""

from typing import Protocol, Dict, Any, Optional, List, runtime_checkable


# =============================================================================
# Price Fetcher Protocol
# =============================================================================

@runtime_checkable
class PriceFetcher(Protocol):
    """
    Protocol interface for cloud price fetchers.
    
    Each cloud provider (AWS, Azure, GCP) implements this protocol
    to provide consistent price fetching capabilities.
    
    The interface uses **kwargs to accommodate provider-specific parameters:
    - AWS: service_code (str), aws_credentials (dict)
    - Azure: service_mapping (dict)
    - GCP: billing_client (CloudCatalogClient)
    """
    
    name: str  # Provider identifier: "aws", "azure", or "gcp"
    
    def fetch_price(
        self,
        service_name: str,
        region_code: str,
        region_map: Dict[str, str],
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch pricing data for a specific service in a region.
        
        Args:
            service_name: Service identifier (e.g., "iot", "functions")
            region_code: Cloud region code
            region_map: Mapping of region codes to human-readable names
            debug: Enable debug logging
            **kwargs: Provider-specific parameters:
                - AWS: service_code (str), aws_credentials (dict)
                - Azure: service_mapping (dict)
                - GCP: billing_client (CloudCatalogClient instance)
            
        Returns:
            Dictionary with pricing data for the service
        """
        ...


# =============================================================================
# Concrete Fetcher Wrappers
# =============================================================================

class AWSPriceFetcher:
    """
    AWS price fetcher implementing PriceFetcher Protocol.
    
    Required kwargs:
        - service_code (str): AWS service code for pricing API
        - aws_credentials (dict): AWS credentials for API authentication
    """
    
    name: str = "aws"
    
    def fetch_price(
        self,
        service_name: str,
        region_code: str,
        region_map: Dict[str, str],
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Fetch AWS pricing data using the AWS Pricing API."""
        from backend.fetch_data.cloud_price_fetcher_aws import fetch_aws_price
        
        service_code = kwargs.get("service_code", service_name)
        aws_credentials = kwargs.get("aws_credentials")
        
        return fetch_aws_price(
            service_name=service_name,
            service_code=service_code,
            region_code=region_code,
            region_map=region_map,
            aws_credentials=aws_credentials,
            debug=debug
        )


class AzurePriceFetcher:
    """
    Azure price fetcher implementing PriceFetcher Protocol.
    
    Required kwargs:
        - service_mapping (dict): Service mapping for Azure service codes
    """
    
    name: str = "azure"
    
    def fetch_price(
        self,
        service_name: str,
        region_code: str,
        region_map: Dict[str, str],
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Fetch Azure pricing data using the Azure Retail Prices API."""
        from backend.fetch_data.cloud_price_fetcher_azure import fetch_azure_price
        
        service_mapping = kwargs.get("service_mapping", {})
        
        return fetch_azure_price(
            service_name=service_name,
            region_code=region_code,
            region_map=region_map,
            service_mapping=service_mapping,
            debug=debug
        )


class GCPPriceFetcher:
    """
    GCP price fetcher implementing PriceFetcher Protocol.
    
    Required kwargs:
        - billing_client: Google Cloud Billing CloudCatalogClient instance
    """
    
    name: str = "gcp"
    
    def fetch_price(
        self,
        service_name: str,
        region_code: str,
        region_map: Dict[str, str],
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Fetch GCP pricing data using the Cloud Billing API."""
        from backend.fetch_data.cloud_price_fetcher_google import fetch_gcp_price
        
        billing_client = kwargs.get("billing_client")
        
        return fetch_gcp_price(
            billing_client=billing_client,
            service_name=service_name,
            region_code=region_code,
            region_map=region_map,
            debug=debug
        )


# =============================================================================
# Price Fetcher Factory
# =============================================================================

class PriceFetcherFactory:
    """
    Factory for creating price fetcher instances.
    
    Provides centralized creation of cloud-specific price fetchers,
    making it easy to add new providers or mock fetchers for testing.
    
    Example:
        >>> fetcher = PriceFetcherFactory.create("aws")
        >>> isinstance(fetcher, PriceFetcher)
        True
        >>> fetcher.name
        'aws'
    """
    
    _registry: Dict[str, type] = {
        "aws": AWSPriceFetcher,
        "azure": AzurePriceFetcher,
        "gcp": GCPPriceFetcher,
    }
    
    @classmethod
    def create(cls, provider: str) -> PriceFetcher:
        """
        Create a price fetcher for the specified provider.
        
        Args:
            provider: Provider name ("aws", "azure", or "gcp")
            
        Returns:
            PriceFetcher instance
            
        Raises:
            ValueError: If provider is not registered
        """
        provider_lower = provider.lower()
        if provider_lower not in cls._registry:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Available: {list(cls._registry.keys())}"
            )
        return cls._registry[provider_lower]()
    
    @classmethod
    def get_all(cls) -> List[PriceFetcher]:
        """
        Get instances of all registered fetchers.
        
        Returns:
            List of all PriceFetcher instances
        """
        return [fetcher_cls() for fetcher_cls in cls._registry.values()]
    
    @classmethod
    def register(cls, provider: str, fetcher_class: type) -> None:
        """
        Register a new fetcher class.
        
        Useful for testing (mock fetchers) or extending with new providers.
        
        Args:
            provider: Provider name
            fetcher_class: Class implementing PriceFetcher protocol
        """
        cls._registry[provider.lower()] = fetcher_class
    
    @classmethod
    def available_providers(cls) -> List[str]:
        """
        Get list of available provider names.
        
        Returns:
            List of registered provider names
        """
        return list(cls._registry.keys())
