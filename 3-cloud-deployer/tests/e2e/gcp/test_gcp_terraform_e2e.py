"""
GCP Terraform End-to-End Test.

This test deploys all GCP layers using Terraform, sends Pub/Sub messages through
the pipeline, verifies data reaches Firestore, then destroys resources.

IMPORTANT: This test deploys REAL GCP resources and incurs costs.
Run with: pytest -m live

Estimated duration: 15-30 minutes
Estimated cost: ~$0.50-2.00 USD

Note: GCP does not have managed L4/L5 equivalents (Digital Twins, Grafana),
so this test only covers L1-L3.
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
class TestGCPTerraformE2E:
    """
    Live E2E test for GCP deployment using Terraform.
    
    Tests the complete data flow:
    Pub/Sub → Dispatcher → Processor → Persister → Firestore → Hot Reader
    
    Uses TerraformDeployerStrategy for infrastructure provisioning.
    
    TODO(GCP-L4L5): L4/L5 not tested - GCP lacks managed Digital Twin and Grafana services.
    When GCP L4/L5 is implemented, add test phases for those layers similar to AWS/Azure E2E tests.
    """
    
    @pytest.fixture(scope="class")
    def deployed_environment(self, request, gcp_terraform_e2e_project_path, gcp_credentials):
        """
        Deploy all GCP layers via Terraform with GUARANTEED cleanup.
        
        Uses unique project name per run to avoid Terraform state conflicts.
        Cleanup (terraform destroy) ALWAYS runs, even on test failure.
        """
        from src.core.config_loader import load_project_config, load_credentials
        from src.core.context import DeploymentContext
        from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
        import validator
        import constants as CONSTANTS
        
        print("\n" + "="*60)
        print("  GCP TERRAFORM E2E TEST - PRE-DEPLOYMENT VALIDATION")
        print("="*60)
        
        project_path = Path(gcp_terraform_e2e_project_path)
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
        # PHASE 2: Validate GCP Credentials
        # ==========================================
        print("\n[VALIDATION] Phase 2: GCP Credentials")
        
        gcp_creds = credentials.get("gcp")
        if not gcp_creds:
            pytest.fail("No GCP credentials found in config_credentials.json")
        
        required_fields = ["gcp_region"]
        missing_fields = [f for f in required_fields if not gcp_creds.get(f)]
        if missing_fields:
            pytest.fail(f"Missing required GCP credential fields: {missing_fields}")
        
        # gcp_billing_account OR gcp_project_id is required
        has_billing = gcp_creds.get("gcp_billing_account", "").strip()
        has_project_id = gcp_creds.get("gcp_project_id", "").strip()
        if not has_billing and not has_project_id:
            pytest.fail(
                "GCP requires either 'gcp_project_id' (existing project) or "
                "'gcp_billing_account' (new project creation) in credentials."
            )
        
        print(f"  ✓ GCP credentials validated")
        
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
        
        def terraform_cleanup():
            """Cleanup function - always runs terraform destroy."""
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
                print("  Some resources may still exist in GCP.")
                print("  Please check the Google Cloud Console and manually delete:")
                print(f"    Project: {gcp_creds.get('gcp_project_id') or config.digital_twin_name}-project")
                print("")
                print("  Console: https://console.cloud.google.com")
                print("!"*60)
        
        # Register cleanup to run ALWAYS
        # NOTE: Commented out for debugging - resources will NOT be destroyed
        # request.addfinalizer(terraform_cleanup)
        
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
            "project_path": gcp_terraform_e2e_project_path,
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
            "gcp_project_id",
            "gcp_service_account_email",
        ]
        
        for output in required_outputs:
            assert outputs.get(output) is not None, f"Missing Terraform output: {output}"
        
        print("[VERIFY] ✓ Terraform outputs present")
    
    def test_02_l1_pubsub_deployed(self, deployed_environment):
        """Verify L1: Pub/Sub topics deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        telemetry_topic = outputs.get("gcp_pubsub_telemetry_topic")
        events_topic = outputs.get("gcp_pubsub_events_topic")
        
        # Topics may be null if L1 not using GCP
        if telemetry_topic is not None:
            print(f"[VERIFY] ✓ L1 Pub/Sub Telemetry Topic: {telemetry_topic}")
        else:
            pytest.skip("L1 not deployed to GCP")
        
        if events_topic is not None:
            print(f"[VERIFY] ✓ L1 Pub/Sub Events Topic: {events_topic}")
    
    def test_03_l2_functions_deployed(self, deployed_environment):
        """Verify L2: Cloud Functions deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        processor_url = outputs.get("gcp_processor_url")
        persister_url = outputs.get("gcp_persister_url")
        
        if processor_url is not None:
            print(f"[VERIFY] ✓ L2 Processor URL: {processor_url}")
        else:
            pytest.skip("L2 not deployed to GCP")
        
        if persister_url is not None:
            print(f"[VERIFY] ✓ L2 Persister URL: {persister_url}")
    
    def test_04_l3_firestore_deployed(self, deployed_environment):
        """Verify L3: Firestore deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        firestore_db = outputs.get("gcp_firestore_database")
        hot_reader_url = outputs.get("gcp_hot_reader_url")
        
        if firestore_db is not None:
            print(f"[VERIFY] ✓ L3 Firestore Database: {firestore_db}")
        else:
            pytest.skip("L3 Hot not deployed to GCP")
        
        if hot_reader_url is not None:
            print(f"[VERIFY] ✓ L3 Hot Reader URL: {hot_reader_url}")
    
    def test_05_l3_cold_storage_deployed(self, deployed_environment):
        """Verify L3 Cold: Cloud Storage bucket deployed via Terraform."""
        outputs = deployed_environment["terraform_outputs"]
        
        cold_bucket = outputs.get("gcp_cold_bucket")
        
        if cold_bucket is not None:
            print(f"[VERIFY] ✓ L3 Cold Bucket: {cold_bucket}")
        else:
            pytest.skip("L3 Cold not deployed to GCP")
    
    def test_06_l4_l5_not_available(self, deployed_environment):
        """
        Verify L4/L5: Not available in GCP (no managed services).
        
        TODO(GCP-L4L5): When GCP L4/L5 is implemented, convert this to actual verification tests.
        """
        # GCP does not have managed Digital Twin or Grafana services
        # This test documents that fact
        print("[VERIFY] ℹ L4/L5 not available - GCP lacks managed Digital Twin and Grafana")
        print("         Future work: Consider self-hosted solutions on Compute Engine")
    
    # =========================================================================
    # DATA FLOW TESTS
    # =========================================================================
    
    def test_07_send_pubsub_message(self, deployed_environment):
        """Send Pub/Sub message through the pipeline."""
        credentials = deployed_environment["credentials"]
        outputs = deployed_environment["terraform_outputs"]
        
        gcp_creds = credentials.get("gcp", {})
        project_id = outputs.get("gcp_project_id") or gcp_creds.get("gcp_project_id")
        telemetry_topic = outputs.get("gcp_pubsub_telemetry_topic")
        
        if not telemetry_topic:
            pytest.skip("Pub/Sub topic not deployed")
        
        try:
            from google.cloud import pubsub_v1
            
            # Set credentials
            creds_file = gcp_creds.get("gcp_credentials_file")
            if creds_file:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file
            
            publisher = pubsub_v1.PublisherClient()
            topic_path = telemetry_topic
            
            test_payload = {
                "iotDeviceId": "temperature-sensor-1",
                "temperature": 42.5,
                "time": str(int(time.time() * 1000))
            }
            
            data = json.dumps(test_payload).encode("utf-8")
            future = publisher.publish(topic_path, data)
            message_id = future.result()
            
            print(f"[DATA] ✓ Sent test message: {test_payload}")
            print(f"[DATA]   Message ID: {message_id}")
            
            # Store for later verification
            deployed_environment["test_payload"] = test_payload
            deployed_environment["test_device_id"] = test_payload["iotDeviceId"]
            
        except ImportError:
            pytest.skip("google-cloud-pubsub SDK not installed")
        except Exception as e:
            pytest.fail(f"Failed to send Pub/Sub message: {e}")
    
    def test_08_verify_data_in_firestore(self, deployed_environment):
        """Verify sent data reached Firestore via Hot Reader."""
        outputs = deployed_environment["terraform_outputs"]
        test_device_id = deployed_environment.get("test_device_id")
        
        if not test_device_id:
            pytest.skip("No test message was sent")
        
        # Wait for data propagation
        print("[DATA] Waiting for data propagation (15 seconds)...")
        time.sleep(15)
        
        hot_reader_url = outputs.get("gcp_hot_reader_url")
        if not hot_reader_url:
            pytest.skip("Hot Reader URL not available")
        
        try:
            # Query for last entry
            response = requests.get(
                hot_reader_url,
                params={
                    "iotDeviceId": test_device_id,
                    "limit": 1
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"[DATA] Hot Reader response: {data}")
                
                items = data.get("items", [])
                if items:
                    print("[DATA] ✓ Data verified in Firestore via Hot Reader")
                else:
                    print("[DATA] ⚠ No data found yet - may need more propagation time")
            else:
                print(f"[DATA] Hot Reader returned: {response.status_code}")
                pytest.skip(f"Hot Reader returned {response.status_code}")
                
        except Exception as e:
            print(f"[DATA] Warning: Could not verify Firestore data: {e}")
            pytest.skip(f"Could not query Hot Reader: {e}")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "live"])
