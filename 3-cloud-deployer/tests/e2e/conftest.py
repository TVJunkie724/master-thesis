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
    """
    Fixed, deterministic ID for E2E test runs.
    
    Using a consistent ID ensures:
    - Idempotent resource naming across test runs
    - Skip-if-exists logic can reuse existing resources
    - Reduced costs (no duplicate resources created)
    - Easy resumption after partial failures
    
    The ID is kept short to comply with Azure naming limits.
    """
    return "twin2c-e2e"


@pytest.fixture(scope="session")
def template_project_path():
    """Path to the template project."""
    return Path(__file__).parent.parent.parent / "upload" / "template"


@pytest.fixture(scope="session")
def terraform_e2e_test_id():
    """
    Fixed, deterministic ID for Terraform E2E test runs.
    
    Using a consistent ID ensures:
    - Idempotent resource naming across test runs
    - Skip-if-exists logic can reuse existing resources
    - Reduced costs (no duplicate resources created)
    - Easy resumption after partial failures
    
    The ID is kept short to comply with Azure naming limits.
    """
    return "tf-e2e-az2"


@pytest.fixture(scope="session")
def terraform_e2e_project_path(template_project_path, terraform_e2e_test_id, tmp_path_factory):
    """
    Create a unique temporary E2E test project for Terraform deployment.
    
    Each test run gets a unique project name to avoid Terraform state conflicts.
    """
    # Create temp directory for E2E project
    temp_dir = tmp_path_factory.mktemp("terraform_e2e")
    project_path = temp_dir / terraform_e2e_test_id
    
    # Copy template project
    shutil.copytree(template_project_path, project_path)
    
    # Modify config.json with unique twin name
    config_path = project_path / "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    config["digital_twin_name"] = terraform_e2e_test_id
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
        "layer_5_provider": "azure"  # Using AzureRM 4.x with Grafana v11
    }
    with open(providers_path, "w") as f:
        json.dump(providers, f, indent=2)
    
    print(f"\n[TERRAFORM E2E] Created unique test project: {project_path}")
    print(f"[TERRAFORM E2E] Digital twin name: {terraform_e2e_test_id}")
    
    yield str(project_path)
    
    # Cleanup temp directory
    print(f"\n[TERRAFORM E2E] Cleaning up temp project: {project_path}")
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
def e2e_failure_project_path(template_project_path, e2e_test_id, tmp_path_factory):
    """
    Create a temporary E2E test project with INVALID IoT Hub region.
    
    This project is designed to trigger a deployment failure during L1
    to test the cleanup/destroy functionality.
    
    The invalid region 'invalid-region-xyz' will cause IoT Hub creation to fail
    with a clear error message, allowing us to verify:
    - Setup layer deploys successfully
    - L1 fails during IoT Hub creation
    - Cleanup runs and destroys all resources
    """
    # Create temp directory for failure test project
    temp_dir = tmp_path_factory.mktemp("e2e_failure_project")
    failure_test_id = f"fail-{e2e_test_id}"
    project_path = temp_dir / failure_test_id
    
    # Copy template project
    shutil.copytree(template_project_path, project_path)
    
    # Modify config.json with unique twin name
    config_path = project_path / "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    config["digital_twin_name"] = failure_test_id
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
    
    # Modify config_credentials.json with INVALID IoT Hub region
    creds_path = project_path / "config_credentials.json"
    if creds_path.exists():
        with open(creds_path, "r") as f:
            credentials = json.load(f)
        
        if "azure" in credentials:
            # Keep valid credentials for authentication, but use invalid IoT Hub region
            credentials["azure"]["azure_region_iothub"] = "invalid-region-xyz"
            
            with open(creds_path, "w") as f:
                json.dump(credentials, f, indent=2)
            
            print(f"\n[E2E FAILURE] Created failure test project: {project_path}")
            print(f"[E2E FAILURE] Digital twin name: {failure_test_id}")
            print(f"[E2E FAILURE] Invalid IoT Hub region: invalid-region-xyz")
    
    yield str(project_path)
    
    # Cleanup temp directory
    print(f"\n[E2E FAILURE] Cleaning up temp project: {project_path}")



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


@pytest.fixture(scope="session")
def gcp_terraform_e2e_test_id():
    """
    Fixed, deterministic ID for GCP Terraform E2E test runs.
    """
    return "tf-e2e-gcp"


@pytest.fixture(scope="session")
def gcp_terraform_e2e_project_path(template_project_path, gcp_terraform_e2e_test_id, tmp_path_factory):
    """
    Create a unique temporary E2E test project for GCP Terraform deployment.
    
    Configures all layers to use GCP (except L4/L5 which are disabled).
    """
    # Create temp directory for E2E project
    temp_dir = tmp_path_factory.mktemp("gcp_terraform_e2e")
    project_path = temp_dir / gcp_terraform_e2e_test_id
    
    # Copy template project
    shutil.copytree(template_project_path, project_path)
    
    # Modify config.json with unique twin name
    config_path = project_path / "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    config["digital_twin_name"] = gcp_terraform_e2e_test_id
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    # Modify config_providers.json to all-GCP (L1-L3 only)
    providers_path = project_path / "config_providers.json"
    providers = {
        "layer_1_provider": "google",
        "layer_2_provider": "google",
        "layer_3_hot_provider": "google",
        "layer_3_cold_provider": "google",
        "layer_3_archive_provider": "google",
        "layer_4_provider": "",  # GCP has no managed Digital Twin
        "layer_5_provider": ""   # GCP has no managed Grafana
    }
    with open(providers_path, "w") as f:
        json.dump(providers, f, indent=2)
    
    print(f"\n[GCP TERRAFORM E2E] Created unique test project: {project_path}")
    print(f"[GCP TERRAFORM E2E] Digital twin name: {gcp_terraform_e2e_test_id}")
    print(f"[GCP TERRAFORM E2E] L4/L5 disabled (no GCP managed services)")
    
    yield str(project_path)
    
    # Cleanup temp directory
    print(f"\n[GCP TERRAFORM E2E] Cleaning up temp project: {project_path}")


