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
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture(scope="function")
def mock_aws_context(aws_credentials):
    """
    Start moto services and initialize globals_aws clients.
    """
    with mock_aws():
        # Initialize clients (they will use the mocked boto3 because of mock_aws context)
        globals_aws.initialize_aws_clients()
        yield
