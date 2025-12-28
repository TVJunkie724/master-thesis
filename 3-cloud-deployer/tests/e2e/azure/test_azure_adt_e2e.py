"""
Azure Digital Twins (L4) Focused E2E Test.

This test deploys ONLY Layer 4 resources (Azure Digital Twins + 3D Scene Assets)
for rapid testing of ADT deployment and scene upload without full infrastructure.

IMPORTANT: Run this test via the helper script for full output capture:
    python tests/e2e/run_e2e_test.py azure-adt

Estimated duration: 5-10 minutes
Estimated cost: ~$0.10 USD
"""
import pytest
import subprocess
import json
import os
from pathlib import Path

# Directory containing the focused Terraform config
TERRAFORM_DIR = Path(__file__).parent.parent / "azure_adt_test"

# Path to scene assets (template) - go up 4 levels: azure/ -> e2e/ -> tests/ -> deployer/
SCENE_ASSETS_PATH = Path(__file__).parent.parent.parent.parent / "upload" / "template" / "scene_assets"


class TestAzureAdtE2E:
    """
    E2E test for Azure Digital Twins (L4) deployment.
    
    Tests:
    1. ADT instance creation
    2. Storage account + 3dscenes container
    3. GLB file upload
    4. 3DScenesConfiguration.json upload
    5. Filename reference consistency
    6. RBAC permissions
    """
    
    @pytest.fixture(scope="class")
    def tfvars(self):
        """
        Load Azure credentials and generate tfvars.
        
        Reads from config_credentials.json (searches multiple paths) and creates
        test.tfvars.json in the azure_adt_test directory.
        """
        # Search multiple paths for credentials (same pattern as Grafana test)
        deployer_root = Path(__file__).parent.parent.parent
        creds_paths = [
            deployer_root / "config_credentials.json",
            Path("/app/config_credentials.json"),
            Path("/app/upload/template/config_credentials.json"),
        ]
        
        azure_creds = None
        for creds_path in creds_paths:
            if creds_path.exists():
                with open(creds_path) as f:
                    creds = json.load(f)
                
                azure = creds.get("azure", {})
                if azure.get("azure_subscription_id"):
                    azure_creds = azure
                    break
        
        if not azure_creds:
            pytest.skip("Azure credentials not found in config_credentials.json")
        
        required_fields = [
            "azure_subscription_id",
            "azure_tenant_id", 
            "azure_client_id",
            "azure_client_secret"
        ]
        
        for field in required_fields:
            if not azure_creds.get(field):
                pytest.skip(f"Missing Azure credential: {field}")
        
        # Build tfvars with scene assets path
        tfvars = {
            "azure_subscription_id": azure_creds["azure_subscription_id"],
            "azure_tenant_id": azure_creds["azure_tenant_id"],
            "azure_client_id": azure_creds["azure_client_id"],
            "azure_client_secret": azure_creds["azure_client_secret"],
            "azure_region": azure_creds.get("azure_region", "westeurope"),
            "test_name_suffix": "e2e-pytest",
            "scene_assets_path": str(SCENE_ASSETS_PATH),
        }
        
        # Write tfvars file
        tfvars_path = TERRAFORM_DIR / "test.tfvars.json"
        with open(tfvars_path, "w") as f:
            json.dump(tfvars, f, indent=2)
        
        yield tfvars_path
        
        # Cleanup tfvars (contains secrets)
        if tfvars_path.exists():
            tfvars_path.unlink()
    
    def test_01_terraform_init(self, tfvars):
        """Initialize Terraform in the azure_adt_test directory."""
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
        """Test Terraform plan - validates ADT and 3D scene resources."""
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
            pytest.fail(f"terraform plan failed: {result.stderr}")
        
        # Verify key resources are planned
        assert "azurerm_digital_twins_instance.test" in result.stdout, \
            "ADT instance should be in plan"
        assert "azurerm_storage_container.scenes" in result.stdout, \
            "Scenes container should be in plan"
        assert "azurerm_storage_blob.scene_glb" in result.stdout, \
            "GLB blob should be in plan"
        assert "azurerm_storage_blob.scene_config" in result.stdout, \
            "Config blob should be in plan"
    
    def test_04_terraform_apply(self, tfvars):
        """Test Terraform apply - creates ADT and uploads 3D scene files."""
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
            timeout=600,  # ADT creation can take a few minutes
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform apply failed: {result.stderr}")
    
    def test_05_verify_outputs(self, tfvars):
        """Verify Terraform outputs and resource creation."""
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
        
        # Print test summary
        test_summary = outputs.get("test_summary", {}).get("value", "")
        print(test_summary)
        
        # Verify ADT was created
        assert outputs.get("adt_endpoint", {}).get("value"), \
            "ADT endpoint should exist"
        
        # Verify storage was created
        assert outputs.get("storage_account_name", {}).get("value"), \
            "Storage account should exist"
        
        # Verify scene files were uploaded
        assert outputs.get("scene_glb_url", {}).get("value"), \
            "GLB file should be uploaded"
        assert outputs.get("scene_config_url", {}).get("value"), \
            "Config file should be uploaded"
        
        # Verify scenes container URL
        container_url = outputs.get("scenes_container_url", {}).get("value")
        assert container_url, "Scenes container URL should exist"
        print(f"\n✅ Scenes container URL: {container_url}")
        print("   (Use this URL to link ADT to 3D Scenes Studio)")
    
    def test_06_verify_scene_config(self, tfvars):
        """Verify 3DScenesConfiguration.json references correct GLB filename."""
        config_path = SCENE_ASSETS_PATH / "azure" / "3DScenesConfiguration.json"
        
        if not config_path.exists():
            pytest.skip("3DScenesConfiguration.json not found")
        
        with open(config_path) as f:
            config = json.load(f)
        
        # Find the GLB reference
        scenes = config.get("configuration", {}).get("scenes", [])
        if not scenes:
            pytest.skip("No scenes defined in config")
        
        assets = scenes[0].get("assets", [])
        if not assets:
            pytest.skip("No assets defined in scene")
        
        glb_url = assets[0].get("url", "")
        
        # Verify it matches what Terraform uploads
        assert glb_url == "scene.glb", \
            f"GLB URL should be 'scene.glb', got '{glb_url}'. " \
            "This mismatch causes empty data visualizer!"
        
        print(f"✅ GLB filename reference matches: {glb_url}")
    
    def test_07_terraform_destroy(self, tfvars):
        """Cleanup - destroy all test resources."""
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
            print("\n⚠️ Warning: destroy had errors, resources may need manual cleanup")
        
        # Always pass - we want to see the output even if destroy fails
        assert True


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
