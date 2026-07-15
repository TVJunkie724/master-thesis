import os
import pytest
import sys


def pytest_ignore_collect(collection_path, config):
    """Keep every live-cloud E2E module opt-in, even for `pytest tests`."""
    del config
    if "e2e" not in collection_path.parts:
        return False
    return os.environ.get("RUN_E2E_TESTS") != "1"

# Set PYTHONPATH to include src and root if not already there
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture(scope="function", autouse=True)
def mock_env_vars(request, monkeypatch):
    """Set mock environment variables to prevent accidental cloud calls.
    
    Note: This fixture is skipped for E2E tests which need real credentials.
    """
    # Skip for E2E tests - they need real credentials for actual cloud operations
    if "e2e" in str(request.fspath):
        return
    
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    monkeypatch.setenv("REGION", "eu-central-1")

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
def mock_sleep(request, monkeypatch):
    """Skip time.sleep calls to speed up unit tests.
    
    Note: This fixture is skipped for E2E tests which need real timing.
    """
    # Skip for E2E tests - they need real sleep for cloud propagation
    if "e2e" in str(request.fspath):
        return
    
    monkeypatch.setattr("time.sleep", lambda x: None)
