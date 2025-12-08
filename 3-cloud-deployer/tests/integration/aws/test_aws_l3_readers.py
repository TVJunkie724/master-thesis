"""
Integration tests for L3 Reader components using new provider pattern.
"""

import pytest
from unittest.mock import MagicMock, patch
from moto import mock_aws


class TestHotReader:
    """Tests for Hot Reader components."""

    @patch("util.compile_lambda_function")
    def test_create_hot_reader_components(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Hot Reader IAM + Lambda creation."""
        from src.providers.aws.layers.layer_3_storage import (
            create_hot_reader_iam_role, create_hot_reader_lambda_function
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_hot_reader_iam_role(mock_provider)
        create_hot_reader_lambda_function(mock_provider, mock_config, project_path)
        
        function_name = mock_provider.naming.hot_reader_lambda_function()
        response = mock_provider.clients["lambda"].get_function(FunctionName=function_name)
        assert response["Configuration"]["FunctionName"] == function_name

    @patch("util.compile_lambda_function")
    def test_destroy_hot_reader_components(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Hot Reader destruction."""
        from src.providers.aws.layers.layer_3_storage import (
            create_hot_reader_iam_role, create_hot_reader_lambda_function,
            destroy_hot_reader_iam_role, destroy_hot_reader_lambda_function
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_hot_reader_iam_role(mock_provider)
        create_hot_reader_lambda_function(mock_provider, mock_config, project_path)
        
        destroy_hot_reader_lambda_function(mock_provider)
        destroy_hot_reader_iam_role(mock_provider)
        
        role_name = mock_provider.naming.hot_reader_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)


class TestHotReaderLastEntry:
    """Tests for Hot Reader Last Entry components."""

    @patch("util.compile_lambda_function")
    def test_create_hot_reader_last_entry_components(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Hot Reader Last Entry IAM + Lambda creation."""
        from src.providers.aws.layers.layer_3_storage import (
            create_hot_reader_last_entry_iam_role, create_hot_reader_last_entry_lambda_function
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_hot_reader_last_entry_iam_role(mock_provider)
        create_hot_reader_last_entry_lambda_function(mock_provider, mock_config, project_path)
        
        function_name = mock_provider.naming.hot_reader_last_entry_lambda_function()
        response = mock_provider.clients["lambda"].get_function(FunctionName=function_name)
        assert response["Configuration"]["FunctionName"] == function_name

    @patch("util.compile_lambda_function")
    def test_destroy_hot_reader_last_entry_components(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Hot Reader Last Entry destruction."""
        from src.providers.aws.layers.layer_3_storage import (
            create_hot_reader_last_entry_iam_role, create_hot_reader_last_entry_lambda_function,
            destroy_hot_reader_last_entry_iam_role, destroy_hot_reader_last_entry_lambda_function
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_hot_reader_last_entry_iam_role(mock_provider)
        create_hot_reader_last_entry_lambda_function(mock_provider, mock_config, project_path)
        
        destroy_hot_reader_last_entry_lambda_function(mock_provider)
        destroy_hot_reader_last_entry_iam_role(mock_provider)
        
        role_name = mock_provider.naming.hot_reader_last_entry_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)
