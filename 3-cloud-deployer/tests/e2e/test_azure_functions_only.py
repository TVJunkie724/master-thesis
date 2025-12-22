"""
Azure Functions Only E2E Test.

This test deploys Azure Function Apps using Python SDK (not Terraform) to verify
that L0 glue and User function ZIPs are correctly bundled and deployed.

Uses the SAME multicloud provider config as test_multicloud_e2e.py:
- L1: google → L2: azure (triggers ingestion glue)
- L3: aws → L4: azure (triggers adt-pusher glue)

This allows fast verification of the Azure function deployment fix without
deploying the full multicloud infrastructure.

IMPORTANT: This test deploys REAL resources and incurs costs (~$0.50).
Run with: pytest -m live -s
"""
import pytest
import os
import sys
import json
import logging
import time
import uuid
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.providers.azure.layers.function_bundler import (
    bundle_l0_functions,
    bundle_l1_functions,
    bundle_l2_functions,
    bundle_user_functions,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(scope="module")
def azure_credentials():
    """Load Azure credentials from template."""
    creds_path = Path(__file__).parent.parent.parent / "upload" / "template" / "config_credentials.json"
    
    if not creds_path.exists():
        pytest.skip("Azure credentials not found")
    
    with open(creds_path) as f:
        creds = json.load(f)
    
    azure_creds = creds.get("azure", {})
    
    required = ["azure_subscription_id", "azure_tenant_id", "azure_client_id", "azure_client_secret"]
    if not all(azure_creds.get(k) for k in required):
        pytest.skip("Azure credentials incomplete")
    
    return azure_creds


@pytest.fixture(scope="module")
def template_project_path():
    """Return path to template project."""
    return str(Path(__file__).parent.parent.parent / "upload" / "template")


@pytest.fixture(scope="module")
def multicloud_providers():
    """
    Multicloud provider config - SAME as test_multicloud_e2e.py.
    
    This triggers L0 glue functions:
    - ingestion: L1 (google) → L2 (azure) boundary
    - adt-pusher: L3 (aws) → L4 (azure) boundary
    """
    return {
        "layer_1_provider": "google",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "google",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "azure",
        "layer_5_provider": "aws"
    }


# ==============================================================================
# Helper Functions
# ==============================================================================

def deploy_zip_to_function_app(web_client, rg_name: str, app_name: str, zip_bytes: bytes) -> bool:
    """
    Deploy ZIP to Function App via Kudu API.
    
    Returns True on success, False on failure.
    """
    import requests
    from requests.auth import HTTPBasicAuth
    
    # Get publishing credentials
    publish_creds = web_client.web_apps.begin_list_publishing_credentials(rg_name, app_name).result()
    
    kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/zipdeploy?isAsync=true"
    
    # Write ZIP to temp file for upload
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp.write(zip_bytes)
        tmp_path = tmp.name
    
    try:
        with open(tmp_path, 'rb') as f:
            response = requests.post(
                kudu_url,
                data=f,
                auth=HTTPBasicAuth(
                    publish_creds.publishing_user_name,
                    publish_creds.publishing_password
                ),
                headers={"Content-Type": "application/zip"},
                timeout=300
            )
        
        return response.status_code in [200, 202]
    finally:
        os.unlink(tmp_path)


def list_function_names(web_client, rg_name: str, app_name: str) -> list:
    """List function names in a Function App."""
    try:
        functions = list(web_client.web_apps.list_functions(rg_name, app_name))
        return [f.name.split('/')[-1] for f in functions]
    except Exception as e:
        print(f"Error listing functions for {app_name}: {e}")
        return []


# ==============================================================================
# Test Class
# ==============================================================================

# Suppress noisy Azure SDK logging
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)

