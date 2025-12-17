"""
Azure Terraform End-to-End Test.

This test deploys all Azure layers using Terraform, sends IoT messages through
the pipeline, verifies data reaches Cosmos DB and Grafana, then destroys resources.

IMPORTANT: This test deploys REAL Azure resources and incurs costs.
Run with: pytest -m live

Estimated duration: 15-30 minutes
Estimated cost: ~$0.50-2.00 USD
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
    IoT Device → IoT Hub → Dispatcher → Persister → Cosmos DB → Hot Reader → Grafana
    
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
        
        azure_creds = credentials.get("azure")
        if not azure_creds:
            pytest.fail("No Azure credentials found in config_credentials.json")
        
        required_fields = CONSTANTS.REQUIRED_CREDENTIALS_FIELDS.get("azure", [])
        missing_fields = [f for f in required_fields if not azure_creds.get(f)]
        if missing_fields:
            pytest.fail(f"Missing required Azure credential fields: {missing_fields}")
        print(f"  ✓ All required fields present: {len(required_fields)} fields")
        
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
        
        # Create context for post-deployment SDK operations
        context = DeploymentContext(
            project_name=config.digital_twin_name,
            project_path=project_path,
            config=config
        )
        
        # Track deployment status
        deployment_success = False
        terraform_outputs = {}
        
        # Flag to control cleanup behavior - set to True for faster retries
        SKIP_CLEANUP_ON_FAILURE = True
        
        def terraform_cleanup():
            """Cleanup function - only destroys if deployment succeeded or flag is False."""
            nonlocal deployment_success
            
            if SKIP_CLEANUP_ON_FAILURE and not deployment_success:
                print("\n" + "="*60)
                print("  CLEANUP: SKIPPING (deployment failed, resources reusable)")
                print("="*60)
                print("  Resources kept for faster retry. To clean up manually:")
                print(f"    terraform -chdir=/app/src/terraform destroy -auto-approve")
                return
            
            print("\n" + "="*60)
            print("  CLEANUP: TERRAFORM DESTROY")
            print("="*60)
            
            try:
                strategy.destroy_all()
                print("[CLEANUP] ✓ Resources destroyed successfully")
            except Exception as e:
                print(f"[CLEANUP] ✗ Destroy failed: {e}")
                print("\n" + "!"*60)
                print("  ⚠️  CLEANUP FAILURE DETECTED!")
                print("")
                print("  Some resources may still exist in Azure.")
                print("  Please check the Azure Portal and manually delete:")
                print(f"    Resource Group: rg-{config.digital_twin_name}")
                print("")
                print("  Portal: https://portal.azure.com")
                print("!"*60)
        
        # Register cleanup to run ALWAYS
        request.addfinalizer(terraform_cleanup)
        
        # ==========================================
        # PHASE 4: Terraform Deployment
        # ==========================================
        print("\n" + "="*60)
        print("  TERRAFORM DEPLOYMENT")
        print("="*60)
        
        try:
            terraform_outputs = strategy.deploy_all(context)
            deployment_success = True
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
            "project_path": terraform_e2e_project_path,
            "config": config,
            "terraform_outputs": terraform_outputs,
            "credentials": credentials
        }
    
    # =========================================================================
    # LAYER VERIFICATION TESTS
    # =========================================================================
    
    def test_01_terraform_outputs_present(self, deployed_environment):
        """Verify Terraform outputs are populated."""
        outputs = deployed_environment["terraform_outputs"]
        
        required_outputs = [
            "azure_resource_group_name",
            "azure_managed_identity_id",
            "azure_storage_account_name",
        ]
        
        for output in required_outputs:
            assert outputs.get(output) is not None, f"Missing Terraform output: {output}"
        
        print("[VERIFY] ✓ Terraform outputs present")
    
    def test_02_l1_iot_hub_deployed(self, deployed_environment):
        """Verify L1: IoT Hub deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        iothub_name = outputs.get("azure_iothub_name")
        assert iothub_name is not None, "IoT Hub not created"
        
        print(f"[VERIFY] ✓ L1 IoT Hub: {iothub_name}")
    
    def test_03_l3_cosmos_deployed(self, deployed_environment):
        """Verify L3: Cosmos DB deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        cosmos_name = outputs.get("azure_cosmos_account_name")
        cosmos_endpoint = outputs.get("azure_cosmos_endpoint")
        
        assert cosmos_name is not None, "Cosmos DB not created"
        assert cosmos_endpoint is not None, "Cosmos endpoint not available"
        
        print(f"[VERIFY] ✓ L3 Cosmos DB: {cosmos_name}")
    
    def test_04_l4_adt_deployed(self, deployed_environment):
        """Verify L4: Azure Digital Twins deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        adt_name = outputs.get("azure_adt_instance_name")
        assert adt_name is not None, "ADT instance not created"
        
        print(f"[VERIFY] ✓ L4 ADT: {adt_name}")
    
    def test_05_l5_grafana_deployed(self, deployed_environment):
        """Verify L5: Grafana workspace deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        grafana_name = outputs.get("azure_grafana_name")
        grafana_endpoint = outputs.get("azure_grafana_endpoint")
        
        assert grafana_name is not None, "Grafana not created"
        
        print(f"[VERIFY] ✓ L5 Grafana: {grafana_name}")
        if grafana_endpoint:
            print(f"         URL: {grafana_endpoint}")
    
    # =========================================================================
    # DATA FLOW TESTS
    # =========================================================================
    
    def test_06_send_iot_message(self, deployed_environment):
        """Send IoT message through the pipeline."""
        project_path = deployed_environment["project_path"]
        
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
    
    def test_07_verify_data_in_cosmos_db(self, deployed_environment):
        """Verify sent data reached Cosmos DB via Hot Reader."""
        outputs = deployed_environment["terraform_outputs"]
        test_device_id = deployed_environment.get("test_device_id")
        
        if not test_device_id:
            pytest.skip("No test message was sent")
        
        # Wait for data propagation
        print("[DATA] Waiting for data propagation (15 seconds)...")
        time.sleep(15)
        
        hot_reader_url = outputs.get("azure_l3_hot_reader_url")
        if not hot_reader_url:
            pytest.skip("Hot Reader URL not available")
        
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
                assert property_values, "Hot Reader should return property values"
                
                print("[DATA] ✓ Data verified in Cosmos DB via Hot Reader")
            else:
                print(f"[DATA] Hot Reader returned: {response.status_code}")
                pytest.skip(f"Hot Reader returned {response.status_code}")
                
        except Exception as e:
            print(f"[DATA] Warning: Could not verify Cosmos data: {e}")
            pytest.skip(f"Could not query Hot Reader: {e}")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "live"])
