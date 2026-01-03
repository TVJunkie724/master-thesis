"""
AWS Grafana E2E Test

Pytest-compatible E2E test for AWS Managed Grafana with IAM Identity Center.
This test:
1. Validates SSO detection using the aws_sso_region configuration
2. Creates a minimal Grafana workspace
3. Creates an admin user in IAM Identity Center
4. Assigns the user as Grafana admin
5. Destroys all resources

Prerequisites:
- AWS credentials in config_credentials.json
- aws_sso_region configured (if SSO is in different region)
- platform_user_email set for the admin user

Usage:
    # Run via the E2E helper script (saves full output)
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/run_e2e_test.py --provider aws-grafana
    
    # Or directly with pytest (not recommended - truncates output)
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python -m pytest tests/e2e/aws/test_aws_grafana_e2e.py -v -s
"""

import json
import os
import pytest
import shutil
import subprocess
import tempfile
from pathlib import Path


# Directory where this test file lives
TEST_DIR = Path(__file__).parent
TERRAFORM_SOURCE_DIR = TEST_DIR.parent / "aws_grafana_test"
DEPLOYER_ROOT = TEST_DIR.parent.parent.parent


def load_aws_credentials() -> dict:
    """Load AWS credentials from config_credentials.json."""
    creds_paths = [
        DEPLOYER_ROOT / "config_credentials.json",
        Path("/app/config_credentials.json"),
        Path("/app/upload/template/config_credentials.json"),
    ]
    
    for creds_path in creds_paths:
        if creds_path.exists():
            with open(creds_path) as f:
                creds = json.load(f)
            
            aws = creds.get("aws", {})
            if not aws.get("aws_access_key_id"):
                continue
            
            return {
                "aws_access_key_id": aws.get("aws_access_key_id"),
                "aws_secret_access_key": aws.get("aws_secret_access_key"),
                "aws_region": aws.get("aws_region", "eu-central-1"),
                "aws_sso_region": aws.get("aws_sso_region", ""),
            }
    
    pytest.skip("AWS credentials not found in config_credentials.json")


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


class TestAWSGrafanaE2E:
    """E2E tests for AWS Managed Grafana with SSO."""
    
    @pytest.fixture(scope="class")
    def terraform_workspace(self):
        """Use the persistent aws_grafana_test folder for Terraform state."""
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
        
        # POST-CLEANUP: Destroy resources after test (in test_06)
        # We don't do it here to allow inspection of test_06 results
    
    @pytest.fixture(scope="class")
    def tfvars(self, terraform_workspace):
        """Generate tfvars.json with credentials and unique naming."""
        import time
        
        aws_creds = load_aws_credentials()
        user_config = load_user_config()
        
        # Use timestamp for unique naming to avoid conflicts
        timestamp = int(time.time()) % 100000  # Last 5 digits for shorter name
        unique_suffix = f"e2e-{timestamp}"
        
        tfvars = {
            **aws_creds,
            **user_config,
            "test_name_suffix": unique_suffix,
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
        """Test Terraform plan - validates SSO detection."""
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
            
            # Check for specific SSO errors
            if "identity_store_id" in result.stderr or "aws_ssoadmin_instances" in result.stderr:
                pytest.fail(
                    "SSO detection failed! Check aws_sso_region configuration.\n"
                    f"Error: {result.stderr}"
                )
            
            pytest.fail(f"terraform plan failed: {result.stderr}")
        
        # Verify plan file was created
        assert (terraform_workspace / "plan.tfplan").exists()
    
    def test_04_terraform_apply(self, terraform_workspace, tfvars):
        """Test Terraform apply - creates Grafana workspace and admin user."""
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
            timeout=600,  # Grafana creation can take 5+ minutes
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform apply failed: {result.stderr}")
        
        # Verify state was created
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
        
        # Verify SSO was detected
        assert outputs.get("sso_available", {}).get("value") == True, \
            "SSO should be available"
        
        # Verify Grafana was created
        assert outputs.get("grafana_endpoint", {}).get("value"), \
            "Grafana endpoint should exist"
        
        # Verify admin user was created
        assert outputs.get("grafana_admin_user_id", {}).get("value"), \
            "Grafana admin user should be created"
        
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
            # Don't fail the test for destroy errors, just warn
            print("⚠️ Warning: destroy had errors, resources may need manual cleanup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
