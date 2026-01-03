"""
AWS Step Functions Isolated E2E Test

Pytest-compatible E2E test for AWS Step Functions state machine creation.
This test replicates the PRODUCTION deployment pattern:
1. Creates IAM role for Step Functions
2. Creates Step Functions state machine with definition from template JSON

The test deploys using the actual template's aws_step_function.json file
to match production behavior exactly.

Prerequisites:
- AWS credentials in config_credentials.json

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/run_e2e_test.py aws-stepfunctions
"""

import json
import subprocess
import time
import os
import pytest
from pathlib import Path


# Directory where this test file lives
TEST_DIR = Path(__file__).parent
TERRAFORM_SOURCE_DIR = TEST_DIR.parent / "aws_stepfunctions_test"
DEPLOYER_ROOT = TEST_DIR.parent.parent.parent
TEMPLATE_STATE_MACHINE = DEPLOYER_ROOT / "upload" / "template" / "state_machines" / "aws_step_function.json"


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
            }
    
    pytest.skip("AWS credentials not found in config_credentials.json")


class TestAWSStepFunctionsIsolatedE2E:
    """E2E tests for AWS Step Functions - Isolated deployment test."""
    
    @pytest.fixture(scope="class")
    def terraform_workspace(self):
        """Use the persistent aws_stepfunctions_test folder for Terraform state."""
        workspace_path = TERRAFORM_SOURCE_DIR
        
        if not workspace_path.exists():
            pytest.fail(f"Terraform source dir not found: {workspace_path}")
        
        if not (workspace_path / "main.tf").exists():
            pytest.fail(f"main.tf not found in: {workspace_path}")
        
        print(f"\n📁 Using workspace: {workspace_path}")
        
        yield workspace_path
    
    @pytest.fixture(scope="class")
    def tfvars(self, terraform_workspace):
        """Generate tfvars.json with credentials."""
        aws_creds = load_aws_credentials()
        
        # Use timestamp for unique naming to avoid conflicts
        timestamp = int(time.time()) % 100000
        unique_name = f"sfn-iso-{timestamp}"
        
        tfvars = {
            **aws_creds,
            "test_name": unique_name,
            "state_machine_definition_file": str(TEMPLATE_STATE_MACHINE),
        }
        
        print(f"\n📝 Test Configuration:")
        print(f"   Name: {unique_name}")
        print(f"   State Machine JSON: {TEMPLATE_STATE_MACHINE}")
        
        tfvars_path = terraform_workspace / "test.tfvars.json"
        with open(tfvars_path, "w") as f:
            json.dump(tfvars, f, indent=2)
        
        return tfvars_path
    
    def test_01_verify_template_exists(self):
        """Verify the template's aws_step_function.json exists."""
        assert TEMPLATE_STATE_MACHINE.exists(), \
            f"Template state machine not found: {TEMPLATE_STATE_MACHINE}"
        
        # Verify it has the expected structure
        with open(TEMPLATE_STATE_MACHINE) as f:
            content = json.load(f)
        
        assert "StartAt" in content, \
            "aws_step_function.json should have 'StartAt'"
        assert "States" in content, \
            "aws_step_function.json should have 'States'"
        
        print(f"\n✅ Template JSON verified:")
        print(f"   StartAt: {content.get('StartAt')}")
        print(f"   States: {list(content.get('States', {}).keys())}")
    
    def test_02_terraform_init(self, terraform_workspace, tfvars):
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
    
    def test_03_terraform_validate(self, terraform_workspace, tfvars):
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
    
    def test_04_terraform_plan(self, terraform_workspace, tfvars):
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
    
    def test_05_terraform_apply(self, terraform_workspace, tfvars):
        """Test Terraform apply - creates Step Functions state machine."""
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
            timeout=300,
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform apply failed: {result.stderr}")
        
        assert (terraform_workspace / "terraform.tfstate").exists()
    
    def test_06_verify_outputs(self, terraform_workspace):
        """Verify Terraform outputs and display console URL."""
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
        
        # Verify state machine was created
        assert outputs.get("state_machine_arn", {}).get("value"), \
            "State machine ARN should exist"
        
        # Verify status is ACTIVE
        status = outputs.get("state_machine_status", {}).get("value", "")
        assert status == "ACTIVE", f"State machine status should be ACTIVE, got: {status}"
        
        # Print summary
        print("\n" + "=" * 70)
        print(outputs.get("test_summary", {}).get("value", ""))
        print("=" * 70)
        
        print("\n📋 Key Outputs:")
        print(f"   State Machine: {outputs.get('state_machine_name', {}).get('value', 'unknown')}")
        print(f"   Status: {status}")
        print(f"\n🔗 Console URL:")
        print(f"   {outputs.get('console_url', {}).get('value', 'unknown')}")
    
    def test_07_cleanup(self, terraform_workspace, tfvars):
        """Cleanup test resources."""
        # Check if cleanup is explicitly disabled
        skip_cleanup = os.environ.get("E2E_SKIP_CLEANUP", "false").lower() == "true"
        
        if skip_cleanup:
            print("\n⏸️  CLEANUP SKIPPED - Resources left for manual inspection")
            print(f"\nTo destroy manually:")
            print(f"    cd {terraform_workspace}")
            print(f"    terraform destroy -var-file=test.tfvars.json -auto-approve")
            return
        
        print("\n🧹 Cleaning up test resources...")
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
            timeout=300,
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            print("⚠️ Warning: destroy had errors, resources may need manual cleanup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
