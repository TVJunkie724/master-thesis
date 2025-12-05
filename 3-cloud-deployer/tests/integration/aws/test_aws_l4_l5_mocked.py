import pytest
import boto3
from unittest.mock import MagicMock, patch
import aws.core_deployer_aws as core_aws
import aws.globals_aws as globals_aws
import globals
from botocore.exceptions import ClientError

@patch("aws.globals_aws.aws_twinmaker_client", create=True)
@patch("aws.globals_aws.aws_iam_client", create=True)
@patch("aws.globals_aws.aws_sts_client", create=True)
def test_create_twinmaker_workspace(mock_sts, mock_iam, mock_twinmaker):
    """Verify TwinMaker workspace creation call."""
    mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
    mock_iam.get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test-role"}}
    
    with patch.object(globals, 'config', {"digital_twin_name": "test-twin"}):
        core_aws.create_twinmaker_workspace()
        
        ws_id = globals_aws.twinmaker_workspace_name()
        mock_twinmaker.create_workspace.assert_called()

def test_create_twinmaker_iam_role(mock_aws_context):
    """Verify TwinMaker IAM role creation."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_twinmaker_iam_role()
    
    client = boto3.client("iam")
    role_name = globals_aws.twinmaker_iam_role_name()
    assert client.get_role(RoleName=role_name)

@patch("aws.core_deployer_aws.util_aws.get_grafana_workspace_id_by_name")
def test_create_twinmaker_s3_bucket(mock_get_grafana_id, mock_aws_context):
    """Verify TwinMaker S3 bucket creation (and CORS configuration)."""
    mock_get_grafana_id.return_value = "g-mock-id"
    core_aws.create_twinmaker_s3_bucket()
    
    client = boto3.client("s3")
    bucket_name = globals_aws.twinmaker_s3_bucket_name()
    
    # Check bucket exists
    client.head_bucket(Bucket=bucket_name)
    
    # Check CORS (add_cors_to_twinmaker_s3_bucket)
    core_aws.add_cors_to_twinmaker_s3_bucket()
    cors = client.get_bucket_cors(Bucket=bucket_name)
    assert len(cors["CORSRules"]) > 0

@patch("aws.core_deployer_aws.util_aws.get_grafana_workspace_id_by_name")
@patch("aws.globals_aws.aws_twinmaker_client", create=True)
@patch("aws.globals_aws.aws_iam_client", create=True)
@patch("aws.globals_aws.aws_sts_client", create=True)
@patch("time.sleep")
def test_destroy_twinmaker_workspace(mock_sleep, mock_sts, mock_iam, mock_twinmaker, mock_get_grafana_id):
    """Verify TwinMaker workspace destruction."""
    mock_get_grafana_id.return_value = "g-mock-id"
    
    exception = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "get_workspace"
    )
    mock_twinmaker.get_workspace.side_effect = [
        {"workspace": {"status": "DELETING"}},
        exception
    ]
    
    core_aws.destroy_twinmaker_workspace()
    
    mock_twinmaker.delete_workspace.assert_called()

def test_destroy_twinmaker_iam_role(mock_aws_context):
    """Verify TwinMaker IAM role destruction."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_twinmaker_iam_role()
    
    core_aws.destroy_twinmaker_iam_role()
    
    client = boto3.client("iam")
    with pytest.raises(client.exceptions.NoSuchEntityException):
        client.get_role(RoleName=globals_aws.twinmaker_iam_role_name())

def test_destroy_twinmaker_s3_bucket(mock_aws_context):
    """Verify TwinMaker S3 bucket destruction."""
    core_aws.create_twinmaker_s3_bucket()
    core_aws.destroy_twinmaker_s3_bucket()
    
    client = boto3.client("s3")
    bucket_name = globals_aws.twinmaker_s3_bucket_name()
    
    with pytest.raises(client.exceptions.ClientError) as exc:
        client.head_bucket(Bucket=bucket_name)
    assert exc.value.response["Error"]["Code"] == "404"


# --- Grafana Tests ---

@patch("aws.globals_aws.aws_grafana_client", create=True)
@patch("aws.globals_aws.aws_iam_client", create=True)
@patch("time.sleep")
def test_create_grafana_workspace(mock_sleep, mock_iam, mock_grafana):
    """Verify Grafana workspace creation."""
    mock_iam.get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/grafana-role"}}
    mock_grafana.create_workspace.return_value = {"workspace": {"id": "g-123"}}
    mock_grafana.describe_workspace.return_value = {"workspace": {"status": "ACTIVE"}}
    
    with patch.object(globals, 'config', {"digital_twin_name": "test-twin"}):
        core_aws.create_grafana_workspace()
        
        mock_grafana.create_workspace.assert_called()

def test_create_grafana_iam_role(mock_aws_context):
    """Verify Grafana IAM role creation."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_grafana_iam_role()
    
    client = boto3.client("iam")
    role_name = globals_aws.grafana_iam_role_name()
    assert client.get_role(RoleName=role_name)

@patch("aws.core_deployer_aws.util_aws.get_grafana_workspace_id_by_name")
@patch("aws.globals_aws.aws_grafana_client", create=True)
@patch("time.sleep")
def test_destroy_grafana_workspace(mock_sleep, mock_grafana, mock_get_id):
    """Verify Grafana workspace destruction."""
    mock_get_id.return_value = "g-123"
    
    exception = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "describe_workspace"
    )
    mock_grafana.describe_workspace.side_effect = [
        {"workspace": {"status": "DELETING"}},
        exception
    ]
    
    core_aws.destroy_grafana_workspace()
    
    mock_grafana.delete_workspace.assert_called_with(workspaceId="g-123")

def test_destroy_grafana_iam_role(mock_aws_context):
    """Verify Grafana IAM role destruction."""
    globals_aws.aws_iam_client.attach_role_policy = MagicMock()
    core_aws.create_grafana_iam_role()
    
    core_aws.destroy_grafana_iam_role()
    
    client = boto3.client("iam")
    with pytest.raises(client.exceptions.NoSuchEntityException):
        client.get_role(RoleName=globals_aws.grafana_iam_role_name())
