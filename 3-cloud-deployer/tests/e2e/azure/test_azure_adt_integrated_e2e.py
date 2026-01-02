"""
Azure Digital Twins (L4) Integrated E2E Test.

This test combines Terraform deployment with SDK post-deployment operations
to verify the complete ADT deployment flow:

1. Terraform deployment (azure_adt_test/main.tf):
   - ADT instance creation
   - Storage account + 3dscenes container
   - GLB file upload
   - 3DScenesConfiguration.json upload
   - RBAC permissions

2. SDK post-deployment (layer_4_adt.py):
   - DTDL model upload from azure_hierarchy.json
   - Digital twin creation
   - Relationship creation

IMPORTANT: Run this test via the helper script for full output capture:
    python tests/e2e/run_e2e_test.py azure-adt-full

Estimated duration: 5-10 minutes
Estimated cost: ~$0.10 USD
"""
import pytest
import subprocess
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional
import time

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


# Directory containing the focused Terraform config
TERRAFORM_DIR = Path(__file__).parent.parent / "azure_adt_test"

# Path to scene assets (template)
SCENE_ASSETS_PATH = Path(__file__).parent.parent.parent.parent / "upload" / "template" / "scene_assets"


def _cleanup_adt_resources_sdk(credentials: dict, prefix: str) -> None:
    """
    SDK cleanup of Azure Digital Twins resources by name pattern.
    
    This is a fallback cleanup that runs after terraform destroy to catch
    any orphaned resources that weren't tracked in Terraform state.
    
    Args:
        credentials: Dict with azure credentials
        prefix: Resource name prefix to match (e.g., 'tf-e2e-adt')
    """
    from azure.identity import ClientSecretCredential
    from azure.mgmt.resource import ResourceManagementClient
    
    azure_creds = credentials.get("azure", {})
    tenant_id = azure_creds["azure_tenant_id"]
    
    # Create credential
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=azure_creds["azure_client_id"],
        client_secret=azure_creds["azure_client_secret"]
    )
    
    subscription_id = azure_creds["azure_subscription_id"]
    resource_client = ResourceManagementClient(credential, subscription_id)
    
    print(f"    [Azure SDK] Fallback cleanup for prefix: {prefix}")
    
    # Check for orphaned Digital Twins instances
    print(f"    [Digital Twins] Checking for orphans...")
    try:
        from azure.mgmt.digitaltwins import AzureDigitalTwinsManagementClient
        dt_client = AzureDigitalTwinsManagementClient(credential, subscription_id)
        for instance in dt_client.digital_twins.list():
            if prefix in instance.name:
                print(f"      Found orphan: {instance.name}")
                try:
                    rg_name = instance.id.split('/')[4]
                    poller = dt_client.digital_twins.begin_delete(rg_name, instance.name)
                    poller.result(timeout=600)
                    print(f"        ✓ Deleted")
                except Exception as e:
                    print(f"        ✗ Error: {e}")
    except Exception as e:
        print(f"      Error: {e}")
    
    # Check for orphaned Storage Accounts
    print(f"    [Storage Accounts] Checking for orphans...")
    try:
        from azure.mgmt.storage import StorageManagementClient
        storage_client = StorageManagementClient(credential, subscription_id)
        prefix_nohyphen = prefix.replace("-", "")
        for account in storage_client.storage_accounts.list():
            if prefix in account.name or prefix_nohyphen in account.name:
                print(f"      Found orphan: {account.name}")
                try:
                    rg_name = account.id.split('/')[4]
                    storage_client.storage_accounts.delete(rg_name, account.name)
                    print(f"        ✓ Deleted")
                except Exception as e:
                    print(f"        ✗ Error: {e}")
    except Exception as e:
        print(f"      Error: {e}")
    
    # Delete matching Resource Groups (nuclear option)
    print(f"    [Resource Groups] Cleaning up...")
    try:
        for rg in resource_client.resource_groups.list():
            if prefix in rg.name or "adt-e2e" in rg.name:
                print(f"      Deleting RG: {rg.name}")
                try:
                    poller = resource_client.resource_groups.begin_delete(rg.name)
                    poller.result(timeout=600)
                    print(f"        ✓ Deleted")
                except Exception as e:
                    print(f"        ✗ Error: {e}")
    except Exception as e:
        print(f"      Error listing RGs: {e}")
    
    print(f"    [Azure SDK] Fallback cleanup complete")