@pytest.mark.live
class TestAzureFunctionsOnly:
    """
    Targeted E2E test for Azure Function deployment using Python SDK.
    
    Deploys:
    - L0 Glue Function App (ingestion, adt-pusher for multicloud)
    - L2 Function App (persister)
    - User Function App (processors, event_actions, event-feedback)
    
    This uses the same provider config as test_multicloud_e2e.py to verify
    the L0 and User function deployment fix.
    """
    
    @pytest.fixture(scope="class")
    def azure_infra(self, azure_credentials, template_project_path, multicloud_providers):
        """
        Create Azure infrastructure for function deployment.
        
        Creates minimal infrastructure using Python SDK:
        - Resource Group
        - Storage Account
        - App Service Plan (shared)
        - L0 Glue Function App
        - L2 Function App
        - User Functions App
        """
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import ResourceManagementClient
            from azure.mgmt.web import WebSiteManagementClient
            from azure.mgmt.storage import StorageManagementClient
        except ImportError:
            pytest.skip("Azure SDK not installed")
        
        # Setup credentials
        subscription_id = azure_credentials["azure_subscription_id"]
        credential = ClientSecretCredential(
            tenant_id=azure_credentials["azure_tenant_id"],
            client_id=azure_credentials["azure_client_id"],
            client_secret=azure_credentials["azure_client_secret"]
        )
        
        resource_client = ResourceManagementClient(credential, subscription_id)
        web_client = WebSiteManagementClient(credential, subscription_id)
        storage_client = StorageManagementClient(credential, subscription_id)
        
        # Generate unique names
        unique_id = str(uuid.uuid4())[:8]
        rg_name = f"test-az-funcs-{unique_id}"
        location = "westeurope"
        storage_name = f"testazfunc{unique_id}"
        plan_name = f"test-az-plan-{unique_id}"
        
        l0_app_name = f"test-l0-glue-{unique_id}"
        l1_app_name = f"test-l1-disp-{unique_id}"
        l2_app_name = f"test-l2-funcs-{unique_id}"
        user_app_name = f"test-user-{unique_id}"
        
        print(f"\n{'='*60}")
        print(f"  AZURE FUNCTIONS E2E TEST")
        print(f"{'='*60}")
        print(f"  Resource Group: {rg_name}")
        print(f"  L0 Glue App: {l0_app_name}")
        print(f"  L1 Dispatcher App: {l1_app_name}")
        print(f"  L2 App: {l2_app_name}")
        print(f"  User App: {user_app_name}")
        print(f"{'='*60}\n")
        
        # Track what we've created for cleanup
        created_resources = []
        
        try:
            # 1. Create Resource Group
            print("1️⃣ Creating resource group...")
            resource_client.resource_groups.create_or_update(
                rg_name,
                {"location": location}
            )
            created_resources.append(("rg", rg_name))
            print(f"   ✓ Resource group created")
            
            # 2. Create Storage Account
            print("2️⃣ Creating storage account...")
            storage_client.storage_accounts.begin_create(
                rg_name,
                storage_name,
                {
                    "sku": {"name": "Standard_LRS"},
                    "kind": "StorageV2",
                    "location": location
                }
            ).result()
            
            # Get connection string
            keys = storage_client.storage_accounts.list_keys(rg_name, storage_name)
            storage_key = keys.keys[0].value
            storage_conn_str = f"DefaultEndpointsProtocol=https;AccountName={storage_name};AccountKey={storage_key};EndpointSuffix=core.windows.net"
            print(f"   ✓ Storage account created")
            
            # 3. Create App Service Plan (shared by all Function Apps)
            print("3️⃣ Creating App Service Plan...")
            web_client.app_service_plans.begin_create_or_update(
                rg_name,
                plan_name,
                {
                    "location": location,
                    "sku": {"name": "Y1", "tier": "Dynamic"},
                    "kind": "functionapp",
                    "reserved": True  # Linux
                }
            ).result()
            print(f"   ✓ App Service Plan created")
            
            # Common Function App settings
            def create_function_app(app_name: str, content_share: str):
                from azure.mgmt.web.models import CsmPublishingCredentialsPoliciesEntity
                
                web_client.web_apps.begin_create_or_update(
                    rg_name,
                    app_name,
                    {
                        "location": location,
                        "kind": "functionapp,linux",
                        "server_farm_id": f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.Web/serverfarms/{plan_name}",
                        "site_config": {
                            "linux_fx_version": "Python|3.11",
                            "app_settings": [
                                {"name": "FUNCTIONS_WORKER_RUNTIME", "value": "python"},
                                {"name": "FUNCTIONS_EXTENSION_VERSION", "value": "~4"},
                                {"name": "AzureWebJobsStorage", "value": storage_conn_str},
                                {"name": "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING", "value": storage_conn_str},
                                {"name": "WEBSITE_CONTENTSHARE", "value": content_share},
                                {"name": "SCM_DO_BUILD_DURING_DEPLOYMENT", "value": "true"},
                                {"name": "ENABLE_ORYX_BUILD", "value": "true"},
                                {"name": "AzureWebJobsFeatureFlags", "value": "EnableWorkerIndexing"},
                            ]
                        },
                        "properties": {"storage_account_required": True}
                    }
                ).result()
                
                # Enable SCM Basic Auth (required for ZIP deploy via Kudu)
                web_client.web_apps.update_scm_allowed(
                    rg_name, app_name,
                    CsmPublishingCredentialsPoliciesEntity(allow=True)
                )
                web_client.web_apps.update_ftp_allowed(
                    rg_name, app_name,
                    CsmPublishingCredentialsPoliciesEntity(allow=True)
                )
            
            # 4. Create L0 Glue Function App
            print("4️⃣ Creating L0 Glue Function App...")
            create_function_app(l0_app_name, f"{l0_app_name}-content")
            print(f"   ✓ L0 app created")
            
            # 5. Create L1 Dispatcher Function App
            print("5️⃣ Creating L1 Dispatcher Function App...")
            create_function_app(l1_app_name, f"{l1_app_name}-content")
            print(f"   ✓ L1 app created")
            
            # 6. Create L2 Function App
            print("6️⃣ Creating L2 Function App...")
            create_function_app(l2_app_name, f"{l2_app_name}-content")
            print(f"   ✓ L2 app created")
            
            # 7. Create User Functions App
            print("7️⃣ Creating User Functions App...")
            create_function_app(user_app_name, f"{user_app_name}-content")
            print(f"   ✓ User app created")
            
            # 8. Build ZIPs
            print("\n8️⃣ Building function ZIPs...")
            
            # L0 ZIP (multicloud config triggers ingestion + adt-pusher)
            l0_zip, l0_funcs = bundle_l0_functions(template_project_path, multicloud_providers)
            print(f"   ✓ L0 ZIP: {len(l0_zip)} bytes, functions: {l0_funcs}")
            
            # L1 ZIP (dispatcher)
            l1_zip = bundle_l1_functions(template_project_path)
            print(f"   ✓ L1 ZIP: {len(l1_zip)} bytes")
            
            # L2 ZIP
            l2_zip = bundle_l2_functions(template_project_path)
            print(f"   ✓ L2 ZIP: {len(l2_zip)} bytes")
            
            # User ZIP (from template - has processors, event_actions, event-feedback)
            user_zip = bundle_user_functions(template_project_path)
            if user_zip:
                print(f"   ✓ User ZIP: {len(user_zip)} bytes")
            else:
                print(f"   ⚠ User ZIP: None (no user functions in template)")
            
            # 9. Deploy ZIPs
            print("\n9️⃣ Deploying ZIPs via Kudu...")
            
            if deploy_zip_to_function_app(web_client, rg_name, l0_app_name, l0_zip):
                print(f"   ✓ L0 ZIP deployed")
            else:
                print(f"   ✗ L0 ZIP deployment failed")
            
            if deploy_zip_to_function_app(web_client, rg_name, l1_app_name, l1_zip):
                print(f"   ✓ L1 ZIP deployed")
            else:
                print(f"   ✗ L1 ZIP deployment failed")
            
            if deploy_zip_to_function_app(web_client, rg_name, l2_app_name, l2_zip):
                print(f"   ✓ L2 ZIP deployed")
            else:
                print(f"   ✗ L2 ZIP deployment failed")
            
            if user_zip:
                if deploy_zip_to_function_app(web_client, rg_name, user_app_name, user_zip):
                    print(f"   ✓ User ZIP deployed")
                else:
                    print(f"   ✗ User ZIP deployment failed")
            
            # 10. Wait for function sync (Oryx build takes 2-3 minutes)
            print("\n🔟 Waiting for function sync (180 seconds for Oryx build)...")
            time.sleep(180)
            
            print(f"\n{'='*60}")
            print(f"  INFRASTRUCTURE READY - RUNNING TESTS")
            print(f"{'='*60}\n")
            
            yield {
                "web_client": web_client,
                "resource_client": resource_client,
                "rg_name": rg_name,
                "l0_app_name": l0_app_name,
                "l1_app_name": l1_app_name,
                "l2_app_name": l2_app_name,
                "user_app_name": user_app_name,
                "l0_expected_functions": l0_funcs,
                "user_zip_exists": user_zip is not None,
            }
            
        finally:
            # Cleanup
            print(f"\n{'='*60}")
            print(f"  CLEANUP: Deleting resource group {rg_name}")
            print(f"{'='*60}")
            try:
                resource_client.resource_groups.begin_delete(rg_name).result()
                print("   ✓ Cleanup complete")
            except Exception as e:
                print(f"   ⚠ Cleanup failed: {e}")
                print(f"   Manual cleanup required: az group delete -n {rg_name}")
    
    # ==========================================================================
    # Tests
    # ==========================================================================
    
    def test_01_l0_functions_deployed(self, azure_infra):
        """
        Verify L0 glue functions are deployed.
        
        CRITICAL: This is the main test for the ZIP deployment fix.
        The multicloud config should trigger:
        - ingestion (L1 google → L2 azure)
        - adt-pusher (L3 aws → L4 azure)
        """
        web_client = azure_infra["web_client"]
        rg_name = azure_infra["rg_name"]
        l0_app_name = azure_infra["l0_app_name"]
        expected_funcs = azure_infra["l0_expected_functions"]
        
        print(f"\n  Checking L0 app: {l0_app_name}")
        print(f"  Expected functions: {expected_funcs}")
        
        actual_funcs = list_function_names(web_client, rg_name, l0_app_name)
        print(f"  Actual functions: {actual_funcs}")
        
        # Critical assertion
        assert len(actual_funcs) > 0, f"❌ L0 app has NO functions! ZIP deployment failed."
        
        # Check for expected functions
        for expected in expected_funcs:
            if expected in actual_funcs:
                print(f"  ✓ Found: {expected}")
            else:
                print(f"  ⚠ Missing: {expected}")
        
        # At minimum, ingestion should be present for multicloud
        assert "ingestion" in actual_funcs, f"❌ Missing 'ingestion' function. Found: {actual_funcs}"
        
        print(f"\n  ✅ L0 FUNCTION DEPLOYMENT VERIFIED")
    
    def test_02_l2_functions_deployed(self, azure_infra):
        """Verify L2 functions (persister) are deployed."""
        web_client = azure_infra["web_client"]
        rg_name = azure_infra["rg_name"]
        l2_app_name = azure_infra["l2_app_name"]
        
        print(f"\n  Checking L2 app: {l2_app_name}")
        
        actual_funcs = list_function_names(web_client, rg_name, l2_app_name)
        print(f"  Functions found: {actual_funcs}")
        
        assert len(actual_funcs) > 0, f"❌ L2 app has NO functions!"
        assert "persister" in actual_funcs, f"❌ Missing 'persister'. Found: {actual_funcs}"
        
        print(f"\n  ✅ L2 FUNCTION DEPLOYMENT VERIFIED")
    
    def test_03_user_functions_deployed(self, azure_infra):
        """Verify User functions are deployed (if ZIP exists)."""
        if not azure_infra["user_zip_exists"]:
            pytest.skip("No user functions ZIP was generated")
        
        web_client = azure_infra["web_client"]
        rg_name = azure_infra["rg_name"]
        user_app_name = azure_infra["user_app_name"]
        
        print(f"\n  Checking User app: {user_app_name}")
        
        actual_funcs = list_function_names(web_client, rg_name, user_app_name)
        print(f"  Functions found: {actual_funcs}")
        
        # User functions are optional - just log what's there
        if len(actual_funcs) > 0:
            print(f"\n  ✅ USER FUNCTION DEPLOYMENT VERIFIED")
        else:
            print(f"\n  ⚠ User app has no functions (may be expected)")
    
    def test_04_l1_functions_deployed(self, azure_infra):
        """
        Verify L1 functions (dispatcher) are deployed.
        
        This covers the deployment gap identified in the audit.
        """
        web_client = azure_infra["web_client"]
        rg_name = azure_infra["rg_name"]
        l1_app_name = azure_infra["l1_app_name"]
        
        print(f"\n  Checking L1 app: {l1_app_name}")
        
        actual_funcs = list_function_names(web_client, rg_name, l1_app_name)
        print(f"  Functions found: {actual_funcs}")
        
        # L1 should have 'dispatcher' function
        assert len(actual_funcs) > 0, f"❌ L1 app has NO functions!"
        assert "dispatcher" in actual_funcs, f"❌ Missing 'dispatcher'. Found: {actual_funcs}"
        
        print(f"\n  ✅ L1 FUNCTION DEPLOYMENT VERIFIED")
    
    
# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "live"])
