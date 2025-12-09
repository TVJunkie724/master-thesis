"""
Integration tests for L2 Compute components using new provider pattern.
"""

import pytest
import boto3
from unittest.mock import MagicMock, patch
from moto import mock_aws


class TestPersister:
    """Tests for Persister components."""

    def test_create_persister_iam_role(self, mock_provider):
        """Verify Persister IAM role creation."""
        from src.providers.aws.layers.layer_2_compute import create_persister_iam_role
        
        create_persister_iam_role(mock_provider)
        
        role_name = mock_provider.naming.persister_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    def test_destroy_persister_iam_role(self, mock_provider):
        """Verify Persister IAM role destruction."""
        from src.providers.aws.layers.layer_2_compute import (
            create_persister_iam_role, destroy_persister_iam_role
        )
        
        create_persister_iam_role(mock_provider)
        destroy_persister_iam_role(mock_provider)
        
        role_name = mock_provider.naming.persister_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)

    @patch("src.util.compile_lambda_function")
    def test_create_persister_lambda_function(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Persister Lambda creation."""
        from src.providers.aws.layers.layer_2_compute import (
            create_persister_iam_role, create_persister_lambda_function
        )
        
        mock_compile.return_value = b"fake-zip-content"
        
        create_persister_iam_role(mock_provider)
        create_persister_lambda_function(mock_provider, mock_config, project_path)
        
        function_name = mock_provider.naming.persister_lambda_function()
        response = mock_provider.clients["lambda"].get_function(FunctionName=function_name)
        assert response["Configuration"]["FunctionName"] == function_name


class TestEventChecker:
    """Tests for Event Checker components."""

    def test_create_event_checker_iam_role(self, mock_provider):
        """Verify Event Checker IAM role creation."""
        from src.providers.aws.layers.layer_2_compute import create_event_checker_iam_role
        
        create_event_checker_iam_role(mock_provider)
        
        role_name = mock_provider.naming.event_checker_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    def test_destroy_event_checker_iam_role(self, mock_provider):
        """Verify Event Checker IAM role destruction."""
        from src.providers.aws.layers.layer_2_compute import (
            create_event_checker_iam_role, destroy_event_checker_iam_role
        )
        
        create_event_checker_iam_role(mock_provider)
        destroy_event_checker_iam_role(mock_provider)
        
        role_name = mock_provider.naming.event_checker_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)


class TestLambdaChain:
    """Tests for Lambda Chain (Step Function) components."""

    def test_create_lambda_chain_iam_role(self, mock_provider):
        """Verify Lambda Chain IAM role creation."""
        from src.providers.aws.layers.layer_2_compute import create_lambda_chain_iam_role
        
        create_lambda_chain_iam_role(mock_provider)
        
        role_name = mock_provider.naming.lambda_chain_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    def test_destroy_lambda_chain_iam_role(self, mock_provider):
        """Verify Lambda Chain IAM role destruction."""
        from src.providers.aws.layers.layer_2_compute import (
            create_lambda_chain_iam_role, destroy_lambda_chain_iam_role
        )
        
        create_lambda_chain_iam_role(mock_provider)
        destroy_lambda_chain_iam_role(mock_provider)
        
        role_name = mock_provider.naming.lambda_chain_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)


class TestEventFeedback:
    """Tests for Event Feedback components."""

    def test_create_event_feedback_iam_role(self, mock_provider):
        """Verify Event Feedback IAM role creation."""
        from src.providers.aws.layers.layer_2_compute import create_event_feedback_iam_role
        
        create_event_feedback_iam_role(mock_provider)
        
        role_name = mock_provider.naming.event_feedback_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    def test_destroy_event_feedback_iam_role(self, mock_provider):
        """Verify Event Feedback IAM role destruction."""
        from src.providers.aws.layers.layer_2_compute import (
            create_event_feedback_iam_role, destroy_event_feedback_iam_role
        )
        
        create_event_feedback_iam_role(mock_provider)
        destroy_event_feedback_iam_role(mock_provider)
        
        role_name = mock_provider.naming.event_feedback_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)
