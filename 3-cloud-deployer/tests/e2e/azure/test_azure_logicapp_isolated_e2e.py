"""
Azure Logic App Isolated E2E Test

Pytest-compatible E2E test for Azure Logic App workflow creation.
This test replicates the PRODUCTION deployment pattern to diagnose
why Logic App workflows appear empty in the Azure Portal designer.

Test Scenarios:
- Scenario A (production): 3 resources (workflow + ARM template + separate trigger)
- Scenario B (potential fix): 2 resources (workflow + ARM template only)

The test deploys using the actual template's azure_logic_app.json file
to match production behavior exactly.

IMPORTANT: Cleanup is DISABLED by default for manual investigation.
           Use --cleanup flag or run terraform destroy manually.

Prerequisites:
- Azure credentials in config_credentials.json

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/run_e2e_test.py azure-logicapp-isolated

To run WITHOUT separate trigger (test the fix):
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/run_e2e_test.py azure-logicapp-isolated --no-separate-trigger
"""

import json
import subprocess
import time
import os
import shutil
import pytest
from pathlib import Path


# Directory where this test file lives
TEST_DIR = Path(__file__).parent
TERRAFORM_SOURCE_DIR = TEST_DIR.parent / "azure_logicapp_isolated_test"
DEPLOYER_ROOT = TEST_DIR.parent.parent.parent
TEMPLATE_STATE_MACHINE = DEPLOYER_ROOT / "upload" / "template" / "state_machines" / "azure_logic_app.json"


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


class TestAzureLogicAppIsolatedE2E:
    """E2E tests for Azure Logic App - Isolated deployment test."""
    
    @pytest.fixture(scope="class")
    def terraform_workspace(self):
        """Use the persistent azure_logicapp_isolated_test folder for Terraform state."""
        workspace_path = TERRAFORM_SOURCE_DIR
        
        if not workspace_path.exists():
            pytest.fail(f"Terraform source dir not found: {workspace_path}")
        
        if not (workspace_path / "main.tf").exists():
            pytest.fail(f"main.tf not found in: {workspace_path}")
        
        print(f"\n📁 Using persistent workspace: {workspace_path}")
        
        yield workspace_path
    
    @pytest.fixture(scope="class")
    def tfvars(self, terraform_workspace):
        """Generate tfvars.json with credentials."""
        azure_creds = load_azure_credentials()
        
        # Use timestamp for unique naming to avoid conflicts
        timestamp = int(time.time()) % 100000
        unique_name = f"logicapp-iso-{timestamp}"
        
        # Check for --no-separate-trigger in pytest args or environment
        use_separate_trigger = os.environ.get("USE_SEPARATE_TRIGGER", "true").lower() == "true"
        
        tfvars = {
            **azure_creds,
            "test_name": unique_name,
            "workflow_definition_file": str(TEMPLATE_STATE_MACHINE),
            "use_separate_trigger": use_separate_trigger,
        }
        
        pattern = "PRODUCTION (3 resources)" if use_separate_trigger else "ARM-ONLY (2 resources)"
        print(f"\n📝 Test Configuration:")
        print(f"   Name: {unique_name}")
        print(f"   Pattern: {pattern}")
        print(f"   Workflow JSON: {TEMPLATE_STATE_MACHINE}")
        print(f"   Separate Trigger: {use_separate_trigger}")
        
        tfvars_path = terraform_workspace / "test.tfvars.json"
        with open(tfvars_path, "w") as f:
            json.dump(tfvars, f, indent=2)
        
        return tfvars_path
    
    def test_01_verify_template_exists(self):
        """Verify the template's azure_logic_app.json exists."""
        assert TEMPLATE_STATE_MACHINE.exists(), \
            f"Template state machine not found: {TEMPLATE_STATE_MACHINE}"
        
        # Verify it has the expected structure
        with open(TEMPLATE_STATE_MACHINE) as f:
            content = json.load(f)
        
        assert "definition" in content, \
            "azure_logic_app.json should have a 'definition' wrapper"
        assert "$schema" in content["definition"], \
            "definition should have $schema"
        assert "triggers" in content["definition"], \
            "definition should have triggers section"
        assert "manual" in content["definition"]["triggers"], \
            "definition should have 'manual' trigger"
        assert "actions" in content["definition"], \
            "definition should have actions section"
        
        print(f"\n✅ Template JSON verified:")
        print(f"   Triggers: {list(content['definition']['triggers'].keys())}")
        print(f"   Actions: {list(content['definition']['actions'].keys())}")
    
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
    
    def test_06_verify_outputs(self, terraform_workspace):
        """Verify Terraform outputs and display portal URLs."""
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
        
        # Print investigation summary
        print("\n" + "=" * 70)
        print(outputs.get("test_summary", {}).get("value", ""))
        print("=" * 70)
        
        print("\n📋 Key Outputs:")
        print(f"   Pattern: {outputs.get('test_pattern', {}).get('value', 'unknown')}")
        print(f"   Separate Trigger: {outputs.get('separate_trigger_created', {}).get('value', 'unknown')}")
        print(f"\n🔗 Portal Designer URL:")
        print(f"   {outputs.get('portal_designer_url', {}).get('value', 'unknown')}")
    
    def test_07_cleanup_disabled(self, terraform_workspace, tfvars):
        """
        Cleanup is DISABLED by default for manual investigation.
        
        Run terraform destroy manually when done:
            cd tests/e2e/azure_logicapp_isolated_test
            terraform destroy -var-file=test.tfvars.json -auto-approve
        """
        # Check if cleanup is explicitly requested
        do_cleanup = os.environ.get("E2E_CLEANUP", "false").lower() == "true"
        
        if do_cleanup:
            print("\n🧹 Cleanup requested - destroying resources...")
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
        else:
            print("\n" + "=" * 70)
            print("⏸️  CLEANUP DISABLED - Resources left running for manual investigation")
            print("=" * 70)
            print("\nTo destroy resources manually:")
            print(f"    cd {terraform_workspace}")
            print(f"    terraform destroy -var-file=test.tfvars.json -auto-approve")
            print("\nOr run with cleanup enabled:")
            print("    E2E_CLEANUP=true python tests/e2e/run_e2e_test.py azure-logicapp-isolated")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
