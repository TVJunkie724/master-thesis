"""
Azure Logic App E2E Test

Pytest-compatible E2E test for Azure Logic App workflow creation.
This test:
1. Creates Resource Group
2. Creates Logic App Workflow
3. Applies workflow definition via ARM template
4. Verifies outputs
5. Destroys all resources

This test validates the FIX for the bug where Logic App definitions
weren't being uploaded (workflow appeared empty in portal).

Prerequisites:
- Azure credentials in config_credentials.json

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/run_e2e_test.py azure-logicapp
"""

import json
import subprocess
import time
import pytest
from pathlib import Path


# Directory where this test file lives
TEST_DIR = Path(__file__).parent
TERRAFORM_SOURCE_DIR = TEST_DIR.parent / "azure_logicapp_test"
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


class TestAzureLogicAppE2E:
    """E2E tests for Azure Logic App."""
    
    @pytest.fixture(scope="class")
    def terraform_workspace(self):
        """Use the persistent azure_logicapp_test folder for Terraform state."""
        workspace_path = TERRAFORM_SOURCE_DIR
        
        if not workspace_path.exists():
            pytest.fail(f"Terraform source dir not found: {workspace_path}")
        
        if not (workspace_path / "main.tf").exists():
            pytest.fail(f"main.tf not found in: {workspace_path}")
        
        print(f"\n📁 Using persistent workspace: {workspace_path}")
        
        # PRE-CLEANUP: Destroy any existing resources from previous failed runs
        tfvars_path = workspace_path / "test.tfvars.json"
        if (workspace_path / ".terraform").exists() and tfvars_path.exists():
            print("🧹 Pre-cleanup: Destroying any resources from previous run...")
            subprocess.run(
                ["terraform", "destroy", "-auto-approve", f"-var-file={tfvars_path}"],
                cwd=workspace_path,
                capture_output=True,
                timeout=600,
            )
            # Clear state to start fresh
            state_file = workspace_path / "terraform.tfstate"
            if state_file.exists():
                state_file.unlink()
            backup_file = workspace_path / "terraform.tfstate.backup"
            if backup_file.exists():
                backup_file.unlink()
            print("✅ Pre-cleanup complete")
        
        yield workspace_path
    
    @pytest.fixture(scope="class")
    def tfvars(self, terraform_workspace):
        """Generate tfvars.json with credentials and unique naming."""
        azure_creds = load_azure_credentials()
        
        # Use timestamp for unique naming to avoid conflicts
        timestamp = int(time.time()) % 100000
        unique_suffix = f"e2e-{timestamp}"
        
        tfvars = {
            **azure_creds,
            "test_name_suffix": unique_suffix,
            "workflow_definition_file": "",  # Use default definition
        }
        
        print(f"📝 Using unique name suffix: {unique_suffix}")
        
        tfvars_path = terraform_workspace / "test.tfvars.json"
        with open(tfvars_path, "w") as f:
            json.dump(tfvars, f, indent=2)
        
        return tfvars_path
    
    def test_01_terraform_init(self, terraform_workspace, tfvars):
        """Test Terraform initialization."""
        print(f"\n📁 Workspace: {terraform_workspace}")
        
        result = subprocess.run(
            ["terraform", "init", "-no-color"],
            cwd=terraform_workspace,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform init failed: {result.stderr}")
        
        assert (terraform_workspace / ".terraform").exists()
    
    def test_02_terraform_validate(self, terraform_workspace, tfvars):
        """Test Terraform validation."""
        result = subprocess.run(
            ["terraform", "validate", "-no-color"],
            cwd=terraform_workspace,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform validate failed: {result.stderr}")
    
    def test_03_terraform_plan(self, terraform_workspace, tfvars):
        """Test Terraform plan."""
        result = subprocess.run(
            [
                "terraform", "plan",
                "-no-color",
                f"-var-file={tfvars}",
                "-out=plan.tfplan",
            ],
            cwd=terraform_workspace,
            capture_output=True,
            text=True,
            timeout=180,
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform plan failed: {result.stderr}")
        
        assert (terraform_workspace / "plan.tfplan").exists()
    
    def test_04_terraform_apply(self, terraform_workspace, tfvars):
        """Test Terraform apply - creates Logic App with workflow definition."""
        result = subprocess.run(
            [
                "terraform", "apply",
                "-no-color",
                "-auto-approve",
                "plan.tfplan",
            ],
            cwd=terraform_workspace,
            capture_output=True,
            text=True,
            timeout=600,
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform apply failed: {result.stderr}")
        
        assert (terraform_workspace / "terraform.tfstate").exists()
    
    def test_05_verify_outputs(self, terraform_workspace):
        """Verify Terraform outputs."""
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=terraform_workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            pytest.fail(f"terraform output failed: {result.stderr}")
        
        outputs = json.loads(result.stdout)
        
        # Verify Logic App was created
        assert outputs.get("logic_app_id", {}).get("value"), \
            "Logic App ID should exist"
        
        # Verify workflow definition was applied
        assert outputs.get("workflow_definition_applied", {}).get("value") == True, \
            "Workflow definition should be applied via ARM template"
        
        # Print summary
        print("\n" + "=" * 60)
        print(outputs.get("test_summary", {}).get("value", ""))
        print("=" * 60)
    
    def test_06_terraform_destroy(self, terraform_workspace, tfvars):
        """Clean up all resources."""
        result = subprocess.run(
            [
                "terraform", "destroy",
                "-no-color",
                "-auto-approve",
                f"-var-file={tfvars}",
            ],
            cwd=terraform_workspace,
            capture_output=True,
            text=True,
            timeout=600,
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            print("⚠️ Warning: destroy had errors, resources may need manual cleanup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
