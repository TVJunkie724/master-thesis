"""
E2E Test Fixtures.

Provides fixtures for end-to-end testing of cloud deployments.
These tests deploy REAL resources and incur costs.
"""
import pytest
import os
import sys
import shutil
import json
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "live: marks tests as live E2E tests that deploy real resources"
    )


@pytest.fixture(scope="session")
def e2e_test_id():
    """Generate a unique ID for this E2E test run."""
    return f"e2e-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def template_project_path():
    """Path to the template project."""
    return Path(__file__).parent.parent.parent / "upload" / "template"


@pytest.fixture(scope="session")
def e2e_project_path(template_project_path, e2e_test_id, tmp_path_factory):
    """
    Create a temporary E2E test project from template.
    
    Modifies config_providers.json to use all-Azure for single-cloud test.
    """
    # Create temp directory for E2E project
    temp_dir = tmp_path_factory.mktemp("e2e_project")
    project_path = temp_dir / e2e_test_id
    
    # Copy template project
    shutil.copytree(template_project_path, project_path)
    
    # Modify config.json with unique twin name
    config_path = project_path / "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    config["digital_twin_name"] = e2e_test_id
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    # Modify config_providers.json to all-Azure
    providers_path = project_path / "config_providers.json"
    providers = {
        "layer_1_provider": "azure",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "azure",
        "layer_3_cold_provider": "azure",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "azure",
        "layer_5_provider": "azure"
    }
    with open(providers_path, "w") as f:
        json.dump(providers, f, indent=2)
    
    print(f"\n[E2E] Created test project: {project_path}")
    print(f"[E2E] Digital twin name: {e2e_test_id}")
    
    yield str(project_path)
    
    # Cleanup temp directory
    print(f"\n[E2E] Cleaning up temp project: {project_path}")


@pytest.fixture(scope="session")
def azure_credentials(template_project_path):
    """
    Load Azure credentials from config_credentials.json.
    
    Falls back to environment variables if file not found.
    """
    # First try to load from config_credentials.json
    creds_path = template_project_path / "config_credentials.json"
    
    if creds_path.exists():
        with open(creds_path, "r") as f:
            all_creds = json.load(f)
        
        azure_creds = all_creds.get("azure", {})
        
        if azure_creds.get("azure_subscription_id") and azure_creds.get("azure_client_id"):
            print("[E2E] Using credentials from config_credentials.json")
            
            # Set environment variables for Azure SDK
            os.environ["AZURE_SUBSCRIPTION_ID"] = azure_creds["azure_subscription_id"]
            os.environ["AZURE_CLIENT_ID"] = azure_creds["azure_client_id"]
            os.environ["AZURE_CLIENT_SECRET"] = azure_creds["azure_client_secret"]
            os.environ["AZURE_TENANT_ID"] = azure_creds["azure_tenant_id"]
            
            return {
                "auth_type": "service_principal",
                "subscription_id": azure_creds["azure_subscription_id"],
                "tenant_id": azure_creds["azure_tenant_id"],
                "client_id": azure_creds["azure_client_id"],
                "region": azure_creds.get("azure_region", "westeurope")
            }
    
    # Fallback: Check for environment variables
    sp_vars = [
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_TENANT_ID", 
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET"
    ]
    
    missing = [var for var in sp_vars if not os.environ.get(var)]
    
    if not missing:
        print("[E2E] Using Service Principal from environment variables")
        return {
            "auth_type": "service_principal",
            "subscription_id": os.environ["AZURE_SUBSCRIPTION_ID"],
            "tenant_id": os.environ["AZURE_TENANT_ID"],
            "client_id": os.environ["AZURE_CLIENT_ID"]
        }
    
    # Last resort: Try Azure CLI
    try:
        from azure.identity import DefaultAzureCredential
        cred = DefaultAzureCredential()
        cred.get_token("https://management.azure.com/.default")
        print("[E2E] Using Azure CLI credentials")
        return {"auth_type": "cli"}
    except Exception:
        pytest.skip(
            f"Azure credentials not configured. "
            f"Please set credentials in config_credentials.json or environment variables."
        )


@pytest.fixture(scope="class")
def deployment_context(request, e2e_project_path, azure_credentials):
    """
    Create deployment context for E2E tests.
    
    Sets up the context but does NOT deploy - that's done in the test class.
    """
    from src.core.factory import create_context
    from src.core.config_loader import load_project_config
    from pathlib import Path
    
    # Load project config
    config = load_project_config(Path(e2e_project_path))
    
    # Create context
    context = create_context(config, e2e_project_path)
    
    return context
