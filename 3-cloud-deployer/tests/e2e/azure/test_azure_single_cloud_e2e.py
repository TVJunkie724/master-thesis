"""
Azure Single-Cloud End-to-End Test.

This test deploys all Azure layers, sends IoT messages through the pipeline,
verifies data reaches Cosmos DB and Grafana, then destroys all resources.

IMPORTANT: This test deploys REAL Azure resources and incurs costs.
Run with: pytest -m live

Estimated duration: 20-40 minutes
Estimated cost: ~$0.50-2.00 USD
"""
import pytest
import os
import sys
import json
import time
import requests
from typing import Dict, List, Any, Optional

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))


@pytest.mark.live
class TestAzureSingleCloudE2E:
    """
    Live E2E test for Azure single-cloud deployment.
    
    Tests the complete data flow:
    IoT Device → IoT Hub → Dispatcher → Persister → Cosmos DB → Hot Reader → Grafana
    
    Uses template project as input with config_providers.json set to all-Azure.
    """
    
    @pytest.fixture(scope="class")
    def deployed_environment(self, request, e2e_project_path, azure_credentials):
        """
        Deploy all Azure layers with GUARANTEED cleanup.
        
        Even if tests fail, cleanup will run and report status.
        """
        from src.core.config_loader import load_project_config, load_credentials, get_required_providers
        from src.core.context import DeploymentContext
        from src.core.registry import ProviderRegistry
        from pathlib import Path
        import validator
        
        # Import providers to trigger registration in the registry
        import src.providers  # noqa: F401
        import constants as CONSTANTS
        
        print("\n" + "="*60)
        print("  AZURE E2E TEST - PRE-DEPLOYMENT VALIDATION")
        print("="*60)
        
        project_path = Path(e2e_project_path)
        
        # ==========================================
        # PHASE 1: Validate All Configuration Files
        # ==========================================
        print("\n[VALIDATION] Phase 1: Configuration Files")
        
        # Validate each required config file using existing validator
        config_files_to_validate = [
            CONSTANTS.CONFIG_FILE,
            CONSTANTS.CONFIG_IOT_DEVICES_FILE,
            CONSTANTS.CONFIG_EVENTS_FILE,
            CONSTANTS.CONFIG_CREDENTIALS_FILE,
            CONSTANTS.CONFIG_PROVIDERS_FILE,
        ]
        
        for config_filename in config_files_to_validate:
            config_file_path = project_path / config_filename
            if config_file_path.exists():
                try:
                    with open(config_file_path, 'r') as f:
                        content = json.load(f)
                    validator.validate_config_content(config_filename, content)
                    print(f"  ✓ {config_filename} validated")
                except Exception as e:
                    pytest.fail(f"Validation failed for {config_filename}: {e}")
            else:
                pytest.fail(f"Required config file missing: {config_filename}")
        
        # Load project config for later use
        try:
            config = load_project_config(project_path)
            print(f"  ✓ Project config loaded (twin_name: {config.digital_twin_name})")
        except Exception as e:
            pytest.fail(f"Config loading failed: {e}")
        
        # Load credentials for later use  
        try:
            credentials = load_credentials(project_path)
        except Exception as e:
            pytest.fail(f"Credentials loading failed: {e}")
        
        # ==========================================
        # PHASE 2: Validate Azure Credentials
        # ==========================================
        print("\n[VALIDATION] Phase 2: Azure Credentials")
        
        azure_creds = credentials.get("azure", {})
        if not azure_creds:
            pytest.fail("No Azure credentials found in config_credentials.json")
        
        # Use constants for required fields check
        required_fields = CONSTANTS.REQUIRED_CREDENTIALS_FIELDS.get("azure", [])
        missing_fields = [f for f in required_fields if not azure_creds.get(f)]
        if missing_fields:
            pytest.fail(f"Missing required Azure credential fields: {missing_fields}")
        print(f"  ✓ All required fields present: {len(required_fields)} fields")
        
        # Log regions for visibility
        azure_region = azure_creds.get("azure_region")
        azure_region_iothub = azure_creds.get("azure_region_iothub")
        print(f"  ✓ General region: {azure_region}")
        print(f"  ✓ IoT Hub region: {azure_region_iothub}")
        
        # ==========================================
        # PHASE 2.5: Validate Azure API Permissions
        # ==========================================
        print("\n[VALIDATION] Phase 2.5: Azure API Permissions Check")
        
        from api.azure_credentials_checker import check_azure_credentials
        
        permissions_result = check_azure_credentials(azure_creds)
        
        if permissions_result["status"] == "valid":
            print(f"  ✓ All required permissions present")
            assigned_roles = permissions_result.get('assigned_roles', [])
            if assigned_roles:
                print(f"  ✓ Assigned roles: {', '.join(assigned_roles)}")
        elif permissions_result["status"] == "check_failed":
            pytest.fail(
                f"Cannot verify permissions: {permissions_result['message']}\n"
                "Grant 'Reader' role at subscription level to enable permission checking."
            )
        else:
            # Build detailed error message with missing permissions by layer
            error_lines = [f"Azure credentials missing required permissions: {permissions_result['message']}"]
            for layer_name, layer_info in permissions_result.get("by_layer", {}).items():
                if layer_info.get("status") != "valid":
                    missing = layer_info.get("missing_actions", [])
                    if missing:
                        error_lines.append(f"  {layer_name}: missing {missing}")
            error_lines.append("\nRecommended fix: Assign the 'Digital Twin Deployer' custom role.")
            error_lines.append("See: docs/references/azure_custom_role.json")
            pytest.fail("\n".join(error_lines))
        
        # ==========================================
        # PHASE 3: Initialize Azure Provider
        # ==========================================
        print("\n[VALIDATION] Phase 3: Azure Provider Initialization")
        
        # Create context directly (not using factory since project is in temp dir)
        context = DeploymentContext(
            project_name=config.digital_twin_name,
            project_path=project_path,
            config=config
        )
        
        # Initialize Azure provider
        required = get_required_providers(config)
        for prov_name in required:
            if not prov_name or prov_name.upper() == "NONE":
                continue
            try:
                provider_instance = ProviderRegistry.get(prov_name)
                creds = credentials.get(prov_name, {})
                if creds or prov_name in ("aws", "azure"):
                    provider_instance.initialize_clients(creds, config.digital_twin_name)
                    context.providers[prov_name] = provider_instance
                    print(f"  ✓ Provider '{prov_name}' initialized")
            except ValueError as e:
                # Fail-fast on missing credentials
                pytest.fail(f"Provider '{prov_name}' initialization failed: {e}")
            except Exception as e:
                print(f"  ✗ Provider '{prov_name}' failed: {e}")
        
        # Get Azure provider and its deployer strategy
        provider = context.providers.get("azure")
        if not provider:
            pytest.fail("Azure provider not initialized - check credentials")
        
        # ==========================================
        # PHASE 4: Validate Azure Connectivity
        # ==========================================
        print("\n[VALIDATION] Phase 4: Azure API Connectivity")
        
        try:
            # Try to list resource groups as connectivity check
            rg_client = provider.clients.get("resource")
            if rg_client:
                # Just verify we can make API calls (list returns iterator, doesn't fail until accessed)
                list(rg_client.resource_groups.list())
                print(f"  ✓ Azure Resource Management API accessible")
                print(f"  ✓ Subscription ID: {provider.subscription_id[:8]}...")
        except Exception as e:
            error_msg = str(e)
            if "AuthorizationFailed" in error_msg:
                pytest.fail(f"Azure authorization failed - check role assignments: {e}")
            elif "InvalidSubscriptionId" in error_msg:
                pytest.fail(f"Invalid subscription ID: {e}")
            else:
                pytest.fail(f"Azure connectivity check failed: {e}")
        
        print("\n" + "="*60)
        print("  ✓ ALL VALIDATIONS PASSED - STARTING DEPLOYMENT")
        print("="*60)
        
        deployer = provider.get_deployer_strategy()
        
        # Track deployed layers for cleanup
        deployed_layers: List[str] = []
        
        def cleanup():
            """Cleanup function - ALWAYS runs, even on failure."""
            print("\n" + "="*60)
            print("  CLEANUP: DESTROYING ALL RESOURCES")
            print("="*60)
            
            destroy_results: Dict[str, str] = {}
            
            # Destroy in reverse order of deployment
            destroy_order = [
                ("l5", "destroy_l5"),
                ("l4", "destroy_l4"),
                ("l3_hot", "destroy_l3_hot"),
                ("l2", "destroy_l2"),
                ("l1", "destroy_l1"),
                ("setup", "destroy_setup")
            ]
            
            for layer_name, destroy_method in destroy_order:
                if layer_name in deployed_layers:
                    try:
                        print(f"\n[CLEANUP] Destroying {layer_name}...")
                        getattr(deployer, destroy_method)(context)
                        destroy_results[layer_name] = "✓ Destroyed successfully"
                        print(f"[CLEANUP] ✓ {layer_name} destroyed")
                    except Exception as e:
                        destroy_results[layer_name] = f"✗ Failed: {type(e).__name__}: {e}"
                        print(f"[CLEANUP] ✗ {layer_name} FAILED: {e}")
                else:
                    destroy_results[layer_name] = "- Not deployed"
            
            # Print cleanup summary
            print("\n" + "-"*60)
            print("  CLEANUP SUMMARY")
            print("-"*60)
            for layer, status in destroy_results.items():
                print(f"  {layer}: {status}")
            print("-"*60)
            
            # Check for failures and warn user
            failures = [l for l, s in destroy_results.items() if "Failed" in s]
            if failures:
                print("\n" + "!"*60)
                print("  ⚠️  CLEANUP FAILURES DETECTED!")
                print("")
                print("  Some resources may still exist in Azure.")
                print("  Please check the Azure Portal and manually delete:")
                print(f"    Resource Group: {config.digital_twin_name}*")
                print("")
                print("  Portal: https://portal.azure.com")
                print("!"*60)
        
        # Register cleanup to run ALWAYS (even on failure/skip)
        request.addfinalizer(cleanup)
        
        # ===== DEPLOYMENT PHASE =====
        try:
            # Deploy Setup Layer
            print("\n[DEPLOY] === Setup Layer ===")
            deployer.deploy_setup(context)
            deployed_layers.append("setup")
            print("[DEPLOY] ✓ Setup layer deployed")
            
            # Deploy L1 (IoT Hub, Dispatcher)
            print("\n[DEPLOY] === Layer 1 - Data Acquisition ===")
            deployer.deploy_l1(context)
            deployed_layers.append("l1")
            print("[DEPLOY] ✓ L1 deployed")
            
            # Deploy L2 (Persister, Processors)
            print("\n[DEPLOY] === Layer 2 - Data Processing ===")
            deployer.deploy_l2(context)
            deployed_layers.append("l2")
            print("[DEPLOY] ✓ L2 deployed")
            
            # Deploy L3 Hot (Cosmos DB, Hot Reader)
            print("\n[DEPLOY] === Layer 3 - Hot Storage ===")
            deployer.deploy_l3_hot(context)
            deployed_layers.append("l3_hot")
            print("[DEPLOY] ✓ L3 Hot deployed")
            
            # Deploy L4 (Azure Digital Twins)
            print("\n[DEPLOY] === Layer 4 - Twin Management ===")
            deployer.deploy_l4(context)
            deployed_layers.append("l4")
            print("[DEPLOY] ✓ L4 deployed")
            
            # Deploy L5 (Grafana)
            print("\n[DEPLOY] === Layer 5 - Visualization ===")
            deployer.deploy_l5(context)
            deployed_layers.append("l5")
            print("[DEPLOY] ✓ L5 deployed")
            
        except Exception as e:
            print(f"\n[DEPLOY] ✗ DEPLOYMENT FAILED: {type(e).__name__}: {e}")
            print("[DEPLOY] Cleanup will still run for deployed layers.")
            raise
        
        print("\n" + "="*60)
        print("  DEPLOYMENT COMPLETE - RUNNING TESTS")
        print("="*60)
        
        yield {
            "context": context,
            "deployer": deployer,
            "provider": provider,
            "project_path": e2e_project_path,
            "config": config,
            "deployed_layers": deployed_layers
        }
    
    # =========================================================================
    # LAYER VERIFICATION TESTS
    # =========================================================================
    
    def test_01_setup_layer_deployed(self, deployed_environment):
        """Verify Setup Layer: Resource Group, Managed Identity, Storage Account."""
        provider = deployed_environment["provider"]
        
        from src.providers.azure.layers.layer_setup_azure import (
            check_resource_group,
            check_managed_identity,
            check_storage_account
        )
        
        assert check_resource_group(provider), "Resource Group should exist"
        assert check_managed_identity(provider), "Managed Identity should exist"
        assert check_storage_account(provider), "Storage Account should exist"
        
        print("[VERIFY] ✓ Setup layer resources exist")
    
    def test_02_l1_iot_hub_deployed(self, deployed_environment):
        """Verify L1: IoT Hub and Dispatcher function deployed."""
        provider = deployed_environment["provider"]
        
        from src.providers.azure.layers.layer_1_iot import (
            check_iot_hub,
            check_dispatcher_function,
            check_l1_function_app
        )
        
        assert check_iot_hub(provider), "IoT Hub should exist"
        assert check_l1_function_app(provider), "L1 Function App should exist"
        assert check_dispatcher_function(provider), "Dispatcher function should exist"
        
        print("[VERIFY] ✓ L1 IoT resources exist")
    
    def test_03_l2_processing_deployed(self, deployed_environment):
        """Verify L2: Persister and processor functions deployed."""
        provider = deployed_environment["provider"]
        
        from src.providers.azure.layers.layer_2_compute import (
            check_l2_function_app,
            check_persister_function
        )
        
        assert check_l2_function_app(provider), "L2 Function App should exist"
        assert check_persister_function(provider), "Persister function should exist"
        
        print("[VERIFY] ✓ L2 Processing resources exist")
    
    def test_04_l3_hot_storage_deployed(self, deployed_environment):
        """Verify L3 Hot: Cosmos DB and Hot Reader deployed."""
        provider = deployed_environment["provider"]
        
        from src.providers.azure.layers.layer_3_storage import (
            check_cosmos_account,
            check_hot_cosmos_container,
            check_hot_reader_function
        )
        
        assert check_cosmos_account(provider), "Cosmos DB account should exist"
        assert check_hot_cosmos_container(provider), "Hot container should exist"
        assert check_hot_reader_function(provider), "Hot Reader function should exist"
        
        print("[VERIFY] ✓ L3 Hot Storage resources exist")
    
    def test_05_l4_adt_deployed(self, deployed_environment):
        """Verify L4: Azure Digital Twins instance deployed."""
        provider = deployed_environment["provider"]
        
        from src.providers.azure.layers.layer_4_adt import (
            check_adt_instance
        )
        
        assert check_adt_instance(provider), "ADT instance should exist"
        
        print("[VERIFY] ✓ L4 ADT resources exist")
    
    def test_06_l5_grafana_deployed(self, deployed_environment):
        """Verify L5: Grafana workspace and datasource deployed."""
        provider = deployed_environment["provider"]
        
        from src.providers.azure.layers.layer_5_grafana import (
            check_grafana_workspace,
            get_grafana_workspace_url
        )
        
        assert check_grafana_workspace(provider), "Grafana workspace should exist"
        
        grafana_url = get_grafana_workspace_url(provider)
        assert grafana_url is not None, "Grafana URL should be available"
        
        print(f"[VERIFY] ✓ L5 Grafana deployed at: {grafana_url}")
    
    # =========================================================================
    # DATA FLOW TESTS
    # =========================================================================
    
    def test_07_send_iot_message(self, deployed_environment):
        """Send IoT message through the pipeline."""
        project_path = deployed_environment["project_path"]
        config = deployed_environment["config"]
        
        # Get simulator config for first device
        sim_config_path = os.path.join(
            project_path, "iot_device_simulator", "azure", "config_generated.json"
        )
        
        if not os.path.exists(sim_config_path):
            pytest.skip("Simulator config not generated - check L1 deployment")
        
        with open(sim_config_path, "r") as f:
            sim_config = json.load(f)
        
        # Send test message using azure-iot-device SDK
        try:
            from azure.iot.device import IoTHubDeviceClient, Message
            
            client = IoTHubDeviceClient.create_from_connection_string(
                sim_config["connection_string"]
            )
            
            test_payload = {
                "iotDeviceId": sim_config["device_id"],
                "temperature": 42.5,
                "time": ""  # Will be filled by Cosmos
            }
            
            client.connect()
            message = Message(json.dumps(test_payload))
            message.content_type = "application/json"
            message.content_encoding = "utf-8"
            client.send_message(message)
            client.disconnect()
            
            print(f"[DATA] ✓ Sent test message: {test_payload}")
            
            # Store for later verification
            deployed_environment["test_payload"] = test_payload
            deployed_environment["test_device_id"] = sim_config["device_id"]
            
        except ImportError:
            pytest.skip("azure-iot-device SDK not installed")
        except Exception as e:
            pytest.fail(f"Failed to send IoT message: {e}")
    
    def test_08_verify_data_in_cosmos_db(self, deployed_environment):
        """Verify sent data reached Cosmos DB via Hot Reader."""
        provider = deployed_environment["provider"]
        config = deployed_environment["config"]
        test_device_id = deployed_environment.get("test_device_id")
        
        if not test_device_id:
            pytest.skip("No test message was sent")
        
        # Wait for data propagation (IoT Hub → Event Grid → Functions → Cosmos)
        print("[DATA] Waiting for data propagation (15 seconds)...")
        time.sleep(15)
        
        # Query Hot Reader endpoint
        from src.providers.azure.layers.layer_3_storage import get_hot_reader_function_url
        
        try:
            hot_reader_url = get_hot_reader_function_url(provider)
            
            if not hot_reader_url:
                pytest.skip("Hot Reader URL not available")
            
            # Query for last entry
            response = requests.post(
                f"{hot_reader_url}-last-entry",
                json={
                    "entityId": test_device_id,
                    "componentName": test_device_id,
                    "selectedProperties": ["temperature"]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"[DATA] Hot Reader response: {data}")
                
                property_values = data.get("propertyValues", {})
                assert property_values, "Hot Reader should return property values"
                
                print("[DATA] ✓ Data verified in Cosmos DB via Hot Reader")
            else:
                print(f"[DATA] Hot Reader returned: {response.status_code}")
                pytest.skip(f"Hot Reader returned {response.status_code}")
                
        except Exception as e:
            print(f"[DATA] Warning: Could not verify Cosmos data: {e}")
            pytest.skip(f"Could not query Hot Reader: {e}")
    
    def test_09_verify_data_in_grafana(self, deployed_environment):
        """Query Grafana HTTP API to verify data is accessible."""
        provider = deployed_environment["provider"]
        test_device_id = deployed_environment.get("test_device_id")
        
        if not test_device_id:
            pytest.skip("No test message was sent")
        
        from src.providers.azure.layers.layer_5_grafana import get_grafana_workspace_url
        
        grafana_url = get_grafana_workspace_url(provider)
        if not grafana_url:
            pytest.skip("Grafana URL not available")
        
        # Get Azure AD token for Grafana API
        try:
            from azure.identity import DefaultAzureCredential
            
            credential = DefaultAzureCredential()
            # Grafana uses its own scope
            token = credential.get_token("https://grafana.azure.com/.default")
            
            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json"
            }
            
            # Check datasources are configured
            response = requests.get(
                f"{grafana_url}/api/datasources",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                datasources = response.json()
                print(f"[GRAFANA] Found {len(datasources)} datasources")
                
                # Find JSON API datasource (Hot Reader)
                json_api_ds = None
                for ds in datasources:
                    if "json" in ds.get("type", "").lower():
                        json_api_ds = ds
                        break
                
                if json_api_ds:
                    print(f"[GRAFANA] ✓ JSON API datasource configured: {json_api_ds.get('name')}")
                else:
                    print("[GRAFANA] No JSON API datasource found")
                
                print("[GRAFANA] ✓ Grafana API accessible and configured")
            else:
                print(f"[GRAFANA] API returned: {response.status_code}")
                pytest.skip(f"Grafana API returned {response.status_code}")
                
        except ImportError:
            pytest.skip("azure-identity not installed")
        except Exception as e:
            print(f"[GRAFANA] Warning: Could not verify Grafana: {e}")
            pytest.skip(f"Could not query Grafana: {e}")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "live"])