@dataclass
class MockConfig:
    """Mock config object for SDK operations."""
    digital_twin_name: str
    hierarchy: Dict[str, Any]


@pytest.mark.live
class TestAzureAdtIntegratedE2E:
    """
    Integrated E2E test for Azure Digital Twins (L4) deployment.
    
    Tests the complete deployment flow:
    1. Terraform infrastructure (ADT + Storage + 3D Scenes)
    2. SDK operations (DTDL models + Twins + Relationships)
    3. Verification of all resources
    """
    
    @pytest.fixture(scope="class")
    def deployed_environment(self, request, azure_adt_e2e_project_path, azure_credentials):
        """
        Deploy ADT via Terraform + SDK operations with cleanup.
        
        Uses the focused terraform config (azure_adt_test/main.tf) for infrastructure,
        then calls SDK operations to upload DTDL models and create twins.
        """
        print("\n" + "="*60)
        print("  AZURE ADT INTEGRATED E2E TEST")
        print("="*60)
        
        project_path = Path(azure_adt_e2e_project_path)
        
        # ==========================================
        # PHASE 1: Load Credentials
        # ==========================================
        print("\n[PHASE 1] Loading credentials...")
        
        creds_paths = [
            project_path / "config_credentials.json",
            Path("/app/config_credentials.json"),
            Path("/app/upload/template/config_credentials.json"),
        ]
        
        credentials = None
        for creds_path in creds_paths:
            if creds_path.exists():
                with open(creds_path) as f:
                    credentials = json.load(f)
                print(f"  ✓ Loaded credentials from: {creds_path}")
                break
        
        if not credentials or not credentials.get("azure"):
            pytest.skip("Azure credentials not found")
        
        azure_creds = credentials["azure"]
        required_fields = [
            "azure_subscription_id",
            "azure_tenant_id",
            "azure_client_id",
            "azure_client_secret"
        ]
        for field in required_fields:
            if not azure_creds.get(field):
                pytest.skip(f"Missing Azure credential: {field}")
        
        print(f"  ✓ Subscription: {azure_creds['azure_subscription_id'][:8]}...")
        
        # ==========================================
        # PHASE 2: Load Hierarchy from Template
        # ==========================================
        print("\n[PHASE 2] Loading hierarchy...")
        
        hierarchy_path = project_path / "twin_hierarchy" / "azure_hierarchy.json"
        if not hierarchy_path.exists():
            pytest.skip(f"Hierarchy not found: {hierarchy_path}")
        
        with open(hierarchy_path) as f:
            hierarchy = json.load(f)
        
        model_count = len(hierarchy.get("models", []))
        twin_count = len(hierarchy.get("twins", []))
        rel_count = len(hierarchy.get("relationships", []))
        print(f"  ✓ Loaded hierarchy: {model_count} models, {twin_count} twins, {rel_count} relationships")
        
        # ==========================================
        # PHASE 3: Build Terraform tfvars
        # ==========================================
        print("\n[PHASE 3] Building Terraform tfvars...")
        
        tfvars = {
            "azure_subscription_id": azure_creds["azure_subscription_id"],
            "azure_tenant_id": azure_creds["azure_tenant_id"],
            "azure_client_id": azure_creds["azure_client_id"],
            "azure_client_secret": azure_creds["azure_client_secret"],
            "azure_region": azure_creds.get("azure_region", "westeurope"),
            "test_name_suffix": "e2e-full",
            "scene_assets_path": str(SCENE_ASSETS_PATH),
        }
        
        tfvars_path = TERRAFORM_DIR / "test.tfvars.json"
        with open(tfvars_path, "w") as f:
            json.dump(tfvars, f, indent=2)
        print(f"  ✓ Created tfvars: {tfvars_path}")
        
        # Track terraform outputs and state
        terraform_outputs = {}
        adt_endpoint = None
        
        # Cleanup function (COMMENTED OUT for manual verification)
        def terraform_cleanup():
            """Cleanup function - runs terraform destroy + SDK fallback."""
            print("\n" + "="*60)
            print("  CLEANUP: TERRAFORM DESTROY")
            print("="*60)
            
            # NOTE: Cleanup is COMMENTED OUT for manual verification
            # Uncomment the following block when ready for automatic cleanup:
            
            # try:
            #     result = subprocess.run(
            #         [
            #             "terraform", "destroy",
            #             "-no-color",
            #             "-auto-approve",
            #             f"-var-file={tfvars_path}",
            #         ],
            #         cwd=TERRAFORM_DIR,
            #         capture_output=True,
            #         text=True,
            #         timeout=600,
            #     )
            #     print(result.stdout)
            #     if result.returncode != 0:
            #         print(f"[CLEANUP] ✗ Terraform destroy failed: {result.stderr}")
            #     else:
            #         print("[CLEANUP] ✓ Terraform destroy completed")
            # except Exception as e:
            #     print(f"[CLEANUP] ✗ Destroy failed: {e}")
            # 
            # # SDK fallback cleanup
            # try:
            #     _cleanup_adt_resources_sdk(credentials, "adt-e2e")
            #     print("  ✓ Azure SDK cleanup completed")
            # except Exception as e:
            #     print(f"  ✗ Azure SDK cleanup failed: {e}")
            
            print("\n⚠️  CLEANUP SKIPPED - Manual verification enabled")
            print("    To manually destroy resources:")
            print(f"    cd {TERRAFORM_DIR}")
            print(f"    terraform destroy -var-file={tfvars_path}")
            
            # Always cleanup tfvars (contains secrets)
            if tfvars_path.exists():
                tfvars_path.unlink()
                print("  ✓ Removed tfvars file")
        
        # Register cleanup to run ALWAYS (on success or failure)
        request.addfinalizer(terraform_cleanup)
        
        # ==========================================
        # PHASE 4: Terraform Init
        # ==========================================
        print("\n[PHASE 4] Terraform init...")
        
        result = subprocess.run(
            ["terraform", "init", "-no-color"],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform init failed: {result.stderr}")
        print("  ✓ Terraform initialized")
        
        # ==========================================
        # PHASE 5: Terraform Plan
        # ==========================================
        print("\n[PHASE 5] Terraform plan...")
        
        result = subprocess.run(
            [
                "terraform", "plan",
                "-no-color",
                f"-var-file={tfvars_path}",
                "-out=plan.tfplan",
            ],
            cwd=TERRAFORM_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform plan failed: {result.stderr}")
        print("  ✓ Terraform plan created")
        
        # ==========================================
        # PHASE 6: Terraform Apply
        # ==========================================
        print("\n[PHASE 6] Terraform apply...")
        
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
            timeout=600,
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(result.stderr)
            pytest.fail(f"terraform apply failed: {result.stderr}")
        print("  ✓ Terraform apply completed")
        
        # ==========================================
        # PHASE 6.5: Wait for RBAC Propagation
        # ==========================================
        # Azure role assignments take 2-10 minutes to propagate.
        # Without this delay, SDK operations will fail with 403 Forbidden.
        print("\n[PHASE 6.5] Waiting for RBAC propagation...")
        rbac_wait_seconds = 90  # Conservative wait for role propagation
        print(f"  ⏳ Waiting {rbac_wait_seconds}s for Azure role assignment propagation...")
        time.sleep(rbac_wait_seconds)
        print("  ✓ RBAC wait complete")
        
        # ==========================================
        # PHASE 7: Get Terraform Outputs
        # ==========================================
        print("\n[PHASE 7] Getting Terraform outputs...")
        
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
        terraform_outputs = {k: v.get("value") for k, v in outputs.items()}
        
        adt_endpoint = terraform_outputs.get("adt_endpoint")
        storage_account = terraform_outputs.get("storage_account_name")
        
        print(f"  ✓ ADT Endpoint: {adt_endpoint}")
        print(f"  ✓ Storage Account: {storage_account}")
        
        # ==========================================
        # PHASE 8: SDK - Upload DTDL Models and Twins
        # ==========================================
        print("\n[PHASE 8] SDK - Uploading DTDL models and twins...")
        
        try:
            from azure.identity import ClientSecretCredential
            from azure.digitaltwins.core import DigitalTwinsClient
            
            # Create credential
            credential = ClientSecretCredential(
                tenant_id=azure_creds["azure_tenant_id"],
                client_id=azure_creds["azure_client_id"],
                client_secret=azure_creds["azure_client_secret"]
            )
            
            # Connect to ADT with retry for RBAC propagation
            adt_client = None
            max_retries = 5
            retry_delay = 30  # seconds
            
            for attempt in range(max_retries):
                try:
                    adt_client = DigitalTwinsClient(adt_endpoint, credential)
                    # Test connection by listing models (will fail with 403 if RBAC not propagated)
                    list(adt_client.list_models())
                    print(f"  ✓ Connected to ADT: {adt_endpoint}")
                    break
                except Exception as e:
                    if "403" in str(e) or "Forbidden" in str(e) or "AuthorizationFailed" in str(e):
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (attempt + 1)
                            print(f"  ⚠ RBAC not propagated yet (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            print(f"  ✗ RBAC propagation timeout after {max_retries} attempts")
                            raise
                    else:
                        raise
            
            if not adt_client:
                raise Exception("Failed to connect to ADT after retries")
            
            # Upload models
            models = hierarchy.get("models", [])
            if models:
                try:
                    created_models = adt_client.create_models(models)
                    created_count = len(list(created_models))
                    print(f"  ✓ Uploaded {created_count} DTDL models")
                except Exception as e:
                    if "already exists" in str(e).lower() or "ModelIdAlreadyExists" in str(e):
                        print(f"  ✓ DTDL models already exist (skipping)")
                    else:
                        print(f"  ⚠ Model upload error: {e}")
            
            # Create twins
            twins = hierarchy.get("twins", [])
            created_twins = 0
            for twin in twins:
                twin_id = twin.get("$dtId", "unknown")
                try:
                    adt_client.upsert_digital_twin(twin_id, twin)
                    created_twins += 1
                except Exception as e:
                    print(f"    ⚠ Could not create twin {twin_id}: {e}")
            print(f"  ✓ Created {created_twins}/{len(twins)} twins")
            
            # Create relationships
            relationships = hierarchy.get("relationships", [])
            created_rels = 0
            for rel in relationships:
                source_id = rel.get("$dtId", "unknown")
                rel_id = rel.get("$relationshipId", "unknown")
                try:
                    adt_client.upsert_relationship(
                        source_id, rel_id,
                        {
                            "$targetId": rel.get("$targetId"),
                            "$relationshipName": rel.get("$relationshipName")
                        }
                    )
                    created_rels += 1
                except Exception as e:
                    print(f"    ⚠ Could not create relationship {rel_id}: {e}")
            print(f"  ✓ Created {created_rels}/{len(relationships)} relationships")
            
        except ImportError as e:
            print(f"  ⚠ Azure SDK not available: {e}")
            pytest.skip("azure-digitaltwins-core SDK not installed")
        except Exception as e:
            print(f"  ⚠ SDK operations failed: {e}")
            # Don't fail the test - infrastructure is still deployed
        
        print("\n" + "="*60)
        print("  DEPLOYMENT COMPLETE - RUNNING VERIFICATION TESTS")
        print("="*60)
        
        yield {
            "terraform_outputs": terraform_outputs,
            "adt_endpoint": adt_endpoint,
            "hierarchy": hierarchy,
            "credentials": credentials,
            "project_path": str(project_path),
        }
    
    # =========================================================================
    # VERIFICATION TESTS
    # =========================================================================
    
    def test_01_adt_instance_deployed(self, deployed_environment):
        """Verify ADT instance was created by Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        adt_endpoint = outputs.get("adt_endpoint")
        assert adt_endpoint is not None, "ADT endpoint should exist"
        assert adt_endpoint.startswith("https://"), "ADT endpoint should be HTTPS URL"
        
        print(f"[VERIFY] ✓ ADT Instance: {adt_endpoint}")
    
    def test_02_storage_account_deployed(self, deployed_environment):
        """Verify Storage account was created for 3D scenes."""
        outputs = deployed_environment["terraform_outputs"]
        
        storage_name = outputs.get("storage_account_name")
        assert storage_name is not None, "Storage account should exist"
        
        scenes_url = outputs.get("scenes_container_url")
        assert scenes_url is not None, "Scenes container URL should exist"
        
        print(f"[VERIFY] ✓ Storage Account: {storage_name}")
        print(f"[VERIFY] ✓ Scenes Container: {scenes_url}")
    
    def test_03_3d_scene_files_uploaded(self, deployed_environment):
        """Verify 3D scene files were uploaded to storage."""
        outputs = deployed_environment["terraform_outputs"]
        
        glb_url = outputs.get("scene_glb_url")
        config_url = outputs.get("scene_config_url")
        
        assert glb_url is not None, "GLB file URL should exist"
        assert config_url is not None, "Config file URL should exist"
        assert "scene.glb" in glb_url, "GLB should be scene.glb"
        assert "3DScenesConfiguration.json" in config_url, "Config should be 3DScenesConfiguration.json"
        
        print(f"[VERIFY] ✓ GLB File: {glb_url}")
        print(f"[VERIFY] ✓ Config File: {config_url}")
    
    def test_04_dtdl_models_exist(self, deployed_environment):
        """Verify DTDL models were uploaded to ADT via SDK."""
        adt_endpoint = deployed_environment["adt_endpoint"]
        credentials = deployed_environment["credentials"]
        hierarchy = deployed_environment["hierarchy"]
        
        if not adt_endpoint:
            pytest.skip("ADT endpoint not available")
        
        try:
            from azure.identity import ClientSecretCredential
            from azure.digitaltwins.core import DigitalTwinsClient
            
            azure_creds = credentials["azure"]
            credential = ClientSecretCredential(
                tenant_id=azure_creds["azure_tenant_id"],
                client_id=azure_creds["azure_client_id"],
                client_secret=azure_creds["azure_client_secret"]
            )
            
            adt_client = DigitalTwinsClient(adt_endpoint, credential)
            
            # Check all models from hierarchy
            models = hierarchy.get("models", [])
            verified_count = 0
            for model in models:
                model_id = model.get("@id", "unknown")
                try:
                    adt_client.get_model(model_id)
                    print(f"[VERIFY] ✓ Model exists: {model_id}")
                    verified_count += 1
                except Exception as e:
                    print(f"[VERIFY] ✗ Model not found: {model_id} - {e}")
            
            assert verified_count == len(models), f"Expected {len(models)} models, found {verified_count}"
            print(f"[VERIFY] ✓ All {verified_count} DTDL models verified")
            
        except ImportError:
            pytest.skip("azure-digitaltwins-core SDK not installed")
    
    def test_05_twins_exist(self, deployed_environment):
        """Verify Digital Twins were created in ADT via SDK."""
        adt_endpoint = deployed_environment["adt_endpoint"]
        credentials = deployed_environment["credentials"]
        hierarchy = deployed_environment["hierarchy"]
        
        if not adt_endpoint:
            pytest.skip("ADT endpoint not available")
        
        try:
            from azure.identity import ClientSecretCredential
            from azure.digitaltwins.core import DigitalTwinsClient
            
            azure_creds = credentials["azure"]
            credential = ClientSecretCredential(
                tenant_id=azure_creds["azure_tenant_id"],
                client_id=azure_creds["azure_client_id"],
                client_secret=azure_creds["azure_client_secret"]
            )
            
            adt_client = DigitalTwinsClient(adt_endpoint, credential)
            
            # Check all twins from hierarchy
            twins = hierarchy.get("twins", [])
            verified_count = 0
            for twin in twins:
                twin_id = twin.get("$dtId", "unknown")
                try:
                    result = adt_client.get_digital_twin(twin_id)
                    print(f"[VERIFY] ✓ Twin exists: {twin_id}")
                    verified_count += 1
                except Exception as e:
                    print(f"[VERIFY] ✗ Twin not found: {twin_id} - {e}")
            
            assert verified_count == len(twins), f"Expected {len(twins)} twins, found {verified_count}"
            print(f"[VERIFY] ✓ All {verified_count} Digital Twins verified")
            
        except ImportError:
            pytest.skip("azure-digitaltwins-core SDK not installed")
    
    def test_06_relationships_exist(self, deployed_environment):
        """Verify relationships were created between twins."""
        adt_endpoint = deployed_environment["adt_endpoint"]
        credentials = deployed_environment["credentials"]
        hierarchy = deployed_environment["hierarchy"]
        
        if not adt_endpoint:
            pytest.skip("ADT endpoint not available")
        
        try:
            from azure.identity import ClientSecretCredential
            from azure.digitaltwins.core import DigitalTwinsClient
            
            azure_creds = credentials["azure"]
            credential = ClientSecretCredential(
                tenant_id=azure_creds["azure_tenant_id"],
                client_id=azure_creds["azure_client_id"],
                client_secret=azure_creds["azure_client_secret"]
            )
            
            adt_client = DigitalTwinsClient(adt_endpoint, credential)
            
            # Check relationships from hierarchy
            relationships = hierarchy.get("relationships", [])
            verified_count = 0
            for rel in relationships:
                source_id = rel.get("$dtId", "unknown")
                rel_id = rel.get("$relationshipId", "unknown")
                try:
                    result = adt_client.get_relationship(source_id, rel_id)
                    print(f"[VERIFY] ✓ Relationship exists: {rel_id}")
                    verified_count += 1
                except Exception as e:
                    print(f"[VERIFY] ✗ Relationship not found: {rel_id} - {e}")
            
            assert verified_count == len(relationships), f"Expected {len(relationships)} relationships, found {verified_count}"
            print(f"[VERIFY] ✓ All {verified_count} relationships verified")
            
        except ImportError:
            pytest.skip("azure-digitaltwins-core SDK not installed")
    
    def test_07_deployment_summary(self, deployed_environment):
        """Print deployment summary for manual verification."""
        outputs = deployed_environment["terraform_outputs"]
        hierarchy = deployed_environment["hierarchy"]
        
        print("\n" + "="*60)
        print("  DEPLOYMENT SUMMARY (for manual verification)")
        print("="*60)
        print(f"\n  ADT Endpoint: {outputs.get('adt_endpoint')}")
        print(f"  Storage Account: {outputs.get('storage_account_name')}")
        print(f"  Scenes Container: {outputs.get('scenes_container_url')}")
        print(f"\n  DTDL Models: {len(hierarchy.get('models', []))}")
        print(f"  Digital Twins: {len(hierarchy.get('twins', []))}")
        print(f"  Relationships: {len(hierarchy.get('relationships', []))}")
        print("\n  3D Scene Files:")
        print(f"    GLB: {outputs.get('scene_glb_url')}")
        print(f"    Config: {outputs.get('scene_config_url')}")
        print("\n  To view in Azure Portal:")
        print(f"    https://portal.azure.com")
        print("\n  To cleanup:")
        print(f"    cd {TERRAFORM_DIR}")
        print(f"    terraform destroy -var-file=test.tfvars.json")
        print("="*60)
        
        assert True  # Always pass - informational test


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