@pytest.fixture(scope="session")
def gcp_credentials(template_project_path):
    """
    Load GCP credentials from config_credentials.json.
    
    Falls back to environment variables if file not found.
    """
    # First try to load from config_credentials.json
    creds_path = template_project_path / "config_credentials.json"
    
    if creds_path.exists():
        with open(creds_path, "r") as f:
            all_creds = json.load(f)
        
        gcp_creds = all_creds.get("gcp", {})
        
        # Check for credentials file or project_id
        has_creds_file = gcp_creds.get("gcp_credentials_file")
        has_project = gcp_creds.get("gcp_project_id") or gcp_creds.get("gcp_billing_account")
        
        if has_creds_file and has_project:
            print("[GCP E2E] Using credentials from config_credentials.json")
            
            # Set environment variable for GCP SDK
            if has_creds_file and os.path.exists(has_creds_file):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = has_creds_file
            
            return {
                "auth_type": "service_account",
                "project_id": gcp_creds.get("gcp_project_id", ""),
                "region": gcp_creds.get("gcp_region", "europe-west1"),
                "credentials_file": has_creds_file
            }
    
    # Fallback: Check for environment variables
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("[GCP E2E] Using credentials from GOOGLE_APPLICATION_CREDENTIALS")
        return {
            "auth_type": "service_account",
            "credentials_file": os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        }
    
    # Last resort: Try Application Default Credentials
    try:
        from google.auth import default
        credentials, project = default()
        print("[GCP E2E] Using Application Default Credentials")
        return {
            "auth_type": "adc",
            "project_id": project
        }
    except Exception:
        pytest.skip(
            f"GCP credentials not configured. "
            f"Please set credentials in config_credentials.json or GOOGLE_APPLICATION_CREDENTIALS."
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


@pytest.fixture(scope="session")
def aws_credentials(template_project_path):
    """
    Load AWS credentials from config_credentials.json.
    
    Falls back to environment variables if file not found.
    """
    # First try to load from config_credentials.json
    creds_path = template_project_path / "config_credentials.json"
    
    if creds_path.exists():
        with open(creds_path, "r") as f:
            all_creds = json.load(f)
        
        aws_creds = all_creds.get("aws", {})
        
        if aws_creds.get("aws_access_key_id") and aws_creds.get("aws_secret_access_key"):
            print("[AWS E2E] Using credentials from config_credentials.json")
            
            # Set environment variables for AWS SDK and Terraform
            os.environ["AWS_ACCESS_KEY_ID"] = aws_creds["aws_access_key_id"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = aws_creds["aws_secret_access_key"]
            os.environ["AWS_REGION"] = aws_creds.get("aws_region", "eu-west-1")
            
            return {
                "auth_type": "access_key",
                "region": aws_creds.get("aws_region", "eu-west-1"),
                "access_key_id": aws_creds["aws_access_key_id"],
                "secret_access_key": aws_creds["aws_secret_access_key"],
            }
    
    # Fallback: Check for environment variables
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        print("[AWS E2E] Using AWS credentials from environment variables")
        return {
            "auth_type": "access_key",
            "region": os.environ.get("AWS_REGION", "eu-west-1"),
        }
    
    pytest.skip(
        "AWS credentials not configured. "
        "Please set credentials in config_credentials.json or environment variables."
    )


@pytest.fixture(scope="session")
def aws_terraform_e2e_test_id():
    """
    Fixed, deterministic ID for AWS Terraform E2E test runs.
    
    Using a consistent ID ensures:
    - Idempotent resource naming across test runs
    - Skip-if-exists logic can reuse existing resources
    - Reduced costs (no duplicate resources created)
    - Easy resumption after partial failures
    
    The ID is kept short to comply with AWS naming limits.
    """
    return "tf-e2e-aws"


@pytest.fixture(scope="session")
def aws_terraform_e2e_project_path(template_project_path, aws_terraform_e2e_test_id, tmp_path_factory):
    """
    Create a unique temporary E2E test project for AWS Terraform deployment.
    
    Configures all layers to use AWS.
    """
    # Create temp directory for E2E project
    temp_dir = tmp_path_factory.mktemp("aws_terraform_e2e")
    project_path = temp_dir / aws_terraform_e2e_test_id
    
    # Copy template project
    shutil.copytree(template_project_path, project_path)
    
    # Modify config.json with unique twin name
    config_path = project_path / "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    config["digital_twin_name"] = aws_terraform_e2e_test_id
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    # Modify config_providers.json to all-AWS
    providers_path = project_path / "config_providers.json"
    providers = {
        "layer_1_provider": "aws",
        "layer_2_provider": "aws",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "aws",
        "layer_3_archive_provider": "aws",
        "layer_4_provider": "aws",
        "layer_5_provider": "aws"
    }
    with open(providers_path, "w") as f:
        json.dump(providers, f, indent=2)
    
    print(f"\n[AWS TERRAFORM E2E] Created unique test project: {project_path}")
    print(f"[AWS TERRAFORM E2E] Digital twin name: {aws_terraform_e2e_test_id}")
    
    yield str(project_path)
    
    # Cleanup temp directory
    print(f"\n[AWS TERRAFORM E2E] Cleaning up temp project: {project_path}")
