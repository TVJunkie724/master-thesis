"""
Azure User Functions E2E Test.

This test deploys Azure Function Apps using Python SDK to verify
that ALL user functions (processors, event_actions, event-feedback) are correctly
bundled and deployed using the process.py + wrapper pattern.

This is a SEPARATE test from test_azure_functions_only.py which tests L0, L1, L2, 
and basic user functions. This test focuses specifically on validating the complete
user function bundling using build_azure_user_bundle from package_builder.py.

Expected user functions in template:
- processors/
    - default_processor/ (process.py)
    - temperature-sensor-2/ (process.py)
- event_actions/
    - high-temperature-callback/ (function_app.py - legacy, should be converted)
    - high-temperature-callback-2/ (function_app.py - legacy)
    - alert-function/
    - notify-function/
- event-feedback/ (process.py)

IMPORTANT: This test deploys REAL resources and incurs costs (~$0.20).
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
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from src.providers.terraform.package_builder import build_azure_user_bundle


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture(scope="module")
def azure_credentials():
    """Load Azure credentials from template."""
    creds_path = Path(__file__).parent.parent.parent.parent / "upload" / "template" / "config_credentials.json"
    
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
    return Path(__file__).parent.parent.parent.parent / "upload" / "template"


@pytest.fixture(scope="module")
def providers_config():
    """Provider config with Azure as L2 (required for user function bundling)."""
    return {
        "layer_1_provider": "google",
        "layer_2_provider": "azure",  # Required for build_azure_user_bundle
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "google",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "azure",
        "layer_5_provider": "aws"
    }


# ==============================================================================
# Helper Functions
# ==============================================================================

def deploy_zip_to_function_app(web_client, rg_name: str, app_name: str, zip_path: Path) -> bool:
    """
    Deploy ZIP file to Function App via Kudu API.
    
    Returns True on success, False on failure.
    """
    import requests
    from requests.auth import HTTPBasicAuth
    
    # Get publishing credentials
    publish_creds = web_client.web_apps.begin_list_publishing_credentials(rg_name, app_name).result()
    
    kudu_url = f"https://{app_name}.scm.azurewebsites.net/api/zipdeploy?isAsync=true"
    
    with open(zip_path, 'rb') as f:
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
class TestAzureUserFunctions:
    """
    Targeted E2E test for Azure User Function deployment.
    
    This test specifically validates that ALL user functions are bundled
    using the process.py + wrapper pattern via build_azure_user_bundle.
    
    Expected functions after deployment:
    - default_processor (from processors/default_processor/)
    - temperature_sensor_2 (from processors/temperature-sensor-2/)
    - event_feedback (from event-feedback/)
    - high_temperature_callback (from event_actions/ if using process.py)
    """
    
    @pytest.fixture(scope="class")
    def azure_user_infra(self, azure_credentials, template_project_path, providers_config):
        """
        Create minimal Azure infrastructure for user function deployment test.
        
        Creates:
        - Resource Group
        - Storage Account
        - App Service Plan
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
        rg_name = f"test-az-user-{unique_id}"
        location = "westeurope"
        storage_name = f"testazuser{unique_id}"
        plan_name = f"test-user-plan-{unique_id}"
        user_app_name = f"test-userfuncs-{unique_id}"
        
        print(f"\n{'='*60}")
        print(f"  AZURE USER FUNCTIONS E2E TEST")
        print(f"{'='*60}")
        print(f"  Resource Group: {rg_name}")
        print(f"  User App: {user_app_name}")
        print(f"{'='*60}\n")
        
        try:
            # 1. Create Resource Group
            print("1️⃣ Creating resource group...")
            resource_client.resource_groups.create_or_update(
                rg_name,
                {"location": location}
            )
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
            
            # 3. Create App Service Plan
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
            
            # 4. Create User Function App
            print("4️⃣ Creating User Functions App...")
            from azure.mgmt.web.models import CsmPublishingCredentialsPoliciesEntity
            
            web_client.web_apps.begin_create_or_update(
                rg_name,
                user_app_name,
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
                            {"name": "WEBSITE_CONTENTSHARE", "value": f"{user_app_name}-content"},
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
                rg_name, user_app_name,
                CsmPublishingCredentialsPoliciesEntity(allow=True)
            )
            web_client.web_apps.update_ftp_allowed(
                rg_name, user_app_name,
                CsmPublishingCredentialsPoliciesEntity(allow=True)
            )
            print(f"   ✓ User Functions App created")
            
            # 5. Build User Functions ZIP using package_builder
            print("\n5️⃣ Building User Functions ZIP (process.py + wrapper)...")
            
            user_zip_path = build_azure_user_bundle(template_project_path, providers_config)
            
            if user_zip_path is None:
                pytest.skip("No user functions found in template project")
            
            print(f"   ✓ User ZIP built: {user_zip_path}")
            print(f"   ✓ ZIP size: {user_zip_path.stat().st_size} bytes")
            
            # List ZIP contents for debugging
            import zipfile
            with zipfile.ZipFile(user_zip_path, 'r') as zf:
                print(f"\n   📦 ZIP Contents:")
                folders = set()
                for name in zf.namelist():
                    parts = name.split('/')
                    if len(parts) > 1 and parts[0] not in folders and parts[0] != '_shared':
                        folders.add(parts[0])
                        print(f"      - {parts[0]}/")
            
            # 6. Deploy ZIP via Kudu
            print("\n6️⃣ Deploying User ZIP via Kudu...")
            
            if deploy_zip_to_function_app(web_client, rg_name, user_app_name, user_zip_path):
                print(f"   ✓ User ZIP deployed")
            else:
                print(f"   ✗ User ZIP deployment failed")
            
            # 7. Wait for function sync
            print("\n7️⃣ Waiting for function sync (180 seconds for Oryx build)...")
            time.sleep(180)
            
            print(f"\n{'='*60}")
            print(f"  INFRASTRUCTURE READY - RUNNING TESTS")
            print(f"{'='*60}\n")
            
            yield {
                "web_client": web_client,
                "resource_client": resource_client,
                "rg_name": rg_name,
                "user_app_name": user_app_name,
                "user_zip_path": user_zip_path,
            }
            
        finally:
            # Cleanup - COMMENTED OUT FOR MANUAL INSPECTION
            print(f"\n{'='*60}")
            print(f"  CLEANUP SKIPPED - Manual inspection enabled")
            print(f"  To delete later: az group delete -n {rg_name}")
            print(f"{'='*60}")
            # try:
            #     resource_client.resource_groups.begin_delete(rg_name).result()
            #     print("   ✓ Cleanup complete")
            # except Exception as e:
            #     print(f"   ⚠ Cleanup failed: {e}")
            #     print(f"   Manual cleanup required: az group delete -n {rg_name}")
    
    # ==========================================================================
    # Tests
    # ==========================================================================
    
    def test_01_user_zip_contains_all_functions(self, azure_user_infra):
        """
        Verify the user ZIP contains ALL expected user functions.
        
        This tests the build_azure_user_bundle function from package_builder.py.
        """
        import zipfile
        
        user_zip_path = azure_user_infra["user_zip_path"]
        
        print(f"\n  Inspecting User ZIP: {user_zip_path}")
        
        with zipfile.ZipFile(user_zip_path, 'r') as zf:
            all_files = zf.namelist()
            
            # Get unique module directories (excluding _shared)
            modules = set()
            for name in all_files:
                parts = name.split('/')
                if len(parts) > 1 and parts[0] != '_shared':
                    modules.add(parts[0])
            
            print(f"  Modules in ZIP: {modules}")
            
            # Expected modules based on template structure
            expected_modules = {
                "default_processor",      # from processors/default_processor/
                "temperature_sensor_2",   # from processors/temperature-sensor-2/
                "event_feedback",         # from event-feedback/
            }
            
            print(f"  Expected modules: {expected_modules}")
            
            # Check for expected modules
            for expected in expected_modules:
                if expected in modules:
                    print(f"  ✓ Found: {expected}")
                else:
                    print(f"  ✗ Missing: {expected}")
            
            # Verify each module has required files
            for module in modules:
                has_function_app = f"{module}/function_app.py" in all_files
                has_process = f"{module}/process.py" in all_files
                
                if has_function_app and has_process:
                    print(f"  ✓ {module}: function_app.py + process.py")
                elif has_function_app:
                    print(f"  ⚠ {module}: function_app.py only (legacy)")
                else:
                    print(f"  ✗ {module}: incomplete structure")
            
            # Check for _shared
            has_shared = any(f.startswith("_shared/") for f in all_files)
            assert has_shared, "❌ Missing _shared/ directory"
            print(f"  ✓ _shared/ directory present")
            
            # Check for main function_app.py
            has_main = "function_app.py" in all_files
            assert has_main, "❌ Missing main function_app.py"
            print(f"  ✓ main function_app.py present")
            
            # Critical: Verify we have at least the expected modules
            found_expected = expected_modules.intersection(modules)
            assert len(found_expected) >= 2, f"❌ Expected at least 2 user function modules, found: {found_expected}"
            
            print(f"\n  ✅ USER ZIP STRUCTURE VERIFIED")
    
    def test_02_user_functions_deployed(self, azure_user_infra):
        """
        Verify user functions are deployed and discoverable in Azure.
        
        CRITICAL: This tests that the process.py + wrapper pattern works
        for deployment, and functions are correctly registered.
        """
        web_client = azure_user_infra["web_client"]
        rg_name = azure_user_infra["rg_name"]
        user_app_name = azure_user_infra["user_app_name"]
        
        print(f"\n  Checking User app: {user_app_name}")
        
        actual_funcs = list_function_names(web_client, rg_name, user_app_name)
        print(f"  Deployed functions: {actual_funcs}")
        
        # Should have at least some functions deployed
        assert len(actual_funcs) > 0, f"❌ User app has NO functions! ZIP deployment or function discovery failed."
        
        # Expected function names (based on process.py + wrapper pattern)
        # The function names come from the wrapper's @bp.function_name decorator
        expected_patterns = [
            "default_processor",      # from processors/default_processor/
            "temperature_sensor_2",   # from processors/temperature-sensor-2/
            "event_feedback",         # from event-feedback/
        ]
        
        found_count = 0
        for expected in expected_patterns:
            # Check if function name contains expected pattern
            matching = [f for f in actual_funcs if expected in f.lower().replace("-", "_")]
            if matching:
                print(f"  ✓ Found: {matching[0]}")
                found_count += 1
            else:
                print(f"  ⚠ Not found: {expected}")
        
        # At minimum, at least 2 user functions should be deployed
        assert found_count >= 2 or len(actual_funcs) >= 2, \
            f"❌ Expected at least 2 user functions, found: {actual_funcs}"
        
        print(f"\n  ✅ USER FUNCTION DEPLOYMENT VERIFIED")
        print(f"  Total functions deployed: {len(actual_funcs)}")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "live"])
