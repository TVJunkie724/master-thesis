"""
Integration tests for dynamic AWS deployment based on configuration flags.

These tests verify that deployment functions correctly read optimization flags
and deploy resources conditionally.
"""

import pytest
from unittest.mock import MagicMock, patch
import globals


@pytest.fixture
def mock_aws_strategy():
    """Mock the AWS deployer strategy to prevent actual AWS calls."""
    with patch("providers.deployer._get_strategy") as mock_get:
        mock_strategy = MagicMock()
        mock_get.return_value = mock_strategy
        yield mock_strategy


class TestL2DynamicDeployment:
    """Tests for Layer 2 dynamic deployment based on optimization flags."""

    def test_deploy_l2_calls_strategy(self, mock_aws_strategy):
        """Verify L2 deployment calls the strategy."""
        import deployers.core_deployer as core_deployer
        
        # Execute
        core_deployer.deploy_l2("aws")
        
        # Verify strategy.deploy_l2 was called
        mock_aws_strategy.deploy_l2.assert_called()

    def test_destroy_l2_calls_strategy(self, mock_aws_strategy):
        """Verify L2 destruction calls the strategy."""
        import deployers.core_deployer as core_deployer
        
        # Execute
        core_deployer.destroy_l2("aws")
        
        # Verify strategy.destroy_l2 was called
        mock_aws_strategy.destroy_l2.assert_called()


class TestL3DynamicDeployment:
    """Tests for Layer 3 dynamic deployment based on provider configuration."""

    def test_deploy_l3_hot_calls_strategy(self, mock_aws_strategy):
        """Verify L3 hot deployment calls the strategy."""
        import deployers.core_deployer as core_deployer
        
        # Execute
        core_deployer.deploy_l3_hot("aws")
        
        # Verify strategy.deploy_l3_hot was called
        mock_aws_strategy.deploy_l3_hot.assert_called()

    def test_deploy_l3_requires_provider(self):
        """Verify L3 deployment requires a provider argument."""
        import deployers.core_deployer as core_deployer
        
        with pytest.raises(ValueError, match="Provider must be specified"):
            core_deployer.deploy_l3_hot(None)

    def test_deploy_l3_full_calls_all_tiers(self, mock_aws_strategy):
        """Verify deploy_l3 calls hot, cold, and archive."""
        import deployers.core_deployer as core_deployer
        
        # Execute
        core_deployer.deploy_l3("aws")
        
        # Verify all three tiers were called
        mock_aws_strategy.deploy_l3_hot.assert_called()
        mock_aws_strategy.deploy_l3_cold.assert_called()
        mock_aws_strategy.deploy_l3_archive.assert_called()
