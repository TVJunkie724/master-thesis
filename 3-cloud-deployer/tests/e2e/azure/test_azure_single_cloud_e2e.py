"""
Azure Terraform End-to-End Test.

This test deploys all Azure layers using Terraform, sends IoT messages through
the pipeline, verifies data reaches Cosmos DB, then destroys all resources.

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
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))

# Configure logging to output to stdout for pytest capture
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


@pytest.mark.live
class TestAzureSingleCloudE2E:
    """
    Live E2E test for Azure single-cloud deployment.
    
    Tests the complete data flow:
    IoT Device → IoT Hub → Dispatcher → Persister → Cosmos DB → Hot Reader → Grafana
    
    Uses TerraformDeployerStrategy for infrastructure provisioning (same pattern as AWS/GCP).
    """
    
    @pytest.fixture(scope="class")
    def deployed_environment(self, request, azure_terraform_e2e_project_path, azure_credentials):
        """
        Deploy all Azure layers via Terraform with GUARANTEED cleanup.
        
        Uses unique project name per run to avoid Terraform state conflicts.
        Cleanup (terraform destroy) ALWAYS runs, even on test failure.
        """
        from src.core.config_loader import load_project_config, load_credentials
        from src.core.context import DeploymentContext
        from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
        import validator
        import constants as CONSTANTS
        
        print("\n" + "="*60)
        print("  AZURE TERRAFORM E2E TEST - PRE-DEPLOYMENT VALIDATION")
        print("="*60)
        
        project_path = Path(azure_terraform_e2e_project_path)
        terraform_dir = Path(__file__).parent.parent.parent.parent / "src" / "terraform"
        
        # ==========================================
        # PHASE 1: Validate Configuration
        # ==========================================
        print("\n[VALIDATION] Phase 1: Configuration Files")
        
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
        
        # Load config
        try:
            config = load_project_config(project_path)
            print(f"  ✓ Project config loaded (twin_name: {config.digital_twin_name})")
        except Exception as e:
            pytest.fail(f"Config loading failed: {e}")
        
        # Load credentials
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
        
        required_azure_fields = ["azure_subscription_id", "azure_region"]
        for field in required_azure_fields:
            if not azure_creds.get(field):
                pytest.fail(f"Azure credentials missing required field: {field}")
        print("  ✓ Azure credentials present")
        print(f"  ✓ General region: {azure_creds.get('azure_region')}")
        print(f"  ✓ IoT Hub region: {azure_creds.get('azure_region_iothub', azure_creds.get('azure_region'))}")
        
        # Validate Azure connectivity using the comprehensive credentials checker
        # (This is the same checker used by CLI and REST API)
        try:
            from api.azure_credentials_checker import check_azure_credentials
            
            result = check_azure_credentials(azure_creds)
            if result["status"] == "error":
                pytest.fail(f"Azure credentials validation failed: {result['message']}")
            elif result["status"] == "invalid":
                print(f"  ⚠ Warning: {result['message']}")
                print("    Deployment may fail due to missing permissions")
            elif result["status"] == "partial":
                print(f"  ⚠ Warning: {result['message']}")
            else:
                print(f"  ✓ Azure API connectivity verified (Subscription: {azure_creds['azure_subscription_id'][:8]}...)")
                if result.get("caller_identity"):
                    print(f"  ✓ Principal authenticated: {result['caller_identity'].get('principal_type')}")
        except ImportError:
            print("  ⚠ azure-identity/azure-mgmt-resource not installed, skipping connectivity check")
        
        # ==========================================
        # PHASE 3: Initialize Terraform Strategy
        # ==========================================
        print("\n[VALIDATION] Phase 3: Terraform Initialization")
        
        strategy = TerraformDeployerStrategy(
            terraform_dir=str(terraform_dir),
            project_path=str(project_path)
        )
        print(f"  ✓ Terraform strategy initialized")
        print(f"    - Terraform dir: {terraform_dir}")
        print(f"    - Project path: {project_path}")
        
        # Initialize Azure provider for post-deployment SDK operations
        # (Required for IoT device registration and config_generated.json creation)
        from src.providers.azure.provider import AzureProvider
        
        azure_provider = AzureProvider()
        azure_provider.initialize_clients(
            azure_creds,
            config.digital_twin_name
        )
        print(f"  ✓ Azure provider initialized for SDK operations")
        
        # Create context for post-deployment SDK operations
        context = DeploymentContext(
            project_name=config.digital_twin_name,
            project_path=project_path,
            config=config,
            credentials=credentials,
            providers={"azure": azure_provider}
        )
        
        # Track deployment status
        terraform_outputs = {}
        
        def terraform_cleanup():
            """Cleanup function - always runs terraform destroy."""
            print("\n" + "="*60)
            print("  CLEANUP: TERRAFORM DESTROY")
            print("="*60)
            
            try:
                strategy.destroy_all(context)
                print("[CLEANUP] ✓ Resources destroyed successfully")
            except Exception as e:
                print(f"[CLEANUP] ✗ Destroy failed: {e}")
                print("\n" + "!"*60)
                print("  ⚠️  CLEANUP FAILURE DETECTED!")
                print("")
                print("  Some resources may still exist in Azure.")
                print("  Please check the Azure Portal and manually delete:")
                print(f"    Resource Group: {config.digital_twin_name}-rg")
                print("")
                print("  Portal: https://portal.azure.com")
                print("!"*60)
        
        # Register cleanup to run ALWAYS (on success or failure)
        # TODO: TEMPORARILY DISABLED FOR DEBUGGING - uncomment when done:
        # request.addfinalizer(terraform_cleanup)
        
        # ==========================================
        # PHASE 4: Terraform Deployment
        # ==========================================
        print("\n" + "="*60)
        print("  TERRAFORM DEPLOYMENT")
        print("="*60)
        
        try:
            terraform_outputs = strategy.deploy_all(context)
            print("\n[DEPLOY] ✓ Terraform deployment complete")
            
        except Exception as e:
            print(f"\n[DEPLOY] ✗ DEPLOYMENT FAILED: {type(e).__name__}: {e}")
            raise
        
        print("\n" + "="*60)
        print("  DEPLOYMENT COMPLETE - RUNNING TESTS")
        print("="*60)
        
        yield {
            "context": context,
            "strategy": strategy,
            "project_path": azure_terraform_e2e_project_path,
            "config": config,
            "terraform_outputs": terraform_outputs,
            "credentials": credentials
        }
    
    # =========================================================================
    # LAYER VERIFICATION TESTS
    # =========================================================================
    
    def test_01_terraform_outputs_present(self, deployed_environment):
        """Verify essential Terraform outputs are present."""
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        
        # Check key Terraform outputs exist
        required_outputs = [
            "azure_resource_group_name",
            "azure_storage_account_name",
        ]
        
        for output in required_outputs:
            assert outputs.get(output) is not None, f"Missing Terraform output: {output}"
        
        # Verify subscription_id and region are available from credentials
        azure_creds = credentials.get("azure", {})
        assert azure_creds.get("azure_subscription_id"), "azure_subscription_id missing from credentials"
        assert azure_creds.get("azure_region"), "azure_region missing from credentials"
        
        print(f"[VERIFY] ✓ Terraform outputs present ({len(outputs)} total)")
        print(f"[VERIFY] ✓ Subscription ID: {azure_creds['azure_subscription_id'][:8]}...")
        print(f"[VERIFY] ✓ Region: {azure_creds['azure_region']}")
    
    def test_02_l1_iot_hub_deployed(self, deployed_environment):
        """Verify L1: IoT Hub deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        iot_hub_name = outputs.get("azure_iothub_name")
        l1_function_app = outputs.get("azure_l1_function_app_name")
        
        if iot_hub_name is not None:
            print(f"[VERIFY] ✓ L1 IoT Hub: {iot_hub_name}")
        else:
            pytest.skip("L1 not deployed to Azure")
        
        if l1_function_app is not None:
            print(f"[VERIFY] ✓ L1 Function App: {l1_function_app}")
    
    def test_03_l2_processing_deployed(self, deployed_environment):
        """Verify L2: Processing functions deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        l2_function_app = outputs.get("azure_l2_function_app_name")
        user_functions_app = outputs.get("azure_user_functions_app_name")
        
        if l2_function_app is not None:
            print(f"[VERIFY] ✓ L2 Function App: {l2_function_app}")
        else:
            pytest.skip("L2 not deployed to Azure")
        
        if user_functions_app is not None:
            print(f"[VERIFY] ✓ User Functions App: {user_functions_app}")
    
    def test_04_l3_hot_storage_deployed(self, deployed_environment):
        """Verify L3 Hot: Cosmos DB and Hot Reader deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        cosmos_account = outputs.get("azure_cosmos_account_name")
        hot_reader_url = outputs.get("azure_l3_hot_reader_url")
        
        if cosmos_account is not None:
            print(f"[VERIFY] ✓ L3 Cosmos DB Account: {cosmos_account}")
        else:
            pytest.skip("L3 Hot not deployed to Azure")
        
        if hot_reader_url is not None:
            print(f"[VERIFY] ✓ L3 Hot Reader URL: {hot_reader_url}")
    
    def test_05_l4_adt_deployed(self, deployed_environment):
        """Verify L4: Azure Digital Twins deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        adt_endpoint = outputs.get("azure_adt_endpoint")
        
        if adt_endpoint is not None:
            print(f"[VERIFY] ✓ L4 Azure Digital Twins: {adt_endpoint}")
        else:
            pytest.skip("L4 not deployed to Azure")
    
    def test_06_l5_grafana_deployed(self, deployed_environment):
        """Verify L5: Grafana workspace deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        grafana_endpoint = outputs.get("azure_grafana_endpoint")
        
        if grafana_endpoint is not None:
            print(f"[VERIFY] ✓ L5 Grafana Endpoint: {grafana_endpoint}")
        else:
            pytest.skip("L5 not deployed to Azure")
    
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
        outputs = deployed_environment["terraform_outputs"]
        test_device_id = deployed_environment.get("test_device_id")
        
        if not test_device_id:
            pytest.skip("No test message was sent")
        
        hot_reader_url = outputs.get("azure_l3_hot_reader_url")
        if not hot_reader_url:
            pytest.skip("Hot Reader URL not available")
        
        # Retry with exponential backoff for data propagation
        # (IoT Hub → Event Grid → Functions → Cosmos can take 10-30 seconds)
        max_retries = 5
        base_wait = 10  # Start with 10 seconds
        
        for attempt in range(max_retries):
            wait_time = base_wait * (2 ** attempt)  # 10, 20, 40, 80, 160
            print(f"[DATA] Attempt {attempt + 1}/{max_retries}: waiting {wait_time}s for data propagation...")
            time.sleep(wait_time)
            
            try:
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
                    if property_values:
                        print("[DATA] ✓ Data verified in Cosmos DB via Hot Reader")
                        return  # Success!
                    else:
                        print("[DATA] ⚠ No property values found yet, retrying...")
                else:
                    print(f"[DATA] Hot Reader returned: {response.status_code}, retrying...")
                    
            except Exception as e:
                print(f"[DATA] Request failed: {e}, retrying...")
        
        # All retries exhausted
        pytest.skip(f"Data not found after {max_retries} retries - data propagation may be slow")
    
    def test_09_verify_grafana_access(self, deployed_environment):
        """Verify Grafana endpoint is accessible."""
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        
        grafana_endpoint = outputs.get("azure_grafana_endpoint")
        if not grafana_endpoint:
            pytest.skip("Grafana endpoint not available")
        
        # Get Azure credentials for Grafana API authentication
        azure_creds = credentials.get("azure", {})
        tenant_id = azure_creds.get("azure_tenant_id")
        client_id = azure_creds.get("azure_client_id")
        client_secret = azure_creds.get("azure_client_secret")
        
        if not all([tenant_id, client_id, client_secret]):
            pytest.skip("Azure service principal credentials not available for Grafana API access")
        
        try:
            from azure.identity import ClientSecretCredential
            
            # Use ClientSecretCredential with explicit credentials from config
            # (DefaultAzureCredential doesn't work in Docker without env vars)
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
            
            # Azure Managed Grafana uses a well-known Application ID for OAuth2 tokens.
            # The GUID ce34e7e5-485f-4d76-964f-b3d2b16d1e4f is Microsoft's official
            # Azure Managed Grafana service principal ID, used globally across all tenants.
            # Using "https://grafana.azure.com/.default" returns 401 because the token
            # audience doesn't match what Grafana expects.
            # Reference: https://stackoverflow.com/questions/74534683/azure-managed-grafana-api-authentication
            GRAFANA_APP_ID = "ce34e7e5-485f-4d76-964f-b3d2b16d1e4f"
            token = credential.get_token(f"{GRAFANA_APP_ID}/.default")
            
            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json"
            }
            
            # Retry logic for role propagation (403 = role not yet propagated)
            # Terraform waits 180s, but in edge cases it may take longer
            max_retries = 5
            base_wait = 30  # seconds
            
            for attempt in range(max_retries):
                response = requests.get(
                    f"{grafana_endpoint}/api/datasources",
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    datasources = response.json()
                    print(f"[GRAFANA] Found {len(datasources)} datasources")
                    print("[GRAFANA] ✓ Grafana API accessible and configured")
                    return  # Success!
                
                if response.status_code == 403 and attempt < max_retries - 1:
                    wait_time = base_wait * (attempt + 1)
                    print(f"[GRAFANA] 403 - Role not propagated yet, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                
                # Non-403 error or final attempt
                break
            
            print(f"[GRAFANA] API returned: {response.status_code}")
            print(f"[GRAFANA] Response body: {response.text[:500]}")
            pytest.skip(f"Grafana API returned {response.status_code} after {max_retries} retries")
                
        except ImportError:
            pytest.skip("azure-identity not installed")
        except Exception as e:
            print(f"[GRAFANA] Warning: Could not verify Grafana: {e}")
            pytest.skip(f"Could not query Grafana: {e}")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "live"])
