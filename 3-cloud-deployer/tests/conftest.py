import os
import pytest
from unittest.mock import MagicMock
import sys
import json

# Set PYTHONPATH to include src and root if not already there
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import globals after setting path
import globals

@pytest.fixture(scope="function", autouse=True)
def mock_env_vars():
    """Set mock environment variables to prevent accidental cloud calls."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"
    os.environ["REGION"] = "eu-central-1"

@pytest.fixture(scope="function", autouse=True)
def mock_globals(monkeypatch):
    """
    Populate globals.py with test configuration.
    This fixture runs automatically for every test.
    """
    test_config = {
        "digital_twin_name": "test-twin",
        "layer_3_hot_to_cold_interval_days": 30,
        "layer_3_cold_to_archive_interval_days": 90,
        "mode": "DEBUG"
    }

    test_iot_devices = [
        {"id": "device-1", "name": "temp-sensor", "properties": [{"name": "temp", "dataType": "DOUBLE"}]}
    ]

    test_events = []

    test_providers = {
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "aws",
        "layer_3_archive_provider": "aws",
        "layer_4_provider": "aws",
        "layer_5_provider": "aws"
    }
    
    test_credentials_aws = {
        "aws_access_key_id": "testing",
        "aws_secret_access_key": "testing",
        "aws_region": "eu-central-1"
    }

    monkeypatch.setattr(globals, "config", test_config)
    monkeypatch.setattr(globals, "config_iot_devices", test_iot_devices)
    monkeypatch.setattr(globals, "config_events", test_events)
    monkeypatch.setattr(globals, "config_providers", test_providers)
    
    # Mock credentials directly
    monkeypatch.setattr(globals, "config_credentials_aws", test_credentials_aws)

    # Patch initialize_all to do nothing since we manually populated globals
    monkeypatch.setattr(globals, "initialize_all", lambda: None)

@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """Skip time.sleep calls to speed up tests."""
    monkeypatch.setattr("time.sleep", lambda x: None)
