"""
Integration tests for L1 Dispatcher components using new provider pattern.
"""

import pytest
import boto3
from unittest.mock import MagicMock, patch
from moto import mock_aws


class TestDispatcherIAMRole:
    """Tests for Dispatcher IAM Role."""

    def test_create_dispatcher_iam_role(self, mock_provider):
        """Verify Dispatcher IAM role creation."""
        from src.providers.aws.layers.layer_1_iot import create_dispatcher_iam_role
        
        create_dispatcher_iam_role(mock_provider)
        
        role_name = mock_provider.naming.dispatcher_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    def test_destroy_dispatcher_iam_role(self, mock_provider):
        """Verify Dispatcher IAM role destruction."""
        from src.providers.aws.layers.layer_1_iot import (
            create_dispatcher_iam_role, destroy_dispatcher_iam_role
        )
        
        create_dispatcher_iam_role(mock_provider)
        destroy_dispatcher_iam_role(mock_provider)
        
        role_name = mock_provider.naming.dispatcher_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)


class TestDispatcherLambda:
    """Tests for Dispatcher Lambda Function."""

    @patch("util.compile_lambda_function")
    def test_create_dispatcher_lambda_function(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Dispatcher Lambda creation."""
        from src.providers.aws.layers.layer_1_iot import (
            create_dispatcher_iam_role, create_dispatcher_lambda_function
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_dispatcher_iam_role(mock_provider)
        create_dispatcher_lambda_function(mock_provider, mock_config, project_path)
        
        function_name = mock_provider.naming.dispatcher_lambda_function()
        response = mock_provider.clients["lambda"].get_function(FunctionName=function_name)
        assert response["Configuration"]["FunctionName"] == function_name

    @patch("util.compile_lambda_function")
    def test_destroy_dispatcher_lambda_function(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Dispatcher Lambda destruction."""
        from src.providers.aws.layers.layer_1_iot import (
            create_dispatcher_iam_role, create_dispatcher_lambda_function, destroy_dispatcher_lambda_function
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_dispatcher_iam_role(mock_provider)
        create_dispatcher_lambda_function(mock_provider, mock_config, project_path)
        destroy_dispatcher_lambda_function(mock_provider)
        
        function_name = mock_provider.naming.dispatcher_lambda_function()
        with pytest.raises(mock_provider.clients["lambda"].exceptions.ResourceNotFoundException):
            mock_provider.clients["lambda"].get_function(FunctionName=function_name)


class TestIoTRule:
    """Tests for IoT Topic Rule."""

    @patch("util.compile_lambda_function")
    def test_create_dispatcher_iot_rule(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify IoT rule creation."""
        from src.providers.aws.layers.layer_1_iot import (
            create_dispatcher_iam_role, create_dispatcher_lambda_function, create_dispatcher_iot_rule
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_dispatcher_iam_role(mock_provider)
        create_dispatcher_lambda_function(mock_provider, mock_config, project_path)
        create_dispatcher_iot_rule(mock_provider, mock_config)
        
        rule_name = mock_provider.naming.dispatcher_iot_rule()
        response = mock_provider.clients["iot"].get_topic_rule(ruleName=rule_name)
        assert response["rule"]["ruleName"] == rule_name

    @patch("util.compile_lambda_function")
    def test_destroy_dispatcher_iot_rule(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify IoT rule destruction."""
        from src.providers.aws.layers.layer_1_iot import (
            create_dispatcher_iam_role, create_dispatcher_lambda_function, 
            create_dispatcher_iot_rule, destroy_dispatcher_iot_rule
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_dispatcher_iam_role(mock_provider)
        create_dispatcher_lambda_function(mock_provider, mock_config, project_path)
        create_dispatcher_iot_rule(mock_provider, mock_config)
        destroy_dispatcher_iot_rule(mock_provider)
        
        rule_name = mock_provider.naming.dispatcher_iot_rule()
        with pytest.raises(mock_provider.clients["iot"].exceptions.ResourceNotFoundException):
            mock_provider.clients["iot"].get_topic_rule(ruleName=rule_name)
