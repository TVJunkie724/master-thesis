"""
Azure Function ZIP Deploy E2E Test.

This test validates that the function_bundler produces valid ZIP files that
can be deployed to Azure Functions and have their functions discovered.

Tests:
1. Bundler creates valid ZIP with correct structure
2. ZIP can be deployed to Azure Function App
3. Functions are detected and visible
4. Cleanup removes all resources

IMPORTANT: This test deploys REAL Azure resources and incurs costs.
Run with: pytest tests/e2e/zip_deploy_test -v -m live

Estimated duration: 5-10 minutes
Estimated cost: ~$0.10 USD
"""
import pytest
import os
import sys
import json
import time
import zipfile
import io
import base64
import requests
from pathlib import Path
from typing import Dict, Optional, Tuple

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

# Direct import of function_bundler to avoid circular imports
import importlib.util
_project_root = Path(__file__).parent.parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "function_bundler",
    _project_root / "src" / "providers" / "azure" / "layers" / "function_bundler.py"
)
_function_bundler = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_function_bundler)
bundle_l2_functions = _function_bundler.bundle_l2_functions


# Configuration matching working deployment
TEST_CONFIG = {
    "test_name": "zipdeploy-e2e",
    "location": "westeurope",
    "python_version": "3.11",
    "app_settings": {
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "FUNCTIONS_EXTENSION_VERSION": "~4",
        # NOTE: Do NOT use WEBSITE_RUN_FROM_PACKAGE=1 with remote build
        "SCM_DO_BUILD_DURING_DEPLOYMENT": "true",
        "ENABLE_ORYX_BUILD": "true",  # Required for remote pip install
        "AzureWebJobsFeatureFlags": "EnableWorkerIndexing",
    }
}


def load_azure_credentials() -> Optional[Dict]:
    """Load Azure credentials from config_credentials.json."""
    creds_path = _project_root / "upload" / "template" / "config_credentials.json"
    
    if not creds_path.exists():
        return None
    
    with open(creds_path) as f:
        all_creds = json.load(f)
    
    azure = all_creds.get("azure", {})
    return {
        "subscription_id": azure.get("azure_subscription_id", ""),
        "client_id": azure.get("azure_client_id", ""),
        "client_secret": azure.get("azure_client_secret", ""),
        "tenant_id": azure.get("azure_tenant_id", ""),
        "region": azure.get("azure_region", "westeurope"),
    }


