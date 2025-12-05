import pytest
import boto3
import aws.core_deployer_aws as core_aws
import aws.globals_aws as globals_aws
from unittest.mock import MagicMock

def test_create_hot_reader_components(mock_aws_context):
    """Verify Hot Reader Role and Lambda."""
    # 1. Role
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_hot_reader_iam_role()
    
    client_iam = boto3.client("iam")
    role_name = globals_aws.hot_reader_iam_role_name()
    assert client_iam.get_role(RoleName=role_name)
    
    # 2. Function
    core_aws.create_hot_reader_lambda_function()
    client_lambda = boto3.client("lambda")
    func_name = globals_aws.hot_reader_lambda_function_name()
    assert client_lambda.get_function(FunctionName=func_name)

def test_create_hot_reader_last_entry_components(mock_aws_context):
    """Verify Last Entry Reader Role and Lambda."""
    # 1. Role
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_hot_reader_last_entry_iam_role()
    
    client_iam = boto3.client("iam")
    role_name = globals_aws.hot_reader_last_entry_iam_role_name()
    assert client_iam.get_role(RoleName=role_name)
    
    # 2. Function
    core_aws.create_hot_reader_last_entry_lambda_function()
    client_lambda = boto3.client("lambda")
    func_name = globals_aws.hot_reader_last_entry_lambda_function_name()
    assert client_lambda.get_function(FunctionName=func_name)

def test_destroy_hot_reader_components(mock_aws_context):
    """Verify Hot Reader destruction."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_hot_reader_iam_role()
    core_aws.create_hot_reader_lambda_function()
    
    core_aws.destroy_hot_reader_lambda_function()
    core_aws.destroy_hot_reader_iam_role()
    
    # Verify Function
    client_lambda = boto3.client("lambda")
    with pytest.raises(client_lambda.exceptions.ResourceNotFoundException):
        client_lambda.get_function(FunctionName=globals_aws.hot_reader_lambda_function_name())
        
    # Verify Role
    client_iam = boto3.client("iam")
    with pytest.raises(client_iam.exceptions.NoSuchEntityException):
        client_iam.get_role(RoleName=globals_aws.hot_reader_iam_role_name())

def test_destroy_hot_reader_last_entry_components(mock_aws_context):
    """Verify Last Entry Reader destruction."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_hot_reader_last_entry_iam_role()
    core_aws.create_hot_reader_last_entry_lambda_function()
    
    core_aws.destroy_hot_reader_last_entry_lambda_function()
    core_aws.destroy_hot_reader_last_entry_iam_role()
    
    # Verify Function
    client_lambda = boto3.client("lambda")
    with pytest.raises(client_lambda.exceptions.ResourceNotFoundException):
        client_lambda.get_function(FunctionName=globals_aws.hot_reader_last_entry_lambda_function_name())
        
    # Verify Role
    client_iam = boto3.client("iam")
    with pytest.raises(client_iam.exceptions.NoSuchEntityException):
        client_iam.get_role(RoleName=globals_aws.hot_reader_last_entry_iam_role_name())

