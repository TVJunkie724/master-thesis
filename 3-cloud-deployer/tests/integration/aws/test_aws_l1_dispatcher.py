import pytest
import boto3
import json
import aws.core_deployer_aws as core_aws
import aws.globals_aws as globals_aws
from unittest.mock import MagicMock

def test_create_dispatcher_iam_role(mock_aws_context):
    """Verify IAM role is created and policies are attached (mocked)."""
    # Mock attach_role_policy to bypass moto missing managed policies
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    
    core_aws.create_dispatcher_iam_role()
    
    client = boto3.client("iam")
    role_name = globals_aws.dispatcher_iam_role_name()
    
    # Check Role
    role = client.get_role(RoleName=role_name)
    assert role["Role"]["RoleName"] == role_name
    
    # Check Attach Calls
    assert globals_aws.aws_iam_client.attach_role_policy.call_count >= 2

def test_create_dispatcher_lambda_function(mock_aws_context):
    """Verify Lambda function is created."""
    # Pre-requisite: Role must exist (and we mock attach)
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_dispatcher_iam_role()
    
    core_aws.create_dispatcher_lambda_function()
    
    client = boto3.client("lambda")
    func_name = globals_aws.dispatcher_lambda_function_name()
    
    resp = client.get_function(FunctionName=func_name)
    assert resp["Configuration"]["FunctionName"] == func_name
    assert "DIGITAL_TWIN_INFO" in resp["Configuration"]["Environment"]["Variables"]

def test_destroy_dispatcher_lambda_function(mock_aws_context):
    """Verify deletion."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_dispatcher_iam_role()
    core_aws.create_dispatcher_lambda_function()
    
    core_aws.destroy_dispatcher_lambda_function()
    
    client = boto3.client("lambda")
    with pytest.raises(client.exceptions.ResourceNotFoundException):
        client.get_function(FunctionName=globals_aws.dispatcher_lambda_function_name())

def test_dispatcher_iot_rule(mock_aws_context):
    """Verify IoT Rule Creation."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_dispatcher_iam_role()
    core_aws.create_dispatcher_lambda_function()
    
    core_aws.create_dispatcher_iot_rule()
    
    client = boto3.client("iot")
    rule_name = globals_aws.dispatcher_iot_rule_name()
    
    resp = client.get_topic_rule(ruleName=rule_name)
    assert resp["rule"]["ruleName"] == rule_name
    assert "SELECT * FROM" in resp["rule"]["sql"]
