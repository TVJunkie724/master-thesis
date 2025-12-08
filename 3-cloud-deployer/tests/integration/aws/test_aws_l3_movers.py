"""
Integration tests for L3 Mover components using new provider pattern.
"""

import pytest
from unittest.mock import MagicMock, patch
from moto import mock_aws


class TestHotColdMover:
    """Tests for Hot-to-Cold Mover components."""

    def test_create_hot_cold_mover_iam_role(self, mock_provider):
        """Verify Hot-Cold Mover IAM role creation."""
        from src.providers.aws.layers.layer_3_storage import create_hot_cold_mover_iam_role
        
        create_hot_cold_mover_iam_role(mock_provider)
        
        role_name = mock_provider.naming.hot_cold_mover_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    @patch("util.compile_lambda_function")
    def test_create_hot_cold_mover_event_rule(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Hot-Cold Mover EventBridge rule creation."""
        from src.providers.aws.layers.layer_3_storage import (
            create_hot_cold_mover_iam_role, create_hot_cold_mover_lambda_function,
            create_hot_cold_mover_event_rule
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_hot_cold_mover_iam_role(mock_provider)
        create_hot_cold_mover_lambda_function(mock_provider, mock_config, project_path)
        create_hot_cold_mover_event_rule(mock_provider)
        
        rule_name = mock_provider.naming.hot_cold_mover_event_rule()
        response = mock_provider.clients["events"].describe_rule(Name=rule_name)
        assert response["Name"] == rule_name


class TestColdArchiveMover:
    """Tests for Cold-to-Archive Mover components."""

    def test_create_cold_archive_mover_iam_role(self, mock_provider):
        """Verify Cold-Archive Mover IAM role creation."""
        from src.providers.aws.layers.layer_3_storage import create_cold_archive_mover_iam_role
        
        create_cold_archive_mover_iam_role(mock_provider)
        
        role_name = mock_provider.naming.cold_archive_mover_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    @patch("util.compile_lambda_function")
    def test_create_cold_archive_mover_components(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Cold-Archive Mover Lambda creation."""
        from src.providers.aws.layers.layer_3_storage import (
            create_cold_archive_mover_iam_role, create_cold_archive_mover_lambda_function
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_cold_archive_mover_iam_role(mock_provider)
        create_cold_archive_mover_lambda_function(mock_provider, mock_config, project_path)
        
        function_name = mock_provider.naming.cold_archive_mover_lambda_function()
        response = mock_provider.clients["lambda"].get_function(FunctionName=function_name)
        assert response["Configuration"]["FunctionName"] == function_name

    @patch("util.compile_lambda_function")
    def test_destroy_cold_archive_mover_components(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Cold-Archive Mover destruction."""
        from src.providers.aws.layers.layer_3_storage import (
            create_cold_archive_mover_iam_role, create_cold_archive_mover_lambda_function,
            destroy_cold_archive_mover_iam_role, destroy_cold_archive_mover_lambda_function
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_cold_archive_mover_iam_role(mock_provider)
        create_cold_archive_mover_lambda_function(mock_provider, mock_config, project_path)
        
        destroy_cold_archive_mover_lambda_function(mock_provider)
        destroy_cold_archive_mover_iam_role(mock_provider)
        
        role_name = mock_provider.naming.cold_archive_mover_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)
