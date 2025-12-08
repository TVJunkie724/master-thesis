"""
Unit tests for ProviderRegistry.

Tests the Registry pattern implementation for provider lookup.
"""

import pytest
from src.core.registry import ProviderRegistry
from src.core.exceptions import ProviderNotFoundError


class TestProviderRegistry:
    """Test suite for ProviderRegistry."""

    def setup_method(self):
        """Clear registry before each test to ensure isolation."""
        ProviderRegistry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        ProviderRegistry.clear()

    def test_register_and_get_provider(self):
        """Test registering a provider and retrieving it by name."""
        # Arrange
        class MockProvider:
            name = "mock"

        # Act
        ProviderRegistry.register("mock", MockProvider)
        provider = ProviderRegistry.get("mock")

        # Assert
        assert provider.name == "mock"
        assert isinstance(provider, MockProvider)

    def test_get_unknown_provider_raises_error(self):
        """Test that requesting an unknown provider raises ProviderNotFoundError."""
        with pytest.raises(ProviderNotFoundError) as exc_info:
            ProviderRegistry.get("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()

    def test_list_providers_returns_sorted_names(self):
        """Test that list_providers returns all registered names sorted."""
        # Arrange
        class ProviderA:
            pass

        class ProviderB:
            pass

        class ProviderC:
            pass

        ProviderRegistry.register("zulu", ProviderA)
        ProviderRegistry.register("alpha", ProviderB)
        ProviderRegistry.register("mike", ProviderC)

        # Act
        providers = ProviderRegistry.list_providers()

        # Assert
        assert providers == ["alpha", "mike", "zulu"]

    def test_is_registered_returns_correct_boolean(self):
        """Test is_registered check."""
        class MockProvider:
            pass

        ProviderRegistry.register("exists", MockProvider)

        assert ProviderRegistry.is_registered("exists") is True
        assert ProviderRegistry.is_registered("missing") is False

    def test_register_same_class_twice_is_idempotent(self):
        """Test that registering the same class twice is allowed."""
        class MockProvider:
            pass

        # Should not raise
        ProviderRegistry.register("mock", MockProvider)
        ProviderRegistry.register("mock", MockProvider)

        assert ProviderRegistry.is_registered("mock")

    def test_register_different_class_same_name_raises_error(self):
        """Test that registering a different class under the same name raises."""
        class ProviderA:
            pass

        class ProviderB:
            pass

        ProviderRegistry.register("conflict", ProviderA)

        with pytest.raises(ValueError) as exc_info:
            ProviderRegistry.register("conflict", ProviderB)

        assert "already registered" in str(exc_info.value)

    def test_get_returns_new_instance_each_time(self):
        """Test that get() returns a new instance each call."""
        class MockProvider:
            pass

        ProviderRegistry.register("mock", MockProvider)

        provider1 = ProviderRegistry.get("mock")
        provider2 = ProviderRegistry.get("mock")

        # Should be different instances
        assert provider1 is not provider2

    def test_clear_removes_all_providers(self):
        """Test that clear() removes all registered providers."""
        class MockProvider:
            pass

        ProviderRegistry.register("mock", MockProvider)
        assert ProviderRegistry.is_registered("mock")

        ProviderRegistry.clear()

        assert not ProviderRegistry.is_registered("mock")
        assert ProviderRegistry.list_providers() == []
