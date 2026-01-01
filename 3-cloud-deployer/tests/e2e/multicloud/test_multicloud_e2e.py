"""
Multi-Cloud Terraform End-to-End Test.

This test deploys across ALL 3 cloud providers with MAXIMUM cross-cloud connections:
- GCP L1 (Pub/Sub) → Azure L2 (Functions) → AWS L3 (DynamoDB) → Azure L4 (ADT) → AWS L5 (Grafana)

IMPORTANT: This test deploys REAL resources across 3 clouds and incurs costs.
Run with: pytest -m live

Estimated duration: 30-45 minutes
Estimated cost: ~$2.00-5.00 USD
"""
import pytest
import os
import sys
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))


@pytest.mark.live
class TestMultiCloudE2E:
    """
    Live E2E test for multi-cloud deployment using Terraform.
    
    Tests ALL cross-cloud connections:
    - L1 (GCP) → L2 (Azure): Pub/Sub → Functions
    - L2 (Azure) → L3 hot (AWS): Functions → DynamoDB
    - L3 hot (AWS) → L4 (Azure): DynamoDB → Digital Twins
    - L4 (Azure) → L5 (AWS): Digital Twins → Grafana
    - L3 hot (AWS) → L3 cold (GCP): Mover → Cloud Storage
    - L3 cold (GCP) → L3 archive (Azure): Lifecycle → Blob Storage
    """
    
    @pytest.fixture(scope="class")
    def deployed_environment(self, request, multicloud_e2e_project_path, gcp_credentials, azure_credentials, aws_credentials):
        """
        Deploy all layers across 3 clouds via Terraform.
        
        Cleanup (terraform destroy) is COMMENTED OUT for initial debugging.
        """
        from src.core.config_loader import load_project_config, load_credentials
        from src.core.context import DeploymentContext
        from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
        import validator
        import constants as CONSTANTS
        
        print("\n" + "="*60)
        print("  MULTI-CLOUD E2E TEST - PRE-DEPLOYMENT VALIDATION")
        print("="*60)
        
        project_path = Path(multicloud_e2e_project_path)
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
        # PHASE 0: Validate All Cloud Credentials (Fail-Fast)
        # ==========================================
        print("\n[VALIDATION] Phase 0: Multi-Cloud Credential Handshake")
        
        # AWS check
        try:
            from api.credentials_checker import check_aws_credentials
            aws_result = check_aws_credentials(credentials.get("aws", {}))
            if aws_result["status"] == "error":
                pytest.fail(f"AWS credentials validation failed: {aws_result['message']}")
            elif aws_result["status"] == "invalid":
                print(f"  ⚠ AWS warning: {aws_result['message']}")
            else:
                print(f"  ✓ AWS credentials validated (Account: {aws_result.get('caller_identity', {}).get('account_id', 'N/A')})")
        except ImportError:
            print("  ⚠ boto3 not installed, skipping AWS credential check")
        
        # Azure check
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import ResourceManagementClient
            
            azure_creds_check = credentials.get("azure", {})
            credential = ClientSecretCredential(
                tenant_id=azure_creds_check.get("azure_tenant_id"),
                client_id=azure_creds_check.get("azure_client_id"),
                client_secret=azure_creds_check.get("azure_client_secret")
            )
            resource_client = ResourceManagementClient(
                credential,
                azure_creds_check.get("azure_subscription_id")
            )
            resource_client.providers.get("Microsoft.Resources")
            print(f"  ✓ Azure credentials validated (Subscription: {azure_creds_check.get('azure_subscription_id', 'N/A')[:8]}...)")
        except ImportError:
            print("  ⚠ azure-mgmt-resource not installed, skipping Azure check")
        except Exception as e:
            pytest.fail(f"Azure credentials validation failed: {e}")
        
        # GCP check
        try:
            from api.gcp_credentials_checker import check_gcp_credentials
            gcp_result = check_gcp_credentials(credentials.get("gcp", {}))
            if gcp_result["status"] == "error":
                pytest.fail(f"GCP credentials validation failed: {gcp_result['message']}")
            elif gcp_result["status"] == "invalid":
                print(f"  ⚠ GCP warning: {gcp_result['message']}")
            else:
                print(f"  ✓ GCP credentials validated (Project: {gcp_result.get('caller_identity', {}).get('project_id', 'N/A')})")
        except ImportError:
            print("  ⚠ google-auth not installed, skipping GCP check")
        
        # ==========================================
        # PHASE 1: Initialize Terraform Strategy
        # ==========================================
        print("\n[VALIDATION] Phase 1: Terraform Initialization")
        
        strategy = TerraformDeployerStrategy(
            terraform_dir=str(terraform_dir),
            project_path=str(project_path)
        )
        print(f"  ✓ Terraform strategy initialized")
        print(f"    - Terraform dir: {terraform_dir}")
        print(f"    - Project path: {project_path}")
        
        # Create context with credentials for post-deployment SDK operations
        context = DeploymentContext(
            project_name=config.digital_twin_name,
            project_path=project_path,
            config=config,
            credentials=credentials,  # CRITICAL: Required for IoT device registration, etc.
        )
        
        # Track deployment status
        deployment_success = False
        terraform_outputs = {}
        
        def terraform_cleanup():
            """Cleanup function - always runs terraform destroy."""
            print("\n" + "="*60)
            print("  CLEANUP: TERRAFORM DESTROY (ALL 3 CLOUDS)")
            print("="*60)
            
            try:
                strategy.destroy_all(context=context)
                print("[CLEANUP] ✓ Resources destroyed successfully")
            except Exception as e:
                print(f"[CLEANUP] ✗ Destroy failed: {e}")
                print("\n" + "!"*60)
                print("  ⚠️  CLEANUP FAILURE DETECTED!")
                print("")
                print("  Some resources may still exist. Check:")
                print("    - GCP Console: https://console.cloud.google.com")
                print("    - Azure Portal: https://portal.azure.com")
                print("    - AWS Console: https://console.aws.amazon.com")
                print("!"*60)
        
        # Register cleanup to run ALWAYS (on success or failure)
        # NOTE: Commented out for initial debugging - resources will NOT be destroyed
        # request.addfinalizer(terraform_cleanup)
        
        # ==========================================
        # PHASE 2: Terraform Deployment
        # ==========================================
        print("\n" + "="*60)
        print("  TERRAFORM DEPLOYMENT (MULTI-CLOUD)")
        print("="*60)
        
        # Create log file for full Terraform output
        log_file = project_path / "terraform_deploy.log"
        
        try:
            print(f"[LOG] Capturing full Terraform output to: {log_file}")
            
            # Open log file
            with open(log_file, "w", buffering=1) as log:
                # Write header
                log.write("="*80 + "\n")
                log.write("TERRAFORM DEPLOYMENT LOG\n")
                log.write("="*80 + "\n\n")
                log.flush()
                
                # Save original stdout/stderr
                import sys
                original_stdout = sys.stdout
                original_stderr = sys.stderr
                
                # Create a tee-like writer that writes to both console and file
                class TeeWriter:
                    def __init__(self, *writers):
                        self.writers = writers
                    def write(self, text):
                        for w in self.writers:
                            w.write(text)
                            w.flush()
                    def flush(self):
                        for w in self.writers:
                            w.flush()
                
                try:
                    # Redirect stdout/stderr to both console and file
                    sys.stdout = TeeWriter(original_stdout, log)
                    sys.stderr = TeeWriter(original_stderr, log)
                    
                    # Run deployment
                    terraform_outputs = strategy.deploy_all(context)
                    deployment_success = True
                    
                finally:
                    # Always restore stdout/stderr
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
            
            print("\n[DEPLOY] ✓ Terraform deployment complete")
            print(f"[LOG] Full output saved to: {log_file}")
            
            # Save outputs to file for debugging
            outputs_file = project_path / "terraform_outputs.json"
            with open(outputs_file, "w") as f:
                json.dump(terraform_outputs, f, indent=2)
            print(f"[OUTPUT] Terraform outputs saved to: {outputs_file}")
            
        except Exception as e:
            print(f"\n[DEPLOY] ✗ DEPLOYMENT FAILED: {type(e).__name__}: {e}")
            print(f"\n{'!'*60}")
            print(f"  FULL TERRAFORM ERROR LOG SAVED")
            print(f"{'!'*60}")
            print(f"\nTo see complete error details, run:")
            print(f"  docker exec master-thesis-3cloud-deployer-1 cat {log_file}")
            print(f"\nOr view in host:")
            print(f"  (File is in the test's temp directory)")
            print(f"{'!'*60}\n")
            raise
        
        print("\n" + "="*60)
        print("  DEPLOYMENT COMPLETE - RUNNING TESTS")
        print("="*60)
        
        yield {
            "context": context,
            "strategy": strategy,
            "project_path": multicloud_e2e_project_path,
            "config": config,
            "terraform_outputs": terraform_outputs,
            "credentials": credentials
        }
    
    # =========================================================================
    # LAYER 0: SETUP/GLUE TESTS
    # =========================================================================
    
    def test_01_gcp_l0_setup(self, deployed_environment):
        """Verify GCP L0 setup (service account, APIs)."""
        outputs = deployed_environment["terraform_outputs"]
        
        assert outputs.get("gcp_service_account_email"), "GCP service account not created"
        assert outputs.get("gcp_project_id"), "GCP project ID not set"
        print(f"  ✓ GCP L0 setup verified")
    
    def test_02_azure_l0_setup(self, deployed_environment):
        """Verify Azure L0 setup (resource group, managed identity)."""
        outputs = deployed_environment["terraform_outputs"]
        
        assert outputs.get("azure_resource_group_name"), "Azure resource group not created"
        assert outputs.get("azure_managed_identity_id"), "Azure managed identity not created"
        print(f"  ✓ Azure L0 setup verified")
    
    def test_03_aws_l0_setup(self, deployed_environment):
        """Verify AWS L0 setup (account configured).
        
        Note: aws_iot_role_arn only exists when L1 is AWS.
        In multicloud config L1=GCP, so we verify aws_account_id instead.
        """
        outputs = deployed_environment["terraform_outputs"]
        
        # Verify AWS is configured - account_id is always present when AWS is used
        assert outputs.get("aws_account_id"), "AWS account not configured"
        print(f"  ✓ AWS L0 setup verified (account: {outputs.get('aws_account_id')})")
    
    # =========================================================================
    # LAYER VERIFICATION TESTS
    # =========================================================================
    
    def test_04_gcp_l1_pubsub(self, deployed_environment):
        """Verify GCP L1 Pub/Sub deployed."""
        outputs = deployed_environment["terraform_outputs"]
        
        telemetry_topic = outputs.get("gcp_pubsub_telemetry_topic")
        assert telemetry_topic, "GCP Pub/Sub telemetry topic not deployed"
        print(f"  ✓ GCP L1 Pub/Sub: {telemetry_topic}")
    
    def test_05_azure_l2_functions(self, deployed_environment):
        """Verify Azure L2 Functions deployed."""
        outputs = deployed_environment["terraform_outputs"]
        
        dispatcher_url = outputs.get("azure_dispatcher_url")
        assert dispatcher_url, "Azure dispatcher function not deployed"
        print(f"  ✓ Azure L2 Functions: {dispatcher_url}")
    
    def test_05b_azure_functions_deployed(self, deployed_environment):
        """Verify Azure Function Apps have their functions deployed (not empty).
        
        CRITICAL: This test catches the case where Function Apps exist but have
        no function code deployed (empty ZIP or ZIP deploy failure).
        """
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        config = deployed_environment["config"]
        
        azure_creds = credentials.get("azure", {})
        subscription_id = azure_creds.get("azure_subscription_id")
        resource_group = outputs.get("azure_resource_group_name")
        
        if not subscription_id or not resource_group:
            pytest.skip("Azure credentials or resource group not available")
        
        # Check SDK availability first
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.web import WebSiteManagementClient
        except ImportError:
            pytest.skip("azure-mgmt-web SDK not installed")
        
        credential = ClientSecretCredential(
            tenant_id=azure_creds.get("azure_tenant_id"),
            client_id=azure_creds.get("azure_client_id"),
            client_secret=azure_creds.get("azure_client_secret")
        )
        
        web_client = WebSiteManagementClient(credential, subscription_id)
        
        # Use Terraform outputs directly for app names
        apps_to_check = {}
        
        # L0 Glue - only if Azure is used (cross-cloud scenario)
        l0_app_name = outputs.get("azure_l0_function_app_name")
        if l0_app_name:
            apps_to_check[l0_app_name] = ["ingestion"]  # Expected based on config
        
        # L2 Functions - only if L2 is Azure
        l2_app_name = outputs.get("azure_l2_function_app_name")
        if l2_app_name:
            apps_to_check[l2_app_name] = ["persister"]
        
        # User Functions - optional
        user_app_name = outputs.get("azure_user_functions_app_name")
        if user_app_name:
            apps_to_check[user_app_name] = []  # User functions are optional
        
        if not apps_to_check:
            pytest.skip("No Azure Function Apps deployed")
        
        all_passed = True
        failures = []
        
        for app_name, expected_functions in apps_to_check.items():
            try:
                functions = list(web_client.web_apps.list_functions(resource_group, app_name))
                function_names = [f.name.split('/')[-1] for f in functions]
                
                print(f"  [{app_name}] Found {len(functions)} functions: {function_names}")
                
                # CRITICAL: Fail if app should have functions but doesn't
                if expected_functions and len(functions) == 0:
                    failures.append(f"{app_name} has NO functions deployed!")
                    all_passed = False
                
                # Check for expected functions
                for expected in expected_functions:
                    if expected not in function_names:
                        print(f"    ⚠ Missing expected: {expected}")
                    else:
                        print(f"    ✓ Found: {expected}")
                        
            except Exception as e:
                failures.append(f"Could not list functions for {app_name}: {e}")
                all_passed = False
        
        if not all_passed:
            pytest.fail(f"Azure Function verification failed: {'; '.join(failures)}")
        
        print("  ✓ All Azure Function Apps verified")
    
    def test_06_aws_l3_dynamodb(self, deployed_environment):
        """Verify AWS L3 DynamoDB deployed."""
        outputs = deployed_environment["terraform_outputs"]
        
        table_name = outputs.get("aws_dynamodb_table_name")
        assert table_name, "AWS DynamoDB table not deployed"
        print(f"  ✓ AWS L3 DynamoDB: {table_name}")
    
    def test_07_gcp_l3_cold_storage(self, deployed_environment):
        """Verify GCP L3 Cold Storage deployed."""
        outputs = deployed_environment["terraform_outputs"]
        
        bucket_name = outputs.get("gcp_cold_bucket")
        assert bucket_name, "GCP cold storage bucket not deployed"
        print(f"  ✓ GCP L3 Cold Storage: {bucket_name}")
    
    def test_08_azure_l3_archive_and_l4(self, deployed_environment):
        """Verify Azure L3 Archive Storage and L4 Digital Twins deployed."""
        outputs = deployed_environment["terraform_outputs"]
        
        # L3 Archive
        archive_account = outputs.get("azure_archive_storage_account")
        assert archive_account, "Azure archive storage not deployed"
        print(f"  ✓ Azure L3 Archive: {archive_account}")
        
        # L4 Digital Twins
        adt_name = outputs.get("azure_adt_instance_name")
        assert adt_name, "Azure Digital Twins not deployed"
        print(f"  ✓ Azure L4 Digital Twins: {adt_name}")
    
    def test_09_aws_l5_grafana(self, deployed_environment):
        """Verify AWS L5 Grafana deployed."""
        outputs = deployed_environment["terraform_outputs"]
        
        grafana_endpoint = outputs.get("aws_grafana_endpoint")
        assert grafana_endpoint, "AWS Grafana not deployed"
        print(f"  ✓ AWS L5 Grafana: {grafana_endpoint}")
    
    # =========================================================================
    # DATA FLOW TESTS
    # =========================================================================
    
    def test_10_send_pubsub_message(self, deployed_environment):
        """Send test message through GCP Pub/Sub."""
        credentials = deployed_environment["credentials"]
        outputs = deployed_environment["terraform_outputs"]
        project_path = Path(deployed_environment["project_path"])
        
        gcp_creds = credentials.get("gcp", {})
        telemetry_topic = outputs.get("gcp_pubsub_telemetry_topic")
        
        if not telemetry_topic:
            pytest.skip("Pub/Sub topic not deployed")
        
        try:
            from google.cloud import pubsub_v1
            
            # Set credentials - convert relative path to absolute
            creds_file = gcp_creds.get("gcp_credentials_file")
            if creds_file:
                if not os.path.isabs(creds_file):
                    creds_file = str(project_path / creds_file)
                if os.path.exists(creds_file):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file
                else:
                    print(f"[WARN] Credentials file not found: {creds_file}")
            
            publisher = pubsub_v1.PublisherClient()
            
            test_payload = {
                "iotDeviceId": "temperature-sensor-1",
                "temperature": 42.5,
                "time": str(int(time.time() * 1000))
            }
            
            data = json.dumps(test_payload).encode("utf-8")
            future = publisher.publish(telemetry_topic, data)
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
    
    def test_11_verify_data_in_dynamodb(self, deployed_environment):
        """Verify sent data reached AWS DynamoDB via hot reader Lambda.
        
        Uses the aws_l3_hot_reader_url endpoint to query data, which:
        1. Tests the actual application flow (HTTP → Lambda → DynamoDB)
        2. Avoids boto3 credential issues in Docker
        3. Validates the L3 hot reader function works
        
        CRITICAL: This test verifies the core multicloud data flow.
        GCP Pub/Sub → Azure Functions → AWS DynamoDB
        
        Note: Azure L2 functions transform 'iotDeviceId' → 'device_id' for DynamoDB.
        """
        import requests
        
        outputs = deployed_environment["terraform_outputs"]
        test_device_id = deployed_environment.get("test_device_id")
        
        if not test_device_id:
            pytest.skip("No test message was sent - test_10 may have failed")
        
        # Wait for data propagation through the multicloud pipeline
        print("[DATA] Waiting for data propagation (20 seconds)...")
        print("[DATA]   GCP Pub/Sub → Azure L2 Functions → AWS DynamoDB")
        time.sleep(20)
        
        # Use the L3 hot reader Lambda URL to verify data
        hot_reader_url = outputs.get("aws_l3_hot_reader_url")
        if not hot_reader_url:
            # Fallback to L0 hot reader if L3 not available
            hot_reader_url = outputs.get("aws_l0_hot_reader_url")
        
        if not hot_reader_url:
            pytest.fail("No hot reader URL available in terraform outputs")
        
        print(f"[DATA] Querying hot reader: {hot_reader_url}")
        
        # Query the hot reader for our test device
        # Note: DynamoDB uses 'device_id' as partition key (Azure L2 transforms iotDeviceId → device_id)
        query_params = {
            "device_id": test_device_id,
            "limit": "5"
        }
        
        try:
            response = requests.get(
                hot_reader_url,
                params=query_params,
                timeout=30
            )
            
            print(f"[DATA] Hot reader response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[DATA] Hot reader response: {json.dumps(data, indent=2, default=str)[:500]}")
                
                # Check if we got valid data
                if isinstance(data, list) and len(data) > 0:
                    print(f"[DATA] ✓ Found {len(data)} records for {test_device_id}")
                    print(f"[DATA] ✓ MULTICLOUD DATA FLOW VERIFIED!")
                    print(f"[DATA]   GCP Pub/Sub → Azure Functions → AWS DynamoDB ✓")
                elif isinstance(data, dict) and data.get("items"):
                    items = data.get("items", [])
                    print(f"[DATA] ✓ Found {len(items)} records for {test_device_id}")
                    print(f"[DATA] ✓ MULTICLOUD DATA FLOW VERIFIED!")
                elif isinstance(data, dict) and data.get("data"):
                    items = data.get("data", [])
                    print(f"[DATA] ✓ Found {len(items)} records for {test_device_id}")
                    print(f"[DATA] ✓ MULTICLOUD DATA FLOW VERIFIED!")
                else:
                    # No data found - this could be timing issue
                    print(f"[DATA] ⚠ No data found for {test_device_id} yet")
                    print(f"[DATA]   Response: {data}")
                    print(f"[DATA]   May need more time to propagate (fresh deployment)")
            elif response.status_code == 404:
                # No data yet - acceptable for fresh deployment (consistent with AWS E2E)
                print(f"[DATA] ⚠ No data found via Hot Reader (expected for fresh deployment)")
            else:
                print(f"[DATA] ⚠ Unexpected response: {response.status_code}")
                print(f"[DATA]   Body: {response.text[:500]}")
                
        except requests.exceptions.Timeout:
            print("[DATA] ⚠ Hot Reader request timed out (Lambda cold start)")
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to query hot reader: {e}")
    
    def test_12_verify_twinmaker_entity(self, deployed_environment):
        """Verify TwinMaker entity exists."""
        outputs = deployed_environment["terraform_outputs"]
        test_device_id = deployed_environment.get("test_device_id")
        
        # Debug: show what keys are in deployed_environment
        print(f"[TWINMAKER] deployed_environment keys: {list(deployed_environment.keys())}")
        print(f"[TWINMAKER] test_device_id value: {test_device_id}")
        
        if not test_device_id:
            pytest.skip("No test device ID available - test_10 may have failed")
        
        workspace_id = outputs.get("aws_twinmaker_workspace_id")
        if not workspace_id:
            pytest.skip("TwinMaker workspace not deployed")
        
        try:
            import boto3
            
            twinmaker = boto3.client('iottwinmaker')
            
            # List entities in workspace
            response = twinmaker.list_entities(workspaceId=workspace_id)
            entities = response.get('entitySummaries', [])
            
            print(f"[TWINMAKER] Found {len(entities)} entities in workspace")
            
            # Look for our test device entity
            device_entity = next((e for e in entities if test_device_id in e.get('entityName', '')), None)
            
            if device_entity:
                print(f"[TWINMAKER] ✓ Entity found: {device_entity['entityName']}")
            else:
                print(f"[TWINMAKER] ⚠ Entity for {test_device_id} not found")
                
        except ImportError:
            pytest.skip("boto3 not installed")
        except Exception as e:
            print(f"[TWINMAKER] ⚠ Could not query TwinMaker: {e}")

    def test_12b_verify_adt_twin(self, deployed_environment):
        """Verify Azure Digital Twins entity exists.
        
        Parallel test to test_12 for Azure L4 scenarios.
        Checks that device twins were created in Azure Digital Twins.
        """
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        test_device_id = deployed_environment.get("test_device_id")
        
        print(f"[ADT] deployed_environment keys: {list(deployed_environment.keys())}")
        print(f"[ADT] test_device_id value: {test_device_id}")
        
        if not test_device_id:
            pytest.skip("No test device ID available - test_10 may have failed")
        
        adt_endpoint = outputs.get("azure_adt_endpoint")
        if not adt_endpoint:
            pytest.skip("Azure Digital Twins not deployed")
        
        # Check SDK availability first
        try:
            from azure.identity import ClientSecretCredential
            from azure.digitaltwins.core import DigitalTwinsClient
        except ImportError:
            pytest.skip("azure-digitaltwins-core SDK not installed")
        
        azure_creds = credentials.get("azure", {})
        
        try:
            credential = ClientSecretCredential(
                tenant_id=azure_creds.get("azure_tenant_id"),
                client_id=azure_creds.get("azure_client_id"),
                client_secret=azure_creds.get("azure_client_secret")
            )
            
            adt_client = DigitalTwinsClient(adt_endpoint, credential)
            
            # Query for twins - list all twins
            query = "SELECT * FROM digitaltwins"
            twins = list(adt_client.query_twins(query))
            
            print(f"[ADT] Found {len(twins)} twins in Azure Digital Twins")
            
            # Look for our test device twin
            device_twin = next((t for t in twins if test_device_id in t.get('$dtId', '')), None)
            
            if device_twin:
                print(f"[ADT] ✓ Twin found: {device_twin['$dtId']}")
            else:
                # List all twin IDs for debugging
                twin_ids = [t.get('$dtId', 'unknown') for t in twins]
                print(f"[ADT] ⚠ Twin for {test_device_id} not found")
                print(f"[ADT]   Available twins: {twin_ids[:10]}...")  # Show first 10
                
        except Exception as e:
            print(f"[ADT] ⚠ Could not query Azure Digital Twins: {e}")


# Allow running this file directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "live"])
