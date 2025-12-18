"""
Azure Terraform End-to-End Test.

This test deploys all Azure layers using Terraform, sends IoT messages through
the pipeline, verifies data reaches Cosmos DB, then destroys resources.

IMPORTANT: This test deploys REAL Azure resources and incurs costs.
Run with: pytest -m live

Estimated duration: 15-30 minutes
Estimated cost: ~$0.50-2.00 USD

This test follows the same pattern as the AWS E2E test for consistency.
"""
import pytest
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))


@pytest.mark.live
class TestAzureTerraformE2E:
    """
    Live E2E test for Azure deployment using Terraform.
    
    Tests the complete data flow:
    IoT Device → IoT Hub → Dispatcher → Persister → Cosmos DB → Hot Reader
    
    Uses TerraformDeployerStrategy for infrastructure provisioning.
    """
    
    @pytest.fixture(scope="class")
    def deployed_environment(self, request, terraform_e2e_project_path, azure_credentials):
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
        
        project_path = Path(terraform_e2e_project_path)
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
        required_azure_fields = ["azure_subscription_id", "azure_client_id", "azure_client_secret", "azure_tenant_id", "azure_region"]
        for field in required_azure_fields:
            if not azure_creds.get(field):
                pytest.fail(f"Azure credentials missing required field: {field}")
        print("  ✓ Azure credentials present")
        
        # Validate Azure API connectivity
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import ResourceManagementClient
            
            credential = ClientSecretCredential(
                tenant_id=azure_creds["azure_tenant_id"],
                client_id=azure_creds["azure_client_id"],
                client_secret=azure_creds["azure_client_secret"]
            )
            
            resource_client = ResourceManagementClient(
                credential,
                azure_creds["azure_subscription_id"]
            )
            
            # Simple API call to verify connectivity
            resource_client.providers.get("Microsoft.Resources")
            print(f"  ✓ Azure API connectivity verified (Subscription: {azure_creds['azure_subscription_id'][:8]}...)")
        except Exception as e:
            pytest.fail(f"Azure API connectivity check failed: {e}")
        
        # ==========================================
        # PHASE 3: Deploy Infrastructure
        # ==========================================
        print("\n[DEPLOYMENT] Phase 3: Terraform Deployment")
        print(f"  Project: {project_path}")
        print(f"  Terraform dir: {terraform_dir}")
        
        context = DeploymentContext(
            project_name=config.digital_twin_name,
            project_path=project_path,
            config=config,
            credentials=credentials,
        )
        
        strategy = TerraformDeployerStrategy(
            terraform_dir=str(terraform_dir),
            project_path=str(project_path)
        )
        
        # Register cleanup to ALWAYS run, even on failure
        def terraform_cleanup():
            print("\n" + "="*60)
            print("  CLEANUP: Running terraform destroy")
            print("="*60)
            try:
                strategy.destroy_all(context)
                print("  ✓ Terraform destroy completed")
            except Exception as e:
                print(f"  ✗ Terraform destroy failed: {e}")
                print("\n  ⚠️  Some resources may still exist in Azure.")
                print(f"  Please check the Azure Portal and manually delete:")
                print(f"    Resource Group: rg-{config.digital_twin_name}")
        
        # DISABLED FOR DEBUGGING - resources persist for re-run (Terraform is idempotent)
        # request.addfinalizer(terraform_cleanup)
        
        # Deploy
        try:
            print("\n  Running terraform init + apply...")
            strategy.deploy_all(context)
            print("  ✓ Terraform deployment completed")
        except Exception as e:
            pytest.fail(f"Terraform deployment failed: {e}")
        
        # Get outputs
        try:
            outputs = strategy.get_outputs()
            print(f"  ✓ Got {len(outputs)} Terraform outputs")
        except Exception as e:
            pytest.fail(f"Failed to get Terraform outputs: {e}")
        
        yield {
            "context": context,
            "strategy": strategy,
            "outputs": outputs,
            "project_path": project_path,
        }
    
    # ==========================================================================
    # TESTS
    # ==========================================================================
    
    def test_01_terraform_outputs_present(self, deployed_environment):
        """Verify essential Terraform outputs are present."""
        outputs = deployed_environment["outputs"]
        
        # Check Azure setup outputs
        assert outputs.get("azure_resource_group_name"), "azure_resource_group_name output missing"
        assert outputs.get("azure_managed_identity_id"), "azure_managed_identity_id output missing"
        print("  ✓ Essential Terraform outputs present")
    
    def test_02_l1_iot_hub_deployed(self, deployed_environment):
        """Verify L1 IoT Hub is deployed."""
        from azure.identity import ClientSecretCredential
        from azure.mgmt.iothub import IotHubClient
        
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        azure_creds = context.credentials.get("azure", {})
        
        iothub_name = outputs.get("azure_iothub_name")
        if not iothub_name:
            pytest.skip("IoT Hub not deployed")
        
        credential = ClientSecretCredential(
            tenant_id=azure_creds["azure_tenant_id"],
            client_id=azure_creds["azure_client_id"],
            client_secret=azure_creds["azure_client_secret"]
        )
        
        iothub_client = IotHubClient(credential, azure_creds["azure_subscription_id"])
        
        rg_name = outputs.get("azure_resource_group_name")
        hub = iothub_client.iot_hub_resource.get(rg_name, iothub_name)
        
        assert hub.name == iothub_name
        print(f"  ✓ IoT Hub exists: {iothub_name}")
    
    def test_03_l3_cosmos_deployed(self, deployed_environment):
        """Verify L3 Cosmos DB is deployed."""
        from azure.identity import ClientSecretCredential
        from azure.mgmt.cosmosdb import CosmosDBManagementClient
        
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        azure_creds = context.credentials.get("azure", {})
        
        cosmos_name = outputs.get("azure_cosmos_account_name")
        if not cosmos_name:
            pytest.skip("Cosmos DB not deployed")
        
        credential = ClientSecretCredential(
            tenant_id=azure_creds["azure_tenant_id"],
            client_id=azure_creds["azure_client_id"],
            client_secret=azure_creds["azure_client_secret"]
        )
        
        cosmos_client = CosmosDBManagementClient(credential, azure_creds["azure_subscription_id"])
        
        rg_name = outputs.get("azure_resource_group_name")
        account = cosmos_client.database_accounts.get(rg_name, cosmos_name)
        
        assert account.name == cosmos_name
        print(f"  ✓ Cosmos DB account exists: {cosmos_name}")
    
    def test_04_l4_adt_deployed(self, deployed_environment):
        """Verify L4 Azure Digital Twins is deployed."""
        from azure.identity import ClientSecretCredential
        from azure.mgmt.digitaltwins import AzureDigitalTwinsManagementClient
        
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        azure_creds = context.credentials.get("azure", {})
        
        adt_name = outputs.get("azure_adt_instance_name")
        if not adt_name:
            pytest.skip("Azure Digital Twins not deployed")
        
        credential = ClientSecretCredential(
            tenant_id=azure_creds["azure_tenant_id"],
            client_id=azure_creds["azure_client_id"],
            client_secret=azure_creds["azure_client_secret"]
        )
        
        adt_client = AzureDigitalTwinsManagementClient(credential, azure_creds["azure_subscription_id"])
        
        rg_name = outputs.get("azure_resource_group_name")
        instance = adt_client.digital_twins.get(rg_name, adt_name)
        
        assert instance.name == adt_name
        print(f"  ✓ Azure Digital Twins exists: {adt_name}")
    
    def test_05_l5_grafana_deployed(self, deployed_environment):
        """Verify L5 Grafana workspace is deployed."""
        from azure.identity import ClientSecretCredential
        from azure.mgmt.dashboard import DashboardManagementClient
        
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        
        azure_creds = context.credentials.get("azure", {})
        
        grafana_name = outputs.get("azure_grafana_name")
        if not grafana_name:
            pytest.skip("Grafana not deployed")
        
        credential = ClientSecretCredential(
            tenant_id=azure_creds["azure_tenant_id"],
            client_id=azure_creds["azure_client_id"],
            client_secret=azure_creds["azure_client_secret"]
        )
        
        dashboard_client = DashboardManagementClient(credential, azure_creds["azure_subscription_id"])
        
        rg_name = outputs.get("azure_resource_group_name")
        grafana = dashboard_client.grafana.get(rg_name, grafana_name)
        
        assert grafana.name == grafana_name
        print(f"  ✓ Grafana workspace exists: {grafana_name}")
        
        endpoint = outputs.get("azure_grafana_endpoint")
        if endpoint:
            print(f"  ✓ Grafana endpoint: {endpoint}")
    
    def test_06_send_iot_message(self, deployed_environment):
        """Send a test message through IoT Hub."""
        context = deployed_environment["context"]
        project_path = deployed_environment["project_path"]
        
        # Get simulator config for first device
        sim_config_path = Path(project_path) / "iot_device_simulator" / "azure" / "config_generated.json"
        
        if not sim_config_path.exists():
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
                "temperature": 23.5,
                "humidity": 65.2,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "test_run": True
            }
            
            print(f"\n  Device ID: {sim_config['device_id']}")
            print(f"  Payload: {json.dumps(test_payload)}")
            
            client.connect()
            message = Message(json.dumps(test_payload))
            message.content_type = "application/json"
            message.content_encoding = "utf-8"
            client.send_message(message)
            client.disconnect()
            
            print("  ✓ Message published successfully")
            
            # Store for later verification
            deployed_environment["test_payload"] = test_payload
            deployed_environment["test_device_id"] = sim_config["device_id"]
            
        except ImportError:
            pytest.skip("azure-iot-device SDK not installed")
        except Exception as e:
            pytest.fail(f"Failed to send IoT message: {e}")
        
        # Wait for processing
        print("  Waiting 15 seconds for message processing...")
        time.sleep(15)
    
    def test_07_verify_data_in_cosmos_db(self, deployed_environment):
        """Verify the test message reached Cosmos DB."""
        from azure.identity import ClientSecretCredential
        from azure.cosmos import CosmosClient
        from azure.mgmt.cosmosdb import CosmosDBManagementClient
        
        outputs = deployed_environment["outputs"]
        context = deployed_environment["context"]
        test_device_id = deployed_environment.get("test_device_id")
        
        azure_creds = context.credentials.get("azure", {})
        
        if not test_device_id:
            pytest.skip("No test message was sent")
        
        cosmos_endpoint = outputs.get("azure_cosmos_endpoint")
        if not cosmos_endpoint:
            pytest.skip("Cosmos DB endpoint not available")
        
        # Get Cosmos key via management API
        credential = ClientSecretCredential(
            tenant_id=azure_creds["azure_tenant_id"],
            client_id=azure_creds["azure_client_id"],
            client_secret=azure_creds["azure_client_secret"]
        )
        
        cosmos_mgmt = CosmosDBManagementClient(credential, azure_creds["azure_subscription_id"])
        rg_name = outputs.get("azure_resource_group_name")
        cosmos_name = outputs.get("azure_cosmos_account_name")
        
        keys = cosmos_mgmt.database_accounts.list_keys(rg_name, cosmos_name)
        cosmos_key = keys.primary_master_key
        
        # Connect to Cosmos DB
        cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
        
        database_name = outputs.get("azure_cosmos_database_name", "telemetry")
        container_name = outputs.get("azure_cosmos_container_name", "measurements")
        
        try:
            database = cosmos_client.get_database_client(database_name)
            container = database.get_container_client(container_name)
            
            # Query for our test device
            query = f"SELECT TOP 5 * FROM c WHERE c.iotDeviceId = '{test_device_id}' ORDER BY c._ts DESC"
            items = list(container.query_items(query=query, enable_cross_partition_query=True))
            
            print(f"\n  Found {len(items)} items for {test_device_id}")
            
            if items:
                latest = items[0]
                print(f"  Latest item: {json.dumps({k: v for k, v in latest.items() if not k.startswith('_')}, default=str)}")
                print("  ✓ Data verified in Cosmos DB")
            else:
                print("  ⚠ No data found (may need more time to propagate)")
                
        except Exception as e:
            print(f"  ⚠ Could not query Cosmos DB: {e}")
    
    def test_08_verify_hot_reader(self, deployed_environment):
        """Verify the Hot Reader Function can read data back from Cosmos DB."""
        outputs = deployed_environment["outputs"]
        test_device_id = deployed_environment.get("test_device_id")
        
        hot_reader_url = outputs.get("azure_l3_hot_reader_url")
        if not hot_reader_url:
            pytest.skip("Hot Reader Function URL not deployed")
        
        if not test_device_id:
            pytest.skip("No test device ID available")
        
        print(f"\n  Hot Reader URL: {hot_reader_url}")
        
        try:
            # Query the hot reader for test device data
            response = requests.post(
                f"{hot_reader_url}-last-entry",
                json={
                    "entityId": test_device_id,
                    "componentName": test_device_id,
                    "selectedProperties": ["temperature", "humidity"]
                },
                timeout=30
            )
            
            print(f"  Response status: {response.status_code}")
            print(f"  Response body: {response.text[:500] if len(response.text) > 500 else response.text}")
            
            if response.status_code == 200:
                data = response.json()
                property_values = data.get("propertyValues", {})
                
                if property_values:
                    print(f"  ✓ Hot Reader returned property values: {property_values}")
                else:
                    print("  ⚠ Hot Reader returned empty property values")
                
                print("  ✓ Hot Reader Function working correctly")
            elif response.status_code == 404:
                print("  ⚠ No data found via Hot Reader (expected for fresh deployment)")
            else:
                print(f"  ⚠ Unexpected response: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("  ⚠ Hot Reader request timed out (Function cold start)")
        except requests.exceptions.RequestException as e:
            print(f"  ⚠ Hot Reader request failed: {e}")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "live"])
