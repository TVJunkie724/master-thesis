import pytest
import boto3
from moto import mock_aws
import aws.globals_aws as globals_aws
import os

@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"

@pytest.fixture(scope="function")
def mock_aws_context(aws_credentials):
    """
    Start moto services and initialize globals_aws clients.
    """
    with mock_aws():
        # Setup Globals
        globals_aws.globals.config_credentials_aws = {
            "aws_access_key_id": "testing",
            "aws_secret_access_key": "testing",
            "aws_region": "eu-central-1"
        }
        globals_aws.globals.config = {
            "digital_twin_name": "test-twin"
        }
        # Initialize clients (they will use the mocked boto3 because of mock_aws context)
        globals_aws.initialize_aws_clients()
        yield


@pytest.fixture(scope="function")
def mock_provider(aws_credentials):
    """
    Create a mock AWSProvider with mocked boto3 clients for new layer functions.
    """
    from unittest.mock import MagicMock, patch, wraps
    from src.providers.aws.provider import AWSProvider
    from src.providers.aws.naming import AWSNaming
    
    with mock_aws():
        provider = AWSProvider()
        provider._naming = AWSNaming("test-twin")
        provider._initialized = True  # Mark as initialized to bypass property check
        
        # Create real moto clients
        iam_client = boto3.client("iam", region_name="eu-central-1")
        
        # Wrap attach_role_policy to succeed even with AWS managed policies
        original_attach = iam_client.attach_role_policy
        def mock_attach_role_policy(**kwargs):
            try:
                return original_attach(**kwargs)
            except Exception:
                # Silently succeed for AWS managed policies that moto doesn't have
                return {}
        iam_client.attach_role_policy = mock_attach_role_policy
        
        provider._clients = {
            "iam": iam_client,
            "iot": boto3.client("iot", region_name="eu-central-1"),
            "iot_data": MagicMock(),  # moto doesn't fully support iot-data
            "lambda": boto3.client("lambda", region_name="eu-central-1"),
            "stepfunctions": boto3.client("stepfunctions", region_name="eu-central-1"),
            "dynamodb": boto3.client("dynamodb", region_name="eu-central-1"),
            "s3": boto3.client("s3", region_name="eu-central-1"),
            "events": boto3.client("events", region_name="eu-central-1"),
            "apigatewayv2": boto3.client("apigatewayv2", region_name="eu-central-1"),
            "twinmaker": MagicMock(),  # Not supported by moto
            "grafana": MagicMock(),  # Not supported by moto
            "sts": boto3.client("sts", region_name="eu-central-1"),
            "logs": boto3.client("logs", region_name="eu-central-1"),
        }
        yield provider


@pytest.fixture(scope="function")
def mock_config():
    """
    Create a mock ProjectConfig for new layer functions.
    """
    from src.core.context import ProjectConfig
    
    return ProjectConfig(
        digital_twin_name="test-twin",
        hot_storage_size_in_days=7,
        cold_storage_size_in_days=30,
        mode="DEBUG",
        iot_devices=[{"id": "device-1", "name": "temp-sensor", "properties": [{"name": "temp", "dataType": "DOUBLE"}]}],
        events=[],
        hierarchy={},
        providers={
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
        },
        optimization={},
        inter_cloud={},
    )


@pytest.fixture(scope="function")
def project_path(tmp_path):
    """Create a temporary project path with lambda code structure."""
    import shutil
    core_lambda = tmp_path / "lambda_functions" / "core"
    core_lambda.mkdir(parents=True)
    
    # Create minimal lambda function stubs
    for func_name in ["dispatcher", "persister", "event-checker", "hot-to-cold-mover", 
                      "cold-to-archive-mover", "hot-reader", "hot-reader-last-entry"]:
        func_dir = core_lambda / func_name
        func_dir.mkdir()
        (func_dir / "lambda_function.py").write_text("def lambda_handler(event, context): pass")
    
    return str(tmp_path)


@pytest.fixture(autouse=True)
def mock_iam_policies(monkeypatch):
    """
    Mock IAM policy attachment operations since moto doesn't fully support AWS managed policies.
    This patches the IAM client's attach_role_policy to be a no-op.
    """
    from unittest.mock import MagicMock
    original_attach = None
    
    def patched_attach(*args, **kwargs):
        # Silently succeed instead of failing on non-existent managed policies
        return {}
    
    # This will be applied after the mock_aws context sets up moto
    pass  # Actual patching happens in mock_provider where we control the client

