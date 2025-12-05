import pytest
import boto3
import json
import aws.core_deployer_aws as core_aws
import aws.globals_aws as globals_aws
from unittest.mock import MagicMock

def test_create_persister_iam_role(mock_aws_context):
    """Verify Persister IAM role is created and policies are attached (mocked)."""
    # Mock attach_role_policy
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    
    core_aws.create_persister_iam_role()
    
    client = boto3.client("iam")
    role_name = globals_aws.persister_iam_role_name()
    
    # Check Role
    role = client.get_role(RoleName=role_name)
    assert role["Role"]["RoleName"] == role_name
    
    # Check Attach Calls
    assert globals_aws.aws_iam_client.attach_role_policy.called

def test_create_persister_lambda_function(mock_aws_context):
    """Verify Persister Lambda function is created."""
    # Pre-requisite: Role must exist
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_persister_iam_role()
    
    core_aws.create_persister_lambda_function()
    
    client = boto3.client("lambda")
    func_name = globals_aws.persister_lambda_function_name()
    
    resp = client.get_function(FunctionName=func_name)
    assert resp["Configuration"]["FunctionName"] == func_name
    # Verify environment variables if any specific ones are expected

def test_create_event_checker_lambda_function(mock_aws_context):
    """Verify Event Checker Lambda function is created."""
    # Pre-requisite: Role must exist
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_event_checker_iam_role()
    
    core_aws.create_event_checker_lambda_function()
    
    client = boto3.client("lambda")
    func_name = globals_aws.event_checker_lambda_function_name()
    
    resp = client.get_function(FunctionName=func_name)
    assert resp["Configuration"]["FunctionName"] == func_name

def test_destroy_persister_lambda_function(mock_aws_context):
    """Verify Persister creation and destruction."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_persister_iam_role()
    core_aws.create_persister_lambda_function()
    
    core_aws.destroy_persister_lambda_function()
    
    client = boto3.client("lambda")
    with pytest.raises(client.exceptions.ResourceNotFoundException):
        client.get_function(FunctionName=globals_aws.persister_lambda_function_name())

def test_destroy_persister_iam_role(mock_aws_context):
    """Verify Persister IAM role destruction."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_persister_iam_role()
    
    core_aws.destroy_persister_iam_role()
    
    client = boto3.client("iam")
    with pytest.raises(client.exceptions.NoSuchEntityException):
        client.get_role(RoleName=globals_aws.persister_iam_role_name())

def test_destroy_event_checker_lambda_function(mock_aws_context):
    """Verify Event Checker creation and destruction."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_event_checker_iam_role()
    core_aws.create_event_checker_lambda_function()
    
    core_aws.destroy_event_checker_lambda_function()
    
    client = boto3.client("lambda")
    with pytest.raises(client.exceptions.ResourceNotFoundException):
        client.get_function(FunctionName=globals_aws.event_checker_lambda_function_name())