@pytest.mark.live
class TestZipDeployE2E:
    """
    Live E2E test for Azure Function ZIP deployment.
    
    Tests the complete flow:
    1. Create ZIP using function_bundler
    2. Deploy to Azure Function App
    3. Verify functions are detected
    4. Cleanup all resources
    """
    
    @pytest.fixture(scope="class")
    def azure_clients(self):
        """Initialize Azure SDK clients."""
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resource import ResourceManagementClient
        from azure.mgmt.storage import StorageManagementClient
        from azure.mgmt.web import WebSiteManagementClient
        
        creds = load_azure_credentials()
        if not creds or not creds["subscription_id"]:
            pytest.skip("Azure credentials not configured")
        
        credential = ClientSecretCredential(
            tenant_id=creds["tenant_id"],
            client_id=creds["client_id"],
            client_secret=creds["client_secret"]
        )
        
        return {
            "credential": credential,
            "subscription_id": creds["subscription_id"],
            "resource": ResourceManagementClient(credential, creds["subscription_id"]),
            "storage": StorageManagementClient(credential, creds["subscription_id"]),
            "web": WebSiteManagementClient(credential, creds["subscription_id"]),
        }
    
    @pytest.fixture(scope="class")
    def function_zip(self) -> Tuple[bytes, int]:
        """Create function ZIP using real bundler."""
        print("\n[ZIP] Creating function ZIP using bundle_l2_functions...")
        
        zip_bytes = bundle_l2_functions(str(_project_root))
        
        # Validate ZIP structure
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            print(f"[ZIP] Created ZIP with {len(names)} files")
            
            # Count expected registrations
            content = zf.read("function_app.py").decode("utf-8")
            blueprint_count = content.count("register_functions")
            print(f"[ZIP] Found {blueprint_count} Blueprint registrations")
        
        return zip_bytes, blueprint_count
    
    @pytest.fixture(scope="class")
    def deployed_function_app(self, request, azure_clients, function_zip):
        """
        Deploy Azure Function App with ZIP and cleanup on completion.
        
        Creates:
        - Resource Group
        - Storage Account
        - App Service Plan (Linux, Consumption)
        - Linux Function App with ZIP deployed
        """
        from azure.mgmt.storage.models import (
            StorageAccountCreateParameters,
            Sku as StorageSku,
            Kind as StorageKind
        )
        from azure.mgmt.web.models import (
            AppServicePlan,
            SkuDescription,
            Site,
            SiteConfig,
            NameValuePair
        )
        
        zip_bytes, expected_functions = function_zip
        
        test_name = TEST_CONFIG["test_name"]
        location = TEST_CONFIG["location"]
        
        rg_name = f"{test_name}-rg"
        storage_name = test_name.replace("-", "") + "stor"
        plan_name = f"{test_name}-plan"
        func_name = f"{test_name}-func"
        
        resource_client = azure_clients["resource"]
        storage_client = azure_clients["storage"]
        web_client = azure_clients["web"]
        
        print("\n" + "="*60)
        print("  ZIP DEPLOY E2E TEST - DEPLOYING RESOURCES")
        print("="*60)
        
        def cleanup():
            """Delete all resources on completion."""
            print("\n" + "="*60)
            print("  CLEANUP: DELETING RESOURCES")
            print("="*60)
            try:
                print(f"[CLEANUP] Deleting resource group: {rg_name}")
                poller = resource_client.resource_groups.begin_delete(rg_name)
                poller.result()  # Wait for deletion
                print(f"[CLEANUP] ✓ Resource group deleted")
            except Exception as e:
                print(f"[CLEANUP] ⚠ Cleanup failed: {e}")
                print(f"[CLEANUP] Manual cleanup required: delete '{rg_name}'")
        
        request.addfinalizer(cleanup)
        
        try:
            # 1. Create Resource Group
            print(f"\n[DEPLOY] Creating resource group: {rg_name}")
            resource_client.resource_groups.create_or_update(
                rg_name,
                {"location": location}
            )
            print(f"[DEPLOY] ✓ Resource group created")
            
            # 2. Create Storage Account
            print(f"[DEPLOY] Creating storage account: {storage_name}")
            poller = storage_client.storage_accounts.begin_create(
                rg_name,
                storage_name,
                StorageAccountCreateParameters(
                    sku=StorageSku(name="Standard_LRS"),
                    kind=StorageKind.STORAGE_V2,
                    location=location
                )
            )
            storage_account = poller.result()
            print(f"[DEPLOY] ✓ Storage account created")
            
            # Get storage account key
            keys = storage_client.storage_accounts.list_keys(rg_name, storage_name)
            storage_key = keys.keys[0].value
            
            # 3. Create App Service Plan (Linux, Consumption Y1)
            print(f"[DEPLOY] Creating app service plan: {plan_name}")
            plan_poller = web_client.app_service_plans.begin_create_or_update(
                rg_name,
                plan_name,
                AppServicePlan(
                    location=location,
                    sku=SkuDescription(name="Y1", tier="Dynamic"),
                    reserved=True,  # Linux
                    kind="linux"
                )
            )
            plan = plan_poller.result()
            print(f"[DEPLOY] ✓ App service plan created")
            
            # 4. Create Function App
            # Build app settings
            storage_connection_string = (
                f"DefaultEndpointsProtocol=https;AccountName={storage_name};"
                f"AccountKey={storage_key};EndpointSuffix=core.windows.net"
            )
            
            app_settings = [
                NameValuePair(name=k, value=v)
                for k, v in TEST_CONFIG["app_settings"].items()
            ]
            # Add storage connection strings (required for Consumption Plan)
            app_settings.extend([
                NameValuePair(name="AzureWebJobsStorage", value=storage_connection_string),
                NameValuePair(name="WEBSITE_CONTENTAZUREFILECONNECTIONSTRING", value=storage_connection_string),
                NameValuePair(name="WEBSITE_CONTENTSHARE", value=func_name.lower()),
            ])
            
            site_config = SiteConfig(
                linux_fx_version=f"Python|{TEST_CONFIG['python_version']}",
                app_settings=app_settings
            )
            
            func_app_poller = web_client.web_apps.begin_create_or_update(
                rg_name,
                func_name,
                Site(
                    location=location,
                    server_farm_id=plan.id,
                    site_config=site_config,
                    kind="functionapp,linux"
                )
            )
            func_app = func_app_poller.result()
            print(f"[DEPLOY] ✓ Function app created")
            
            # 5. Enable SCM Basic Auth (required for zip deploy)
            from azure.mgmt.web.models import CsmPublishingCredentialsPoliciesEntity
            print("[DEPLOY] Enabling SCM Basic Auth...")
            web_client.web_apps.update_scm_allowed(
                rg_name, func_name,
                CsmPublishingCredentialsPoliciesEntity(allow=True)
            )
            web_client.web_apps.update_ftp_allowed(
                rg_name, func_name,
                CsmPublishingCredentialsPoliciesEntity(allow=True)
            )
            print(f"[DEPLOY] ✓ Basic Auth enabled")
            
            # Wait for function app to be ready
            print("[DEPLOY] Waiting 20s for function app to initialize...")
            time.sleep(20)
            
            # 6. Deploy ZIP using async zip deploy API
            print(f"[DEPLOY] Deploying ZIP file ({len(zip_bytes)} bytes)...")
            
            # Get publishing credentials
            creds_poller = web_client.web_apps.begin_list_publishing_credentials(rg_name, func_name)
            publish_creds = creds_poller.result()
            
            # Use async ZIP deploy to trigger remote build
            deploy_url = f"https://{func_name}.scm.azurewebsites.net/api/zipdeploy?isAsync=true"
            
            # Deploy using Basic auth
            auth = (publish_creds.publishing_user_name, publish_creds.publishing_password)
            
            response = requests.post(
                deploy_url,
                data=zip_bytes,
                headers={"Content-Type": "application/zip"},
                auth=auth,
                timeout=300  # 5 minutes for deployment
            )
            
            if response.status_code not in (200, 202):
                pytest.fail(f"ZIP deploy failed: {response.status_code} - {response.text}")
            
            print(f"[DEPLOY] ✓ ZIP deploy initiated (async)")
            
            # Wait for Oryx build and function sync (180s is needed for remote build)
            print("[DEPLOY] Waiting 180s for Oryx build to complete...")
            time.sleep(180)
            
            print("\n" + "="*60)
            print("  DEPLOYMENT COMPLETE - RUNNING TESTS")
            print("="*60)
            
            yield {
                "resource_group": rg_name,
                "function_app_name": func_name,
                "function_app_url": f"https://{func_app.default_host_name}",
                "expected_functions": expected_functions,
                "web_client": web_client,
            }
            
        except Exception as e:
            print(f"\n[DEPLOY] ✗ DEPLOYMENT FAILED: {e}")
            raise
    
    # =========================================================================
    # TESTS
    # =========================================================================
    
    def test_01_zip_has_valid_structure(self, function_zip):
        """Bundler creates ZIP with correct structure for Azure Functions."""
        zip_bytes, _ = function_zip
        
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            
            # Required root files
            assert "function_app.py" in names, "Missing main function_app.py"
            assert "requirements.txt" in names, "Missing requirements.txt"
            assert "host.json" in names, "Missing host.json"
            
            # _shared module
            assert "_shared/__init__.py" in names, "Missing _shared/__init__.py"
            
            # Function submodules (Blueprint pattern)
            assert "persister/__init__.py" in names, "Missing persister/__init__.py"
            assert "persister/function_app.py" in names, "Missing persister/function_app.py"
            
            # Verify main function_app.py has Blueprint registrations
            content = zf.read("function_app.py").decode("utf-8")
            assert "register_functions" in content, "Main file should register Blueprints"
            assert "func.FunctionApp()" in content, "Main file should create FunctionApp"
            
            print(f"[TEST] ✓ ZIP structure valid with {len(names)} files")
    
    def test_02_function_app_created(self, deployed_function_app):
        """Function App is created and accessible."""
        func_name = deployed_function_app["function_app_name"]
        rg_name = deployed_function_app["resource_group"]
        web_client = deployed_function_app["web_client"]
        
        # Verify function app exists
        func_app = web_client.web_apps.get(rg_name, func_name)
        assert func_app is not None, "Function App should exist"
        assert func_app.state == "Running", f"Function App should be running, got: {func_app.state}"
        
        print(f"[TEST] ✓ Function App '{func_name}' exists and is running")
    
    def test_03_functions_detected(self, deployed_function_app):
        """Functions are detected and visible in Azure."""
        func_name = deployed_function_app["function_app_name"]
        rg_name = deployed_function_app["resource_group"]
        expected = deployed_function_app["expected_functions"]
        web_client = deployed_function_app["web_client"]
        
        # List functions with retries
        max_retries = 5
        functions_found = []
        
        for attempt in range(1, max_retries + 1):
            print(f"\n[TEST] Attempt {attempt}/{max_retries}: Listing functions...")
            
            try:
                functions = list(web_client.web_apps.list_functions(rg_name, func_name))
                functions_found = [f.name.split('/')[-1] for f in functions]
                
                print(f"[TEST] Found {len(functions_found)} functions: {functions_found}")
                
                if len(functions_found) >= expected:
                    break
                    
                if attempt < max_retries:
                    print(f"[TEST] Not enough functions yet, waiting 30s...")
                    time.sleep(30)
                    
            except Exception as e:
                print(f"[TEST] Error listing functions: {e}")
                if attempt < max_retries:
                    time.sleep(30)
        
        # Verify we found all expected functions
        assert len(functions_found) >= expected, (
            f"Expected at least {expected} functions, found {len(functions_found)}: {functions_found}"
        )
        
        print(f"[TEST] ✓ All {len(functions_found)} functions detected: {functions_found}")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "live"])
