import os
import pytest
from unittest.mock import MagicMock
import sys
import json

# Set PYTHONPATH to include src and root if not already there
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture(scope="function", autouse=True)
def mock_env_vars():
    """Set mock environment variables to prevent accidental cloud calls."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"
    os.environ["REGION"] = "eu-central-1"

@pytest.fixture(scope="function")
def mock_project_config():
    """
    Create a mock ProjectConfig for tests.
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
            "layer_3_cold_provider": "aws",
            "layer_3_archive_provider": "aws",
            "layer_4_provider": "aws",
            "layer_5_provider": "aws"
        },
        optimization={},
        inter_cloud={}
    )

@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """Skip time.sleep calls to speed up tests."""
    monkeypatch.setattr("time.sleep", lambda x: None)
