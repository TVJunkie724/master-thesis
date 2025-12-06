import pytest
import boto3
import aws.core_deployer_aws as core_aws
import aws.globals_aws as globals_aws
from unittest.mock import MagicMock

def test_create_hot_dynamodb_table(mock_aws_context):
    """Verify DynamoDB Hot Table creation."""
    core_aws.create_hot_dynamodb_table()
    
    client = boto3.client("dynamodb")
    table_name = globals_aws.hot_dynamodb_table_name()
    
    resp = client.describe_table(TableName=table_name)
    assert resp["Table"]["TableName"] == table_name
    # Verify KeySchema
    key_schema = resp["Table"]["KeySchema"]
    assert any(k["AttributeName"] == "iotDeviceId" for k in key_schema) # Assuming 'iotDeviceId' is partition key based on convention

def test_create_cold_s3_bucket(mock_aws_context):
    """Verify Cold S3 Bucket creation."""
    core_aws.create_cold_s3_bucket()
    
    client = boto3.client("s3")
    bucket_name = globals_aws.cold_s3_bucket_name()
    
    # Check if bucket exists
    resp = client.head_bucket(Bucket=bucket_name)
    assert resp["ResponseMetadata"]["HTTPStatusCode"] == 200

def test_create_archive_s3_bucket(mock_aws_context):
    """Verify Archive S3 Bucket creation."""
    core_aws.create_archive_s3_bucket()
    
    client = boto3.client("s3")
    bucket_name = globals_aws.archive_s3_bucket_name()
    
    resp = client.head_bucket(Bucket=bucket_name)
    assert resp["ResponseMetadata"]["HTTPStatusCode"] == 200

def test_create_hot_cold_mover_lambda_function(mock_aws_context):
    """Verify Hot-Cold Mover Lambda creation."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_hot_cold_mover_iam_role()

def test_create_hot_dynamodb_table(mock_aws_context):
    """Verify DynamoDB Hot Table creation."""
    core_aws.create_hot_dynamodb_table()
    
    client = boto3.client("dynamodb")
    table_name = globals_aws.hot_dynamodb_table_name()
    
    resp = client.describe_table(TableName=table_name)
    assert resp["Table"]["TableName"] == table_name
    # Verify KeySchema
    key_schema = resp["Table"]["KeySchema"]
    assert any(k["AttributeName"] == "iotDeviceId" for k in key_schema) # Assuming 'iotDeviceId' is partition key based on convention

def test_create_cold_s3_bucket(mock_aws_context):
    """Verify Cold S3 Bucket creation."""
    core_aws.create_cold_s3_bucket()
    
    client = boto3.client("s3")
    bucket_name = globals_aws.cold_s3_bucket_name()
    
    # Check if bucket exists
    resp = client.head_bucket(Bucket=bucket_name)
    assert resp["ResponseMetadata"]["HTTPStatusCode"] == 200

def test_create_archive_s3_bucket(mock_aws_context):
    """Verify Archive S3 Bucket creation."""
    core_aws.create_archive_s3_bucket()
    
    client = boto3.client("s3")
    bucket_name = globals_aws.archive_s3_bucket_name()
    
    resp = client.head_bucket(Bucket=bucket_name)
    assert resp["ResponseMetadata"]["HTTPStatusCode"] == 200

def test_create_hot_cold_mover_lambda_function(mock_aws_context):
    """Verify Hot-Cold Mover Lambda creation."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_hot_cold_mover_iam_role()
    
    core_aws.create_hot_cold_mover_lambda_function()
    
    client = boto3.client("lambda")
    func_name = globals_aws.hot_cold_mover_lambda_function_name()
    
    resp = client.get_function(FunctionName=func_name)
    assert resp["Configuration"]["FunctionName"] == func_name

def test_destroy_hot_dynamodb_table(mock_aws_context):
    """Verify DynamoDB table destruction."""
    core_aws.create_hot_dynamodb_table()
    core_aws.destroy_hot_dynamodb_table()
    
    client = boto3.client("dynamodb")
    table_name = globals_aws.hot_dynamodb_table_name()
    with pytest.raises(client.exceptions.ResourceNotFoundException):
        client.describe_table(TableName=table_name)

    # Verify Backup Created
    backups = client.list_backups(TableName=table_name)
    assert len(backups["BackupSummaries"]) > 0
    assert backups["BackupSummaries"][-1]["BackupStatus"] == "AVAILABLE"

def test_destroy_cold_s3_bucket(mock_aws_context):
    """Verify Cold S3 bucket destruction."""
    core_aws.create_cold_s3_bucket()
    core_aws.destroy_cold_s3_bucket()
    
    client = boto3.client("s3")
    bucket_name = globals_aws.cold_s3_bucket_name()
    with pytest.raises(client.exceptions.ClientError) as exc:
        client.head_bucket(Bucket=bucket_name)
    assert exc.value.response["Error"]["Code"] == "404"

def test_destroy_archive_s3_bucket(mock_aws_context):
    """Verify Archive S3 bucket destruction."""
    core_aws.create_archive_s3_bucket()
    core_aws.destroy_archive_s3_bucket()
    
    client = boto3.client("s3")
    bucket_name = globals_aws.archive_s3_bucket_name()
    with pytest.raises(client.exceptions.ClientError) as exc:
        client.head_bucket(Bucket=bucket_name)
    assert exc.value.response["Error"]["Code"] == "404"

def test_destroy_hot_cold_mover_components(mock_aws_context):
    """Verify Hot-Cold Mover destruction (Lambda, Role, Rule)."""
    # Setup
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_hot_cold_mover_iam_role()
    core_aws.create_hot_cold_mover_lambda_function()
    core_aws.create_hot_cold_mover_event_rule()
    
    # Destroy
    core_aws.destroy_hot_cold_mover_event_rule()
    core_aws.destroy_hot_cold_mover_lambda_function()
    core_aws.destroy_hot_cold_mover_iam_role()
    
    # Verify Rule Gone
    client_events = boto3.client("events")
    with pytest.raises(client_events.exceptions.ResourceNotFoundException):
        client_events.describe_rule(Name=globals_aws.hot_cold_mover_event_rule_name())
        
    # Verify Function Gone
    client_lambda = boto3.client("lambda")
    with pytest.raises(client_lambda.exceptions.ResourceNotFoundException):
        client_lambda.get_function(FunctionName=globals_aws.hot_cold_mover_lambda_function_name())
        
    # Verify Role Gone
    client_iam = boto3.client("iam")
    with pytest.raises(client_iam.exceptions.NoSuchEntityException):
        client_iam.get_role(RoleName=globals_aws.hot_cold_mover_iam_role_name())
