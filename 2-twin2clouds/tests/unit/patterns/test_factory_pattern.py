"""
Tests for Factory Pattern Implementation
=========================================
Tests the PriceFetcherFactory and PriceFetcher Protocol.
"""

import pytest
from backend.fetch_data.factory import (
    PriceFetcher,
    PriceFetcherFactory,
    AWSPriceFetcher,
    AzurePriceFetcher,
    GCPPriceFetcher,
)


# =============================================================================
# Protocol Compliance Tests
# =============================================================================

class TestProtocolCompliance:
    """Test that all fetcher classes implement the Protocol correctly."""
    
    def test_all_fetchers_implement_protocol(self):
        """All fetcher classes should be instances of PriceFetcher."""
        fetchers = PriceFetcherFactory.get_all()
        
        assert len(fetchers) == 3
        for fetcher in fetchers:
            assert isinstance(fetcher, PriceFetcher)
    
    def test_aws_fetcher_has_name(self):
        """AWSPriceFetcher should have 'aws' as name."""
        fetcher = AWSPriceFetcher()
        assert fetcher.name == "aws"
    
    def test_azure_fetcher_has_name(self):
        """AzurePriceFetcher should have 'azure' as name."""
        fetcher = AzurePriceFetcher()
        assert fetcher.name == "azure"
    
    def test_gcp_fetcher_has_name(self):
        """GCPPriceFetcher should have 'gcp' as name."""
        fetcher = GCPPriceFetcher()
        assert fetcher.name == "gcp"
    
    def test_all_fetchers_have_fetch_method(self):
        """All fetchers should have fetch_price method."""
        for fetcher in PriceFetcherFactory.get_all():
            assert hasattr(fetcher, "fetch_price")
            assert callable(fetcher.fetch_price)


# =============================================================================
# Factory Tests
# =============================================================================

class TestPriceFetcherFactory:
    """Test PriceFetcherFactory functionality."""
    
    def test_create_aws_fetcher(self):
        """Factory should create AWSPriceFetcher for 'aws'."""
        fetcher = PriceFetcherFactory.create("aws")
        
        assert isinstance(fetcher, AWSPriceFetcher)
        assert fetcher.name == "aws"
    
    def test_create_azure_fetcher(self):
        """Factory should create AzurePriceFetcher for 'azure'."""
        fetcher = PriceFetcherFactory.create("azure")
        
        assert isinstance(fetcher, AzurePriceFetcher)
        assert fetcher.name == "azure"
    
    def test_create_gcp_fetcher(self):
        """Factory should create GCPPriceFetcher for 'gcp'."""
        fetcher = PriceFetcherFactory.create("gcp")
        
        assert isinstance(fetcher, GCPPriceFetcher)
        assert fetcher.name == "gcp"
    
    def test_create_case_insensitive(self):
        """Factory should handle case-insensitive provider names."""
        fetcher1 = PriceFetcherFactory.create("AWS")
        fetcher2 = PriceFetcherFactory.create("Aws")
        fetcher3 = PriceFetcherFactory.create("aws")
        
        assert fetcher1.name == "aws"
        assert fetcher2.name == "aws"
        assert fetcher3.name == "aws"
    
    def test_create_unknown_provider(self):
        """Factory should raise ValueError for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            PriceFetcherFactory.create("unknown")
    
    def test_get_all_returns_all_fetchers(self):
        """get_all() should return all registered fetchers."""
        fetchers = PriceFetcherFactory.get_all()
        
        names = {f.name for f in fetchers}
        assert names == {"aws", "azure", "gcp"}
    
    def test_available_providers(self):
        """available_providers() should list all registered provider names."""
        providers = PriceFetcherFactory.available_providers()
        
        assert "aws" in providers
        assert "azure" in providers
        assert "gcp" in providers


# =============================================================================
# Custom Registration Tests
# =============================================================================

class TestCustomRegistration:
    """Test custom fetcher registration for testing/extensibility."""
    
    def test_register_mock_fetcher(self):
        """Custom mock fetcher can be registered."""
        class MockFetcher:
            name = "mock"
            def fetch_price(self, *args, **kwargs):
                return {"price": 0.0}
        
        # Register mock
        PriceFetcherFactory.register("mock", MockFetcher)
        
        # Should be available
        fetcher = PriceFetcherFactory.create("mock")
        assert fetcher.name == "mock"
        assert fetcher.fetch_price() == {"price": 0.0}
        
        # Cleanup - remove mock from registry
        del PriceFetcherFactory._registry["mock"]
    
    def test_override_existing_fetcher(self):
        """Existing fetcher can be overridden (useful for mocking in tests)."""
        original = AWSPriceFetcher
        
        class MockAWSFetcher:
            name = "aws"
            def fetch_price(self, *args, **kwargs):
                return {"mocked": True}
        
        PriceFetcherFactory.register("aws", MockAWSFetcher)
        fetcher = PriceFetcherFactory.create("aws")
        assert fetcher.fetch_price()["mocked"] is True
        
        # Restore original
        PriceFetcherFactory.register("aws", original)


# =============================================================================
# Edge Cases
# =============================================================================

class TestFactoryEdgeCases:
    """Test edge cases for the factory."""
    
    def test_create_multiple_instances(self):
        """Each create() call should return a new instance."""
        fetcher1 = PriceFetcherFactory.create("aws")
        fetcher2 = PriceFetcherFactory.create("aws")
        
        assert fetcher1 is not fetcher2
    
    def test_get_all_returns_new_instances(self):
        """get_all() should return new instances each time."""
        fetchers1 = PriceFetcherFactory.get_all()
        fetchers2 = PriceFetcherFactory.get_all()
        
        for f1, f2 in zip(fetchers1, fetchers2):
            assert f1 is not f2
    
    def test_empty_provider_name(self):
        """Empty provider name should raise ValueError."""
        with pytest.raises(ValueError):
            PriceFetcherFactory.create("")
