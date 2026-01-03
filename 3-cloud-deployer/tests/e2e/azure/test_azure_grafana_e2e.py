"""
Azure Grafana E2E Test

Pytest-compatible E2E test for Azure Managed Grafana with Entra ID user.
This test:
1. Creates a resource group for Grafana
2. Creates an Azure Managed Grafana workspace
3. Creates or finds an admin user in Entra ID
4. Assigns the user as Grafana admin
5. Destroys all resources

Prerequisites:
- Azure credentials in config_credentials.json
- platform_user_email set for the admin user

Usage:
    # Run via the E2E helper script (saves full output)
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/run_e2e_test.py azure-grafana
    
    # Or directly with pytest (not recommended - truncates output)
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python -m pytest tests/e2e/azure/test_azure_grafana_e2e.py -v -s

Note: Terraform state files remain in tests/e2e/azure_grafana_test/ for debugging.
"""

import json
import os
import pytest
import subprocess
from pathlib import Path


# Directory where this test file lives
TEST_DIR = Path(__file__).parent
TERRAFORM_DIR = TEST_DIR.parent / "azure_grafana_test"
DEPLOYER_ROOT = TEST_DIR.parent.parent.parent


def load_azure_credentials() -> dict:
    """Load Azure credentials from config_credentials.json."""
    creds_paths = [
        DEPLOYER_ROOT / "config_credentials.json",
        Path("/app/config_credentials.json"),
        Path("/app/upload/template/config_credentials.json"),
    ]
    
    for creds_path in creds_paths:
        if creds_path.exists():
            with open(creds_path) as f:
                creds = json.load(f)
            
            azure = creds.get("azure", {})
            if not azure.get("azure_subscription_id"):
                continue
            
            return {
                "azure_subscription_id": azure.get("azure_subscription_id"),
                "azure_tenant_id": azure.get("azure_tenant_id"),
                "azure_client_id": azure.get("azure_client_id"),
                "azure_client_secret": azure.get("azure_client_secret"),
                "azure_region": azure.get("azure_region", "westeurope"),
            }
    
    pytest.skip("Azure credentials not found in config_credentials.json")


def load_user_config() -> dict:
    """Load platform user config from config_user.json."""
    config_paths = [
        DEPLOYER_ROOT / "config_user.json",
        Path("/app/config_user.json"),
        Path("/app/upload/template/config_user.json"),
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            with open(config_path) as f:
                user = json.load(f)
            
            if user.get("admin_email"):
                return {
                    "platform_user_email": user.get("admin_email"),
                    "platform_user_first_name": user.get("admin_first_name", "Platform"),
                    "platform_user_last_name": user.get("admin_last_name", "Admin"),
                }
    
    # Use a test email if not configured
    return {
        "platform_user_email": "platform-e2e-test@example.com",
        "platform_user_first_name": "E2E",
        "platform_user_last_name": "Test",
    }


class TestAzureGrafanaE2E:
    """E2E tests for Azure Managed Grafana with Entra ID user."""
    
    @pytest.fixture(scope="class")
    def tfvars(self):
        """Generate tfvars.json with credentials in the terraform directory."""
        azure_creds = load_azure_credentials()
        user_config = load_user_config()
        
        tfvars = {
            **azure_creds,
            **user_config,
            "test_name_suffix": "e2e-pytest",
        }
        
        # Write tfvars to the terraform directory (state stays in same folder)
        tfvars_path = TERRAFORM_DIR / "test.tfvars.json"
        with open(tfvars_path, "w") as f:
            json.dump(tfvars, f, indent=2)
        
        yield tfvars_path
        
        # Cleanup tfvars file (contains secrets)
        if tfvars_path.exists():
            tfvars_path.unlink()
    
    def test_01_terraform_init(self, tfvars):
        """Test Terraform initialization."""
        print(f"\n📁 Terraform directory: {TERRAFORM_DIR}")
        
        result = subprocess.run(
            ["terraform", "init", "-no-color"],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform init failed: {result.stderr}")
        
        assert (TERRAFORM_DIR / ".terraform").exists()
    
    def test_02_terraform_validate(self, tfvars):
        """Test Terraform validation."""
        result = subprocess.run(
            ["terraform", "validate", "-no-color"],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform validate failed: {result.stderr}")
    
    def test_03_terraform_plan(self, tfvars):
        """Test Terraform plan - validates Grafana and user provisioning logic."""
        result = subprocess.run(
            [
                "terraform", "plan",
                "-no-color",
                f"-var-file={tfvars}",
                "-out=plan.tfplan",
            ],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            
            # Check for specific errors
            if "azuread" in result.stderr.lower():
                pytest.fail(
                    "Entra ID access failed! Check Azure AD permissions.\n"
                    f"Error: {result.stderr}"
                )
            
            pytest.fail(f"terraform plan failed: {result.stderr}")
        
        # Verify plan file was created
        assert (TERRAFORM_DIR / "plan.tfplan").exists()
    
    def test_04_terraform_apply(self, tfvars):
        """Test Terraform apply - creates Grafana workspace and admin user."""
        result = subprocess.run(
            [
                "terraform", "apply",
                "-no-color",
                "-auto-approve",
                "plan.tfplan",
            ],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=600,  # Grafana creation can take 5+ minutes
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform apply failed: {result.stderr}")
        
        # Verify state was created
        assert (TERRAFORM_DIR / "terraform.tfstate").exists()
    
    def test_05_verify_outputs(self):
        """Verify Terraform outputs."""
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            pytest.fail(f"terraform output failed: {result.stderr}")
        
        outputs = json.loads(result.stdout)
        
        # Verify Grafana was created
        assert outputs.get("grafana_endpoint", {}).get("value"), \
            "Grafana endpoint should exist"
        
        # Verify admin object ID exists (user found or created)
        admin_object_id = outputs.get("grafana_admin_object_id", {}).get("value")
        user_found = outputs.get("user_exists_in_tenant", {}).get("value")
        user_created = outputs.get("user_created", {}).get("value")
        domain_verified = outputs.get("domain_verified", {}).get("value")
        
        # Either user must exist or have been created (if domain verified)
        if not admin_object_id:
            if not domain_verified:
                pytest.skip("User could not be created - email domain not verified in tenant")
            pytest.fail("Grafana admin user should be found or created")
        
        # Print summary
        print("\n" + "=" * 60)
        print(outputs.get("test_summary", {}).get("value", ""))
        print("=" * 60)
    
    def test_06_terraform_destroy(self, tfvars):
        """Clean up all resources."""
        result = subprocess.run(
            [
                "terraform", "destroy",
                "-no-color",
                "-auto-approve",
                f"-var-file={tfvars}",
            ],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=600,
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            # Don't fail the test for destroy errors, just warn
            print("⚠️ Warning: destroy had errors, resources may need manual cleanup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
