"""
Unit tests for DeploymentContext and ProjectConfig.

Tests the dependency injection pattern implementation.
"""

import pytest
from pathlib import Path
from src.core.context import DeploymentContext, ProjectConfig


class TestProjectConfig:
    """Test suite for ProjectConfig dataclass."""

    def test_get_provider_for_layer_with_int(self):
        """Test getting provider for a layer using integer."""
        config = ProjectConfig(
            digital_twin_name="test-twin",
            hot_storage_size_in_days=30,
            cold_storage_size_in_days=90,
            mode="DEBUG",
            providers={
                "layer_1_provider": "aws",
                "layer_2_provider": "azure",
                "layer_3_hot_provider": "gcp",
            },
        )

        assert config.get_provider_for_layer(1) == "aws"
        assert config.get_provider_for_layer(2) == "azure"

    def test_get_provider_for_layer_3_defaults_to_hot(self):
        """Test that layer 3 without suffix defaults to hot storage."""
        config = ProjectConfig(
            digital_twin_name="test-twin",
            hot_storage_size_in_days=30,
            cold_storage_size_in_days=90,
            mode="DEBUG",
            providers={
                "layer_3_hot_provider": "aws",
            },
        )

        assert config.get_provider_for_layer(3) == "aws"

    def test_get_provider_for_layer_with_string(self):
        """Test getting provider for a layer using string like '3_hot'."""
        config = ProjectConfig(
            digital_twin_name="test-twin",
            hot_storage_size_in_days=30,
            cold_storage_size_in_days=90,
            mode="DEBUG",
            providers={
                "layer_3_hot_provider": "aws",
                "layer_3_cold_provider": "azure",
                "layer_3_archive_provider": "gcp",
            },
        )

        assert config.get_provider_for_layer("3_hot") == "aws"
        assert config.get_provider_for_layer("3_cold") == "azure"
        assert config.get_provider_for_layer("3_archive") == "gcp"

    def test_get_provider_for_missing_layer_raises_error(self):
        """Test that missing layer configuration raises KeyError."""
        config = ProjectConfig(
            digital_twin_name="test-twin",
            hot_storage_size_in_days=30,
            cold_storage_size_in_days=90,
            mode="DEBUG",
            providers={},
        )

        with pytest.raises(KeyError):
            config.get_provider_for_layer(1)

    def test_is_optimization_enabled_returns_true(self):
        """Test checking enabled optimization flag."""
        config = ProjectConfig(
            digital_twin_name="test-twin",
            hot_storage_size_in_days=30,
            cold_storage_size_in_days=90,
            mode="DEBUG",
            optimization={"useEventChecking": True},
        )

        assert config.is_optimization_enabled("useEventChecking") is True

    def test_is_optimization_enabled_returns_false_for_missing(self):
        """Test that missing optimization flags default to False."""
        config = ProjectConfig(
            digital_twin_name="test-twin",
            hot_storage_size_in_days=30,
            cold_storage_size_in_days=90,
            mode="DEBUG",
            optimization={},
        )

        assert config.is_optimization_enabled("nonexistent") is False


class TestDeploymentContext:
    """Test suite for DeploymentContext."""

    def create_test_context(self, providers_config=None, initialized_providers=None):
        """Helper to create test context."""
        config = ProjectConfig(
            digital_twin_name="test-twin",
            hot_storage_size_in_days=30,
            cold_storage_size_in_days=90,
            mode="DEBUG",
            providers=providers_config or {
                "layer_1_provider": "aws",
                "layer_2_provider": "aws",
            },
        )

        return DeploymentContext(
            project_name="test-project",
            project_path=Path("/app/upload/test-project"),
            config=config,
            providers=initialized_providers or {},
        )

    def test_get_provider_for_layer_returns_initialized_provider(self):
        """Test that get_provider_for_layer returns the correct provider."""
        # Create mock provider
        class MockAWSProvider:
            name = "aws"

        mock_provider = MockAWSProvider()

        context = self.create_test_context(
            providers_config={"layer_1_provider": "aws"},
            initialized_providers={"aws": mock_provider},
        )

        result = context.get_provider_for_layer(1)

        assert result is mock_provider
        assert result.name == "aws"

    def test_get_provider_for_layer_raises_on_uninitialized(self):
        """Test error when provider is configured but not initialized."""
        context = self.create_test_context(
            providers_config={"layer_1_provider": "aws"},
            initialized_providers={},  # No providers initialized
        )

        with pytest.raises(ValueError) as exc_info:
            context.get_provider_for_layer(1)

        assert "not been initialized" in str(exc_info.value)

    def test_get_upload_path_joins_correctly(self):
        """Test that get_upload_path correctly joins path components."""
        context = self.create_test_context()

        result = context.get_upload_path("lambda_functions", "dispatcher")

        expected = Path("/app/upload/test-project/lambda_functions/dispatcher")
        assert result == expected

    def test_set_active_layer_updates_state(self):
        """Test that set_active_layer updates the active_layer field."""
        context = self.create_test_context()

        context.set_active_layer(2)
        assert context.active_layer == 2

        context.set_active_layer("3_hot")
        assert context.active_layer == "3_hot"

    def test_get_inter_cloud_connection_returns_config(self):
        """Test retrieving inter-cloud connection configuration."""
        config = ProjectConfig(
            digital_twin_name="test-twin",
            hot_storage_size_in_days=30,
            cold_storage_size_in_days=90,
            mode="DEBUG",
            inter_cloud={
                "connections": {
                    "aws_l1_to_azure_l2": {
                        "url": "https://azure.example.com/ingest",
                        "token": "secret123",
                    }
                }
            },
        )

        context = DeploymentContext(
            project_name="test",
            project_path=Path("/tmp"),
            config=config,
        )

        result = context.get_inter_cloud_connection("aws_l1", "azure_l2")

        assert result["url"] == "https://azure.example.com/ingest"
        assert result["token"] == "secret123"

    def test_get_inter_cloud_connection_raises_on_missing(self):
        """Test error when inter-cloud connection is not configured."""
        config = ProjectConfig(
            digital_twin_name="test-twin",
            hot_storage_size_in_days=30,
            cold_storage_size_in_days=90,
            mode="DEBUG",
            inter_cloud={},
        )

        context = DeploymentContext(
            project_name="test",
            project_path=Path("/tmp"),
            config=config,
        )

        with pytest.raises(KeyError):
            context.get_inter_cloud_connection("aws_l1", "azure_l2")
