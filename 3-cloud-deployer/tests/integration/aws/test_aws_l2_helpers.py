import pytest
import boto3
import aws.core_deployer_aws as core_aws
import aws.globals_aws as globals_aws
from unittest.mock import MagicMock

def test_create_event_checker_iam_role(mock_aws_context):
    """Verify Event Checker IAM role creation."""
    # Mock attach_role_policy
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    
    core_aws.create_event_checker_iam_role()
    
    client = boto3.client("iam")
    role_name = globals_aws.event_checker_iam_role_name()
    
    # Check Role
    role = client.get_role(RoleName=role_name)
    assert role["Role"]["RoleName"] == role_name
    
    # Verify we tried to attach policies
    assert globals_aws.aws_iam_client.attach_role_policy.call_count >= 1

def test_redeploy_event_checker_lambda_function(mock_aws_context):
    """Verify Event Checker Lambda redeployment logic."""
    # Setup: Create initial function
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()

    core_aws.create_event_checker_iam_role()

    # Pre-requisites: Event Feedback and Lambda Chain
    core_aws.create_event_feedback_iam_role()
    core_aws.create_event_feedback_lambda_function()
    
    core_aws.create_lambda_chain_iam_role()
    core_aws.create_lambda_chain_step_function()
    
    core_aws.create_event_checker_lambda_function()
    
    # Verify it exists
    client = boto3.client("lambda")
    func_name = globals_aws.event_checker_lambda_function_name()
    assert client.get_function(FunctionName=func_name)
    
    # Redeploy (should destroy and recreating)
    # We can't easily spy on destroy/create without mocking core_aws itself, 
    # but we can verify the function still exists and no error was raised.
    core_aws.redeploy_event_checker_lambda_function()
    
    assert client.get_function(FunctionName=func_name)
