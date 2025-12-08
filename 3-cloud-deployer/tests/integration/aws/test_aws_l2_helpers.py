"""
Integration tests for L2 helper functions using new provider pattern.
These tests verify the event checker and related helper functions.
"""

import pytest
from unittest.mock import MagicMock, patch
from moto import mock_aws


def test_create_event_checker_iam_role(mock_provider):
    """Verify Event Checker IAM role creation."""
    from src.providers.aws.layers.layer_2_compute import create_event_checker_iam_role
    
    create_event_checker_iam_role(mock_provider)
    
    role_name = mock_provider.naming.event_checker_iam_role()
    response = mock_provider.clients["iam"].get_role(RoleName=role_name)
    assert response["Role"]["RoleName"] == role_name


@patch("util.compile_lambda_function")
def test_redeploy_event_checker_lambda_function(mock_compile, mock_provider, mock_config, project_path):
    """Verify Event Checker Lambda can be redeployed with updates."""
    from src.providers.aws.layers.layer_2_compute import (
        create_event_checker_iam_role, create_event_checker_lambda_function,
        destroy_event_checker_lambda_function
    )
    
    mock_compile.return_value = b"fake-zip-content"
    
    # Create initial
    create_event_checker_iam_role(mock_provider)
    create_event_checker_lambda_function(mock_provider, mock_config, project_path)
    
    # Destroy and recreate to simulate redeployment
    destroy_event_checker_lambda_function(mock_provider)
    create_event_checker_lambda_function(mock_provider, mock_config, project_path)
    
    function_name = mock_provider.naming.event_checker_lambda_function()
    response = mock_provider.clients["lambda"].get_function(FunctionName=function_name)
    assert response["Configuration"]["FunctionName"] == function_name
