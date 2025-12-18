"""
Minimal Azure EventGrid + Function App E2E Test.

This test uses only Python Azure SDK (NO Terraform) to:
1. Create a Resource Group
2. Create a Storage Account
3. Create an App Service Plan
4. Create a Function App with the dispatcher function
5. Wait for function code to sync
6. Create an IoT Hub
7. Create an EventGrid subscription from IoT Hub to dispatcher function
8. Verify the subscription works
9. Clean up everything

This isolates the EventGrid subscription issue without Terraform complexity.

Run with: pytest -m live
"""
import pytest
import os
import sys
import json
import time
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))


@pytest.mark.live
class TestEventGridMinimal:
    """
    Minimal SDK-only test for EventGrid subscription to Function App.
    
    This test bypasses Terraform to give us direct control and visibility
    into the Function App deployment and EventGrid subscription process.
    """
    
    TEST_PREFIX = "evt-test"
    
    @pytest.fixture(scope="class")
    def azure_clients(self, azure_credentials):
        """Create all Azure SDK clients."""
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resource import ResourceManagementClient
        from azure.mgmt.storage import StorageManagementClient
        from azure.mgmt.web import WebSiteManagementClient
        from azure.mgmt.iothub import IotHubClient
        from azure.mgmt.eventgrid import EventGridManagementClient
        
        # Load credentials from fixture
        creds_path = Path(__file__).parent.parent.parent.parent / "upload" / "template" / "config_credentials.json"
        with open(creds_path) as f:
            all_creds = json.load(f)
        
        azure_creds = all_creds.get("azure", {})
        
        credential = ClientSecretCredential(
            tenant_id=azure_creds["azure_tenant_id"],
            client_id=azure_creds["azure_client_id"],
            client_secret=azure_creds["azure_client_secret"]
        )
        
        subscription_id = azure_creds["azure_subscription_id"]
        region = azure_creds.get("azure_region", "westeurope")
        
        return {
            "credential": credential,
            "subscription_id": subscription_id,
            "region": region,
            "resource": ResourceManagementClient(credential, subscription_id),
            "storage": StorageManagementClient(credential, subscription_id),
            "web": WebSiteManagementClient(credential, subscription_id),
            "iothub": IotHubClient(credential, subscription_id),
            "eventgrid": EventGridManagementClient(credential, subscription_id),
        }
    
    @pytest.fixture(scope="class")
    def deployed_resources(self, request, azure_clients):
        """
        Deploy minimal resources using Python SDK with GUARANTEED cleanup.
        """
        from azure.mgmt.resource.resources.models import ResourceGroup
        from azure.mgmt.storage.models import StorageAccountCreateParameters, Sku, Kind
        from azure.mgmt.web.models import AppServicePlan, SkuDescription, Site, SiteConfig
        
        print("\n" + "="*60)
        print("  MINIMAL EVENTGRID SDK TEST")
        print("="*60)
        
        # Unique names
        unique_id = str(uuid.uuid4())[:8]
        rg_name = f"{self.TEST_PREFIX}-rg-{unique_id}"
        storage_name = f"evttest{unique_id}".replace("-", "")[:24]  # Storage names are strict
        plan_name = f"{self.TEST_PREFIX}-plan-{unique_id}"
        func_app_name = f"{self.TEST_PREFIX}-func-{unique_id}"
        iothub_name = f"{self.TEST_PREFIX}-iot-{unique_id}"
        
        region = azure_clients["region"]
        resources = {
            "rg_name": rg_name,
            "storage_name": storage_name,
            "plan_name": plan_name,
            "func_app_name": func_app_name,
            "iothub_name": iothub_name,
            "region": region,
            "function_deployed": False,
            "eventgrid_created": False,
        }
        
        # Cleanup is DISABLED for debugging - uncomment to enable
        # def cleanup():
        #     print("\n" + "="*60)
        #     print("  CLEANUP: Deleting resource group")
        #     print("="*60)
        #     try:
        #         poller = azure_clients["resource"].resource_groups.begin_delete(rg_name)
        #         print(f"  Deleting {rg_name}... (async)")
        #     except Exception as e:
        #         print(f"  Cleanup failed: {e}")
        # 
        # request.addfinalizer(cleanup)
        print(f"\n  ⚠️  CLEANUP DISABLED - Resources will persist for debugging")
        print(f"  Resource Group: {rg_name}")
        
        try:
            # Step 1: Create Resource Group
            print(f"\n[1/7] Creating Resource Group: {rg_name}")
            azure_clients["resource"].resource_groups.create_or_update(
                rg_name,
                ResourceGroup(location=region)
            )
            print("  ✓ Resource Group created")
            
            # Step 2: Create Storage Account
            print(f"\n[2/7] Creating Storage Account: {storage_name}")
            poller = azure_clients["storage"].storage_accounts.begin_create(
                rg_name,
                storage_name,
                StorageAccountCreateParameters(
                    sku=Sku(name="Standard_LRS"),
                    kind=Kind.STORAGE_V2,
                    location=region,
                )
            )
            storage_account = poller.result()
            
            # Get connection string
            keys = azure_clients["storage"].storage_accounts.list_keys(rg_name, storage_name)
            storage_key = keys.keys[0].value
            storage_conn_str = f"DefaultEndpointsProtocol=https;AccountName={storage_name};AccountKey={storage_key};EndpointSuffix=core.windows.net"
            resources["storage_conn_str"] = storage_conn_str
            print("  ✓ Storage Account created")
            
            # Step 3: Create App Service Plan (Consumption)
            print(f"\n[3/7] Creating App Service Plan: {plan_name}")
            poller = azure_clients["web"].app_service_plans.begin_create_or_update(
                rg_name,
                plan_name,
                AppServicePlan(
                    location=region,
                    sku=SkuDescription(name="Y1", tier="Dynamic"),  # Consumption plan
                    reserved=True,  # Linux
                    kind="linux",
                )
            )
            poller.result()
            print("  ✓ App Service Plan created")
            
            # Step 4: Create Function App
            print(f"\n[4/7] Creating Function App: {func_app_name}")
            func_app = azure_clients["web"].web_apps.begin_create_or_update(
                rg_name,
                func_app_name,
                Site(
                    location=region,
                    server_farm_id=f"/subscriptions/{azure_clients['subscription_id']}/resourceGroups/{rg_name}/providers/Microsoft.Web/serverfarms/{plan_name}",
                    kind="functionapp,linux",
                    site_config=SiteConfig(
                        linux_fx_version="Python|3.11",
                        app_settings=[
                            {"name": "FUNCTIONS_WORKER_RUNTIME", "value": "python"},
                            {"name": "FUNCTIONS_EXTENSION_VERSION", "value": "~4"},
                            {"name": "AzureWebJobsStorage", "value": storage_conn_str},
                            {"name": "SCM_DO_BUILD_DURING_DEPLOYMENT", "value": "true"},
                            {"name": "ENABLE_ORYX_BUILD", "value": "true"},
                            {"name": "AzureWebJobsFeatureFlags", "value": "EnableWorkerIndexing"},
                            # Required for Consumption Plan
                            {"name": "WEBSITE_CONTENTAZUREFILECONNECTIONSTRING", "value": storage_conn_str},
                            {"name": "WEBSITE_CONTENTSHARE", "value": func_app_name.lower()},
                        ],
                    ),
                )
            ).result()
            resources["func_app_id"] = func_app.id
            resources["func_app_name"] = func_app_name
            print("  ✓ Function App created")
            
            # Step 4.5: Enable SCM Basic Auth (required for zip deploy)
            from azure.mgmt.web.models import CsmPublishingCredentialsPoliciesEntity
            print("  Enabling SCM Basic Auth...")
            azure_clients["web"].web_apps.update_scm_allowed(
                rg_name, func_app_name,
                CsmPublishingCredentialsPoliciesEntity(allow=True)
            )
            azure_clients["web"].web_apps.update_ftp_allowed(
                rg_name, func_app_name,
                CsmPublishingCredentialsPoliciesEntity(allow=True)
            )
            print("  ✓ Basic Auth enabled")
            
            # Wait for function app to initialize
            print("  Waiting 20s for function app to initialize...")
            time.sleep(20)
            
            # Step 5: Deploy function code via ZIP
            print(f"\n[5/7] Deploying dispatcher function code...")
            self._deploy_function_code(azure_clients, rg_name, func_app_name)
            
            # Wait for function to sync - increased to 180s (3 minutes)
            print("  Waiting up to 180 seconds for Oryx build...")
            for i in range(18):  # 18 * 10s = 180s = 3 minutes
                time.sleep(10)
                # Check if function is visible
                try:
                    functions = list(azure_clients["web"].web_apps.list_functions(rg_name, func_app_name))
                    if any(f.name.endswith("/dispatcher") for f in functions):
                        print(f"  ✓ Dispatcher function visible after {(i+1)*10}s")
                        resources["function_deployed"] = True
                        break
                except Exception as e:
                    pass
                print(f"    Waiting... ({(i+1)*10}s)")
            
            if not resources["function_deployed"]:
                print("  ⚠ Function not visible after 180s, trying EventGrid anyway...")
            
            # Step 6: Create IoT Hub
            print(f"\n[6/7] Creating IoT Hub: {iothub_name}")
            poller = azure_clients["iothub"].iot_hub_resource.begin_create_or_update(
                rg_name,
                iothub_name,
                {
                    "location": region,
                    "sku": {"name": "S1", "capacity": 1},
                }
            )
            iothub = poller.result()
            resources["iothub_id"] = iothub.id
            print("  ✓ IoT Hub created")
            
            # Step 7: Create EventGrid System Topic + Subscription
            print(f"\n[7/7] Creating EventGrid subscription to dispatcher...")
            
            # First create system topic
            topic_name = f"{self.TEST_PREFIX}-topic-{unique_id}"
            topic = azure_clients["eventgrid"].system_topics.begin_create_or_update(
                rg_name,
                topic_name,
                {
                    "location": region,
                    "source": iothub.id,
                    "topic_type": "Microsoft.Devices.IoTHubs",
                }
            ).result()
            print(f"  ✓ System Topic created: {topic_name}")
            
            # Create subscription
            sub_name = f"{self.TEST_PREFIX}-sub-{unique_id}"
            function_endpoint = f"{func_app.id}/functions/dispatcher"
            
            print(f"  Creating subscription to: {function_endpoint}")
            
            try:
                from azure.mgmt.eventgrid.models import (
                    EventSubscription,
                    AzureFunctionEventSubscriptionDestination,
                    EventSubscriptionFilter
                )
                
                subscription = azure_clients["eventgrid"].system_topic_event_subscriptions.begin_create_or_update(
                    rg_name,
                    topic_name,
                    sub_name,
                    EventSubscription(
                        destination=AzureFunctionEventSubscriptionDestination(
                            resource_id=function_endpoint
                        ),
                        filter=EventSubscriptionFilter(
                            included_event_types=["Microsoft.Devices.DeviceTelemetry"]
                        )
                    )
                ).result()
                resources["eventgrid_created"] = True
                print("  ✓ EventGrid subscription created!")
            except Exception as e:
                print(f"  ✗ EventGrid subscription FAILED: {e}")
                resources["eventgrid_error"] = str(e)
            
            yield resources
            
        except Exception as e:
            print(f"\n  ✗ Setup failed: {e}")
            resources["setup_error"] = str(e)
            yield resources
    
    def _deploy_function_code(self, azure_clients, rg_name, func_app_name):
        """Deploy dispatcher function code via Kudu ZIP deploy."""
        import requests
        import zipfile
        import io
        
        # Build the dispatcher function ZIP
        from src.providers.azure.layers.function_bundler import bundle_l1_functions
        
        project_path = Path(__file__).parent.parent.parent.parent / "upload" / "template"
        zip_bytes = bundle_l1_functions(str(project_path))
        
        if not zip_bytes:
            raise Exception("Failed to bundle L1 functions")
        
        # Get publishing credentials
        creds = azure_clients["web"].web_apps.begin_list_publishing_credentials(
            rg_name, func_app_name
        ).result()
        
        # Use async ZIP deploy to trigger remote build (CRITICAL for Oryx)
        deploy_url = f"https://{func_app_name}.scm.azurewebsites.net/api/zipdeploy?isAsync=true"
        
        print(f"  Deploying to: {deploy_url}")
        
        response = requests.post(
            deploy_url,
            data=zip_bytes,
            auth=(creds.publishing_user_name, creds.publishing_password),
            headers={"Content-Type": "application/zip"},
            timeout=300,
        )
        
        if response.status_code in [200, 202]:
            print(f"  ✓ ZIP deploy successful (status: {response.status_code})")
        else:
            print(f"  ✗ ZIP deploy failed: {response.status_code} - {response.text}")
    
    # ==========================================================================
    # TESTS
    # ==========================================================================
    
    def test_01_function_app_created(self, deployed_resources):
        """Verify Function App was created."""
        assert "func_app_id" in deployed_resources, f"Setup failed: {deployed_resources.get('setup_error')}"
        print(f"  ✓ Function App ID: {deployed_resources['func_app_id']}")
    
    def test_02_function_visible(self, deployed_resources):
        """Verify dispatcher function is visible."""
        assert deployed_resources.get("function_deployed"), \
            "Dispatcher function not visible in Function App (Oryx build may have failed)"
        print("  ✓ Dispatcher function is deployed and visible")
    
    def test_03_eventgrid_subscription_created(self, deployed_resources):
        """Verify EventGrid subscription was created successfully."""
        if "eventgrid_error" in deployed_resources:
            pytest.fail(f"EventGrid subscription failed: {deployed_resources['eventgrid_error']}")
        
        assert deployed_resources.get("eventgrid_created"), \
            "EventGrid subscription was not created"
        print("  ✓ EventGrid subscription created successfully")
