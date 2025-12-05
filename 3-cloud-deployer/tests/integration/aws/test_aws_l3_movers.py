import pytest
import boto3
import aws.core_deployer_aws as core_aws
import aws.globals_aws as globals_aws
from unittest.mock import MagicMock

def test_create_hot_cold_mover_iam_role(mock_aws_context):
    """Verify Hot-Cold Mover IAM role."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_hot_cold_mover_iam_role()
    
    client = boto3.client("iam")
    role_name = globals_aws.hot_cold_mover_iam_role_name()
    assert client.get_role(RoleName=role_name)

def test_create_hot_cold_mover_event_rule(mock_aws_context):
    """Verify Hot-Cold Mover Event Rule."""
    # Prereq: Lambda must exist (for add_permission)
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_hot_cold_mover_iam_role()
    core_aws.create_hot_cold_mover_lambda_function()
    
    core_aws.create_hot_cold_mover_event_rule()
    
    client = boto3.client("events")
    rule_name = globals_aws.hot_cold_mover_event_rule_name()
    resp = client.describe_rule(Name=rule_name)
    assert resp["Name"] == rule_name
    assert resp["State"] == "ENABLED"

def test_create_cold_archive_mover_components(mock_aws_context):
    """Verify Cold-Archive Mover components (Role, Function, Rule)."""
    # 1. Role
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_cold_archive_mover_iam_role()
    
    client_iam = boto3.client("iam")
    role_name = globals_aws.cold_archive_mover_iam_role_name()
    assert client_iam.get_role(RoleName=role_name)
    
    # 2. Function
    core_aws.create_cold_archive_mover_lambda_function()
    client_lambda = boto3.client("lambda")
    func_name = globals_aws.cold_archive_mover_lambda_function_name()
    assert client_lambda.get_function(FunctionName=func_name)
    
    # 3. Rule
    core_aws.create_cold_archive_mover_event_rule()
    client_events = boto3.client("events")
    rule_name = globals_aws.cold_archive_mover_event_rule_name()
    resp = client_events.describe_rule(Name=rule_name)
    assert resp["Name"] == rule_name

def test_destroy_cold_archive_mover_components(mock_aws_context):
    """Verify Cold-Archive Mover destruction (Role, Function, Rule)."""
    # Setup
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_cold_archive_mover_iam_role()
    core_aws.create_cold_archive_mover_lambda_function()
    core_aws.create_cold_archive_mover_event_rule()
    
    # Destroy
    core_aws.destroy_cold_archive_mover_event_rule()
    core_aws.destroy_cold_archive_mover_lambda_function()
    core_aws.destroy_cold_archive_mover_iam_role()
    
    # Verify Rule
    client_events = boto3.client("events")
    with pytest.raises(client_events.exceptions.ResourceNotFoundException):
        client_events.describe_rule(Name=globals_aws.cold_archive_mover_event_rule_name())
        
    # Verify Function
    client_lambda = boto3.client("lambda")
    with pytest.raises(client_lambda.exceptions.ResourceNotFoundException):
        client_lambda.get_function(FunctionName=globals_aws.cold_archive_mover_lambda_function_name())
        
    # Verify Role
    client_iam = boto3.client("iam")
    with pytest.raises(client_iam.exceptions.NoSuchEntityException):
        client_iam.get_role(RoleName=globals_aws.cold_archive_mover_iam_role_name())

