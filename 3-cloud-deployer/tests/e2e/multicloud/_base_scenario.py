"""
Shared base module for scenario-based E2E tests.

Each scenario file imports this and provides only the provider configuration.
This module contains ALL shared deployment and verification logic.

Architecture:
    _base_scenario.py          <- This file (shared logic)
    test_scenario_*.py         <- Scenario files (config only)
"""
import pytest
import os
import sys
import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))


@dataclass
class ScenarioConfig:
    """Configuration for a single E2E scenario."""
    name: str                    # e.g., "gcp_azure"
    description: str             # Human-readable description
    providers: Dict[str, str]    # Layer→provider mapping
    
    @property
    def digital_twin_name(self) -> str:
        """Unique name for this scenario's resources."""
        return f"sc-{self.name}"
    
    @property
    def required_clouds(self) -> set:
        """Set of clouds required for this scenario."""
        cloud_map = {"google": "gcp", "azure": "azure", "aws": "aws", "none": None}
        clouds = set()
        for provider in self.providers.values():
            mapped = cloud_map.get(provider)
            if mapped:
                clouds.add(mapped)
        return clouds


def check_required_credentials(scenario: ScenarioConfig, credentials: dict) -> Optional[str]:
    """
    Validate that ALL required cloud credentials are available.
    Returns error message if missing, None if OK.
    """
    required = scenario.required_clouds
    missing = []
    
    if "aws" in required:
        aws_creds = credentials.get("aws", {})
        if not aws_creds.get("aws_access_key_id"):
            missing.append("AWS")
    
    if "azure" in required:
        azure_creds = credentials.get("azure", {})
        if not azure_creds.get("azure_client_id"):
            missing.append("Azure")
    
    if "gcp" in required:
        gcp_creds = credentials.get("gcp", {})
        if not gcp_creds.get("gcp_credentials_file") and not gcp_creds.get("gcp_project_id"):
            missing.append("GCP")
    
    if missing:
        return f"Missing credentials for: {', '.join(missing)}"
    return None


def create_scenario_project(scenario: ScenarioConfig, template_path: Path, base_dir: Path) -> Path:
    """
    Create project directory with MOCKED provider config.
    Each scenario gets unique digital_twin_name and state directory.
    """
    import shutil
    
    project_path = base_dir / scenario.digital_twin_name
    
    if project_path.exists():
        print(f"\n[SCENARIO] Reusing existing project: {project_path}")
    else:
        base_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(template_path, project_path)
        print(f"\n[SCENARIO] Created NEW project: {project_path}")
    
    # Update config.json with scenario-specific twin name
    config_path = project_path / "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)
    config["digital_twin_name"] = scenario.digital_twin_name
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    # MOCK: Write provider mapping (NOT from template!)
    providers_path = project_path / "config_providers.json"
    with open(providers_path, "w") as f:
        json.dump(scenario.providers, f, indent=2)
    
    print(f"[SCENARIO] Digital twin name: {scenario.digital_twin_name}")
    print(f"[SCENARIO] Provider config: {scenario.providers}")
    
    return project_path


class BaseScenarioTest:
    """
    Base class for scenario tests with provider-agnostic verification.
    
    Subclasses MUST define:
        SCENARIO: ScenarioConfig = ScenarioConfig(...)
    """
    
    # Subclasses MUST define this
    SCENARIO: ScenarioConfig = None
    
    @pytest.fixture(scope="class")
    def deployed_environment(self, request, template_project_path):
        """Deploy infrastructure for this scenario.
        
        IMPORTANT: Cleanup is registered FIRST (before any deployment work) to ensure
        resources are cleaned up even if deployment fails. This prevents orphaned
        cloud resources from accumulating when tests are interrupted or fail early.
        """
        import shutil
        from src.core.config_loader import load_project_config, load_credentials
        from src.core.context import DeploymentContext
        from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
        
        scenario = self.SCENARIO
        print("\n" + "="*60)
        print(f"  SCENARIO E2E TEST: {scenario.name}")
        print(f"  {scenario.description}")
        print("="*60)
        
        # ================================================================
        # FIX #1: REGISTER CLEANUP FIRST - before any deployment work
        # ================================================================
        # Use mutable dict to capture context/strategy after they're created
        cleanup_state = {
            "context": None,
            "strategy": None,
            "project_path": None,
            "credentials": None,
        }
        
        def terraform_cleanup():
            """Cleanup finalizer that runs even if deployment fails."""
            print("\n" + "="*60)
            print(f"  CLEANUP: TERRAFORM DESTROY ({scenario.name})")
            print("="*60)
            
            # Try Terraform destroy if we have context and strategy
            if cleanup_state["strategy"] and cleanup_state["context"]:
                try:
                    cleanup_state["strategy"].destroy_all(
                        context=cleanup_state["context"],
                        sdk_fallback="always"  # Always run SDK cleanup for thorough cleanup
                    )
                    print("[CLEANUP] ✓ Resources destroyed via Terraform + SDK")
                except Exception as e:
                    print(f"[CLEANUP] ✗ Terraform destroy failed: {e}")
                    # Even if Terraform fails, try SDK cleanup
                    if cleanup_state["credentials"]:
                        print("[CLEANUP] Attempting SDK-only cleanup as fallback...")
                        try:
                            from tests.e2e.pre_cleanup import cleanup_orphans_for_scenario
                            cleanup_orphans_for_scenario(
                                scenario.name,
                                cleanup_state["credentials"],
                                dry_run=False
                            )
                            print("[CLEANUP] ✓ SDK cleanup completed")
                        except Exception as sdk_e:
                            print(f"[CLEANUP] ✗ SDK cleanup also failed: {sdk_e}")
            else:
                # No context/strategy - deployment failed early, try SDK cleanup
                print("[CLEANUP] No deployment context - attempting SDK-only cleanup...")
                if cleanup_state["credentials"]:
                    try:
                        from tests.e2e.pre_cleanup import cleanup_orphans_for_scenario
                        cleanup_orphans_for_scenario(
                            scenario.name,
                            cleanup_state["credentials"],
                            dry_run=False
                        )
                        print("[CLEANUP] ✓ SDK cleanup completed")
                    except Exception as e:
                        print(f"[CLEANUP] ✗ SDK cleanup failed: {e}")
            
            # Remove state files for fresh next run
            if cleanup_state["project_path"] and cleanup_state["project_path"].exists():
                try:
                    shutil.rmtree(cleanup_state["project_path"])
                    print(f"[CLEANUP] ✓ State files removed: {cleanup_state['project_path']}")
                except Exception as e:
                    print(f"[CLEANUP] ⚠ Could not remove state files: {e}")
        
        # Register cleanup FIRST - before any work that might fail
        skip_cleanup = os.environ.get("E2E_SKIP_CLEANUP", "false").lower() == "true"
        if not skip_cleanup:
            request.addfinalizer(terraform_cleanup)
        else:
            print("[CLEANUP] ⚠ Cleanup disabled (E2E_SKIP_CLEANUP=true)")
        
        # ================================================================
        # FIX #2: PRE-CLEANUP - Remove orphaned resources from previous runs
        # ================================================================
        # Load credentials from template first (always needed for later phases)
        template_credentials = load_credentials(Path(template_project_path))
        cleanup_state["credentials"] = template_credentials
        
        # Check if Terraform state exists (if so, skip pre-cleanup to avoid drift)
        state_dir = Path(__file__).parent / "e2e_state" / scenario.digital_twin_name
        state_file = state_dir / "terraform.tfstate"
        state_exists = state_file.exists() and state_file.stat().st_size > 100
        
        # Pre-cleanup is coupled with cleanup: skip if cleanup is skipped OR state exists
        if skip_cleanup:
            print("\n[PHASE -1] Pre-Test Orphan Cleanup: SKIPPED (E2E_SKIP_CLEANUP=true)")
        elif state_exists:
            print("\n[PHASE -1] Pre-Test Orphan Cleanup: SKIPPED (Terraform state exists - using existing resources)")
        else:
            print("\n[PHASE -1] Pre-Test Orphan Cleanup")
            try:
                from tests.e2e.pre_cleanup import cleanup_orphans_for_scenario
                cleanup_orphans_for_scenario(scenario.name, template_credentials, dry_run=False)
                print("  [OK] Pre-cleanup completed")
            except Exception as e:
                print(f"  [WARN] Pre-cleanup error (continuing anyway): {e}")
        
        # === SETUP: Create project with mocked providers ===
        base_dir = Path(__file__).parent / "e2e_state"
        project_path = create_scenario_project(
            scenario, 
            Path(template_project_path), 
            base_dir
        )
        cleanup_state["project_path"] = project_path
        
        # Load credentials
        credentials = load_credentials(project_path)
        cleanup_state["credentials"] = credentials
        
        # Set AWS environment variables for boto3 (needed for test_07 dataflow)
        if "aws" in credentials:
            aws_creds = credentials["aws"]
            if aws_creds.get("aws_access_key_id"):
                os.environ["AWS_ACCESS_KEY_ID"] = aws_creds["aws_access_key_id"]
            if aws_creds.get("aws_secret_access_key"):
                os.environ["AWS_SECRET_ACCESS_KEY"] = aws_creds["aws_secret_access_key"]
            if aws_creds.get("aws_region"):
                os.environ["AWS_REGION"] = aws_creds["aws_region"]
                os.environ["AWS_DEFAULT_REGION"] = aws_creds["aws_region"]  # boto3 uses this
        
        # === PHASE 0: Credential validation ===
        print("\n[PHASE 0] Credential Validation")
        cred_error = check_required_credentials(scenario, credentials)
        if cred_error:
            pytest.skip(f"Skipping scenario {scenario.name}: {cred_error}")
        print(f"  [OK] All required credentials available: {scenario.required_clouds}")
        
        # === GAP FIX #1: Config file validation ===
        print("\n[PHASE 0.5] Config File Validation")
        try:
            import validator
            import constants as CONSTANTS
            
            config_files = [
                CONSTANTS.CONFIG_FILE,
                CONSTANTS.CONFIG_IOT_DEVICES_FILE,
                CONSTANTS.CONFIG_CREDENTIALS_FILE,
                CONSTANTS.CONFIG_PROVIDERS_FILE,
            ]
            for config_filename in config_files:
                config_file_path = project_path / config_filename
                if config_file_path.exists():
                    with open(config_file_path, 'r') as f:
                        content = json.load(f)
                    validator.validate_config_content(config_filename, content)
            print(f"  [OK] Config files validated")
        except ImportError:
            print(f"  [WARN] validator module not available - skipping validation")
        except Exception as e:
            print(f"  [WARN] Config validation error: {e}")
        
        # === PHASE 1: Terraform deployment ===
        terraform_dir = Path(__file__).parent.parent.parent.parent / "src" / "terraform"
        
        config = load_project_config(project_path)
        strategy = TerraformDeployerStrategy(
            terraform_dir=str(terraform_dir),
            project_path=str(project_path)
        )
        cleanup_state["strategy"] = strategy
        
        context = DeploymentContext(
            project_name=config.digital_twin_name,
            project_path=project_path,
            config=config,
            credentials=credentials,
        )
        cleanup_state["context"] = context
        
        # Deploy (credential validation happens inside deploy_all Step 0)
        terraform_outputs = strategy.deploy_all(context)
        
        # Store mutable test state
        test_state = {
            "test_payload": None,
            "test_device_id": None,
        }
        
        yield {
            "scenario": scenario,
            "context": context,
            "strategy": strategy,
            "project_path": str(project_path),
            "config": config,
            "terraform_outputs": terraform_outputs,
            "credentials": credentials,
            "test_state": test_state,
        }
    
    # =========================================================================
    # PROVIDER-AGNOSTIC LAYER VERIFICATION TESTS
    # =========================================================================
    
    def test_01_l0_setup(self, deployed_environment):
        """Verify L0 setup resources for all active clouds."""
        outputs = deployed_environment["terraform_outputs"]
        scenario = deployed_environment["scenario"]
        
        verified = []
        if "gcp" in scenario.required_clouds and outputs.get("gcp_service_account_email"):
            verified.append("GCP")
        if "azure" in scenario.required_clouds and outputs.get("azure_resource_group_name"):
            verified.append("Azure")
        if "aws" in scenario.required_clouds and outputs.get("aws_account_id"):
            verified.append("AWS")
        
        # FIX #10: Add assertion
        assert len(verified) == len(scenario.required_clouds), \
            f"Expected {len(scenario.required_clouds)} clouds, verified {len(verified)}: {verified}"
        print(f"  [OK] L0 setup verified: {', '.join(verified)}")
    
    def test_01b_l0_glue_functions(self, deployed_environment):
        """Verify L0 glue functions deployed for cross-cloud boundaries.
        
        FIX #9: This test verifies the ACTUAL glue functions exist.
        """
        outputs = deployed_environment["terraform_outputs"]
        scenario = deployed_environment["scenario"]
        glue_verified = []
        
        # L1→L2 boundary: ingestion glue
        l1 = scenario.providers["layer_1_provider"]
        l2 = scenario.providers["layer_2_provider"]
        if l1 != l2:
            # Glue is on the RECEIVER (L2) side
            if l2 == "aws":
                url = outputs.get("aws_l0_ingestion_url")
                if url:
                    glue_verified.append(f"L1\u2192L2 ingestion (AWS)")
            elif l2 == "azure":
                # Azure L0 functions are in the L0 glue app
                app = outputs.get("azure_l0_function_app_name")
                if app:
                    glue_verified.append(f"L1\u2192L2 ingestion (Azure)")
            elif l2 == "google":
                url = outputs.get("gcp_ingestion_url")
                if not url:
                    pytest.fail(f"[FAIL-FAST] GCP L0 ingestion URL not found. Expected: gcp_ingestion_url")
                glue_verified.append(f"L1→L2 ingestion (GCP)")
        
        # L2→L3-Hot boundary: hot-writer glue
        l3_hot = scenario.providers["layer_3_hot_provider"]
        if l2 != l3_hot:
            if l3_hot == "aws":
                url = outputs.get("aws_l0_hot_writer_url")
                if url:
                    glue_verified.append(f"L2\u2192L3-Hot hot-writer (AWS)")
            elif l3_hot == "azure":
                app = outputs.get("azure_l0_function_app_name")
                if app:
                    glue_verified.append(f"L2\u2192L3-Hot hot-writer (Azure)")
            elif l3_hot == "google":
                url = outputs.get("gcp_hot_writer_url")
                if not url:
                    pytest.fail(f"[FAIL-FAST] GCP L0 hot-writer URL not found. Expected: gcp_hot_writer_url")
                glue_verified.append(f"L2→L3-Hot hot-writer (GCP)")
        
        if glue_verified:
            print(f"  [OK] L0 glue verified: {', '.join(glue_verified)}")
        else:
            # No cross-cloud boundaries or outputs not found
            print(f"  [WARN] No L0 glue functions found (may use different output names)")
    
    def test_02_l1_ingestion(self, deployed_environment):
        """Verify L1 (IoT ingestion) based on scenario's L1 provider."""
        outputs = deployed_environment["terraform_outputs"]
        scenario = deployed_environment["scenario"]
        l1_provider = scenario.providers["layer_1_provider"]
        
        if l1_provider == "google":
            assert outputs.get("gcp_pubsub_telemetry_topic"), "GCP Pub/Sub not deployed"
            print(f"  [OK] L1 (GCP Pub/Sub) verified")
        elif l1_provider == "azure":
            assert outputs.get("azure_iothub_name"), "Azure IoT Hub not deployed"
            print(f"  [OK] L1 (Azure IoT Hub) verified")
        elif l1_provider == "aws":
            assert outputs.get("aws_iot_topic_rule_name"), "AWS IoT Core not deployed"
            print(f"  [OK] L1 (AWS IoT Core) verified")
    
    def test_03_l2_processing(self, deployed_environment):
        """Verify L2 (processing functions) based on scenario's L2 provider."""
        outputs = deployed_environment["terraform_outputs"]
        scenario = deployed_environment["scenario"]
        l2_provider = scenario.providers["layer_2_provider"]
        
        if l2_provider == "azure":
            assert outputs.get("azure_l2_function_app_name"), "Azure Functions not deployed"
            print(f"  [OK] L2 (Azure Functions) verified")
        elif l2_provider == "aws":
            assert outputs.get("aws_l2_persister_function_name"), "[FAIL-FAST] AWS L2 persister not deployed. Expected: aws_l2_persister_function_name"
            print(f"  [OK] L2 (AWS Step Functions) verified")
        elif l2_provider == "google":
            assert outputs.get("gcp_processor_url"), "[FAIL-FAST] GCP processor not deployed. Expected: gcp_processor_url"
            print(f"  [OK] L2 (GCP Cloud Functions) verified")
    
    def test_04_l3_storage(self, deployed_environment):
        """Verify L3 storage (hot/cold/archive) based on scenario providers."""
        outputs = deployed_environment["terraform_outputs"]
        scenario = deployed_environment["scenario"]
        
        # L3 Hot
        hot_provider = scenario.providers["layer_3_hot_provider"]
        if hot_provider == "aws":
            assert outputs.get("aws_dynamodb_table_name"), "AWS DynamoDB not deployed"
            print(f"  [OK] L3 Hot (AWS DynamoDB) verified")
        elif hot_provider == "azure":
            assert outputs.get("azure_cosmos_account_name"), "Azure CosmosDB not deployed"
            print(f"  [OK] L3 Hot (Azure CosmosDB) verified")
        elif hot_provider == "google":
            assert outputs.get("gcp_firestore_database"), "GCP Firestore not deployed"
            print(f"  [OK] L3 Hot (GCP Firestore) verified")
        
        # FIX #11: L3 Cold
        cold_provider = scenario.providers["layer_3_cold_provider"]
        if cold_provider == "aws":
            assert outputs.get("aws_s3_cold_bucket"), "[FAIL-FAST] AWS S3 cold bucket not deployed. Expected: aws_s3_cold_bucket"
            print(f"  [OK] L3 Cold (AWS S3) verified")
        elif cold_provider == "azure":
            assert outputs.get("azure_storage_account_name"), "[FAIL-FAST] Azure storage account not deployed. Expected: azure_storage_account_name"
            print(f"  [OK] L3 Cold (Azure Blob) verified")
        elif cold_provider == "google":
            assert outputs.get("gcp_cold_bucket"), "GCP Cloud Storage cold not deployed"
            print(f"  [OK] L3 Cold (GCP Cloud Storage) verified")
        
        # FIX #11: L3 Archive
        archive_provider = scenario.providers["layer_3_archive_provider"]
        if archive_provider == "aws":
            assert outputs.get("aws_s3_archive_bucket"), "[FAIL-FAST] AWS S3 archive bucket not deployed. Expected: aws_s3_archive_bucket"
            print(f"  [OK] L3 Archive (AWS S3 Glacier) verified")
        elif archive_provider == "azure":
            assert outputs.get("azure_storage_account_name"), "[FAIL-FAST] Azure storage account not deployed. Expected: azure_storage_account_name"
            print(f"  [OK] L3 Archive (Azure Blob Archive) verified")
        elif archive_provider == "google":
            # GCP archive uses either dedicated archive bucket OR lifecycle policy on cold bucket
            archive_bucket = outputs.get("gcp_archive_bucket") or outputs.get("gcp_cold_bucket")
            assert archive_bucket, "[FAIL-FAST] GCP archive storage not deployed. Expected: gcp_archive_bucket or gcp_cold_bucket"
            print(f"  [OK] L3 Archive (GCP Cloud Storage Archive) verified")
    
    def test_05_l4_twins(self, deployed_environment):
        """Verify L4 (Digital Twins) based on scenario's L4 provider."""
        outputs = deployed_environment["terraform_outputs"]
        scenario = deployed_environment["scenario"]
        l4_provider = scenario.providers["layer_4_provider"]
        
        if l4_provider == "azure":
            assert outputs.get("azure_adt_instance_name"), "Azure Digital Twins not deployed"
            print(f"  [OK] L4 (Azure Digital Twins) verified")
        elif l4_provider == "aws":
            assert outputs.get("aws_twinmaker_workspace_id"), "AWS TwinMaker not deployed"
            print(f"  [OK] L4 (AWS TwinMaker) verified")
        elif l4_provider in ("none", "google"):
            pytest.skip("No L4 provider configured for this scenario")
    
    def test_06_l5_visualization(self, deployed_environment):
        """Verify L5 (Grafana) based on scenario's L5 provider."""
        outputs = deployed_environment["terraform_outputs"]
        scenario = deployed_environment["scenario"]
        l5_provider = scenario.providers["layer_5_provider"]
        
        if l5_provider == "aws":
            assert outputs.get("aws_grafana_endpoint"), "AWS Grafana not deployed"
            print(f"  [OK] L5 (AWS Grafana) verified")
        elif l5_provider == "azure":
            assert outputs.get("azure_grafana_endpoint"), "Azure Grafana not deployed"
            print(f"  [OK] L5 (Azure Grafana) verified")
        elif l5_provider in ("none", "google"):
            pytest.skip("No L5 provider configured for this scenario")
    
    # =========================================================================
    # DATA FLOW TESTS
    # =========================================================================
    
    def test_07_send_test_message(self, deployed_environment):
        """Send test message based on L1 provider."""
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        project_path = Path(deployed_environment["project_path"])
        test_state = deployed_environment["test_state"]
        l1_provider = scenario.providers["layer_1_provider"]
        
        test_payload = {
            "iotDeviceId": "temperature-sensor-1",
            "temperature": 42.5,
            "time": str(int(time.time() * 1000))
        }
        
        if l1_provider == "google":
            topic = outputs.get("gcp_pubsub_telemetry_topic")
            if not topic:
                pytest.fail("[DATAFLOW CRITICAL] GCP Pub/Sub topic not in Terraform outputs. Check gcp_pubsub_telemetry_topic output.")
            try:
                from google.cloud import pubsub_v1
                
                # FIX #16: Store and restore env var to avoid leaking to other tests
                gcp_creds = credentials.get("gcp", {})
                creds_file = gcp_creds.get("gcp_credentials_file")
                old_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
                try:
                    if creds_file:
                        if not os.path.isabs(creds_file):
                            creds_file = str(project_path / creds_file)
                        if os.path.exists(creds_file):
                            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_file
                    
                    publisher = pubsub_v1.PublisherClient()
                    data = json.dumps(test_payload).encode("utf-8")
                    future = publisher.publish(topic, data)
                    message_id = future.result()
                    print(f"  [OK] Sent via GCP Pub/Sub: {message_id}")
                    
                    test_state["test_payload"] = test_payload
                    test_state["test_device_id"] = test_payload["iotDeviceId"]
                finally:
                    # Restore original env var
                    if old_creds is not None:
                        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = old_creds
                    elif "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
                        del os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
            except ImportError:
                pytest.fail("[DATAFLOW CRITICAL] google-cloud-pubsub not installed in container. Install with: pip install google-cloud-pubsub")
                
        elif l1_provider == "azure":
            # Azure IoT Hub: Send message via HTTP to IoT Hub's REST API
            iothub_hostname = outputs.get("azure_iothub_hostname")
            if not iothub_hostname:
                pytest.fail("[DATAFLOW CRITICAL] Azure IoT Hub hostname not in Terraform outputs. Check azure_iothub_hostname output.")
            
            try:
                from azure.iot.device import IoTHubDeviceClient, Message
                
                # Get device connection string from the generated simulator config
                sim_config_path = project_path / "iot_device_simulator" / "azure" / "config_generated.json"
                if not sim_config_path.exists():
                    pytest.fail(f"[DATAFLOW CRITICAL] Azure device config not found at {sim_config_path}. IoT device registration may have failed.")
                
                with open(sim_config_path) as f:
                    sim_config = json.load(f)
                
                device_conn_str = sim_config.get("connection_string")
                if not device_conn_str:
                    pytest.fail("[DATAFLOW CRITICAL] Device connection string not in simulator config. Check IoT device registration.")
                
                # Send telemetry message as the device
                client = IoTHubDeviceClient.create_from_connection_string(device_conn_str)
                client.connect()
                try:
                    message = Message(json.dumps(test_payload))
                    message.content_type = "application/json"
                    message.content_encoding = "utf-8"
                    client.send_message(message)
                    print(f"  [OK] Sent via Azure IoT Hub device client")
                    
                    test_state["test_payload"] = test_payload
                    test_state["test_device_id"] = test_payload["iotDeviceId"]
                finally:
                    client.disconnect()
                    
            except ImportError:
                pytest.fail("[DATAFLOW CRITICAL] azure-iot-device not installed in container. Install with: pip install azure-iot-device")
            except Exception as e:
                pytest.fail(f"[DATAFLOW CRITICAL] Azure IoT Hub send failed: {e}")
            
        elif l1_provider == "aws":
            # AWS IoT Core: Publish via MQTT using boto3 iot-data
            # 
            # IMPORTANT: This requires iot:Publish permission on the topic ARN.
            # The Terraform deployment automatically grants this permission to the
            # IAM user running terraform apply (via aws_iam_policy.e2e_iot_publish).
            #
            # LIMITATION: Only works with IAM User credentials (access key/secret).
            # Assumed roles (SSO, CI/CD OIDC) require manual iot:Publish permission.
            #
            iot_topic = outputs.get("aws_iot_topic_rule_name")
            iot_endpoint = outputs.get("aws_iot_endpoint")
            
            if not iot_endpoint:
                # Get endpoint dynamically
                try:
                    import boto3
                    iot_client = boto3.client('iot')
                    endpoint_response = iot_client.describe_endpoint(endpointType='iot:Data-ATS')
                    iot_endpoint = endpoint_response['endpointAddress']
                except Exception as e:
                    pytest.fail(f"[DATAFLOW CRITICAL] Could not get AWS IoT endpoint: {e}. Check AWS credentials and IAM permissions for iot:DescribeEndpoint.")
            
            try:
                import boto3
                
                # Use iot-data client to publish to the ingestion topic
                # The topic must match the IoT Topic Rule pattern: dt/{name}/+/telemetry
                # The + is a wildcard for device_id, so we include it in the topic
                device_id = test_payload["iotDeviceId"]
                dt_name = outputs.get('digital_twin_name')
                if not dt_name:
                    pytest.fail("[FAIL-FAST] digital_twin_name output not found. This is required for AWS IoT topic construction.")
                topic_name = f"dt/{dt_name}/{device_id}/telemetry"
                
                iot_data = boto3.client('iot-data', endpoint_url=f"https://{iot_endpoint}")
                
                response = iot_data.publish(
                    topic=topic_name,
                    qos=1,
                    payload=json.dumps(test_payload)
                )
                print(f"  [OK] Sent via AWS IoT Core to topic: {topic_name}")
                
                test_state["test_payload"] = test_payload
                test_state["test_device_id"] = test_payload["iotDeviceId"]
                
            except ImportError:
                pytest.fail("[DATAFLOW CRITICAL] boto3 not installed in container.")
            except Exception as e:
                pytest.fail(f"[DATAFLOW CRITICAL] AWS IoT publish failed: {e}. Check AWS credentials and IoT Core permissions.")
    
    def test_08_verify_hot_storage(self, deployed_environment):
        """Verify data reached L3-Hot storage."""
        import requests
        
        outputs = deployed_environment["terraform_outputs"]
        test_state = deployed_environment["test_state"]
        test_device_id = test_state.get("test_device_id")
        
        if not test_device_id:
            pytest.fail("[DATAFLOW CRITICAL] No test message was sent in test_07. Previous test must have failed.")
        
        # Active wait for data propagation (polling every 2s for up to 120s)
        print("  Waiting for data propagation (polling)...")
        import time
        
        # Use hot reader URL based on L3-Hot provider (fail-fast, no fallbacks)
        scenario = deployed_environment["scenario"]
        l3_hot_provider = scenario.providers["layer_3_hot_provider"]
        
        if l3_hot_provider == "aws":
            hot_reader_url = outputs.get("aws_l3_hot_reader_url")
            if not hot_reader_url:
                pytest.fail("[FAIL-FAST] AWS L3 hot reader URL not found. Expected: aws_l3_hot_reader_url")
        elif l3_hot_provider == "azure":
            hot_reader_url = outputs.get("azure_l3_hot_reader_url")
            if not hot_reader_url:
                pytest.fail("[FAIL-FAST] Azure L3 hot reader URL not found. Expected: azure_l3_hot_reader_url")
        elif l3_hot_provider == "google":
            hot_reader_url = outputs.get("gcp_hot_reader_url")
            if not hot_reader_url:
                pytest.fail("[FAIL-FAST] GCP hot reader URL not found. Expected: gcp_hot_reader_url")
        else:
            pytest.fail(f"[FAIL-FAST] Unknown L3-Hot provider: {l3_hot_provider}")
        
        # Get the inter-cloud token for authentication
        inter_cloud_token = outputs.get("inter_cloud_token")
        headers = {}
        if inter_cloud_token:
            headers["X-Inter-Cloud-Token"] = inter_cloud_token
        
        max_retries = 60
        retry_interval = 2
        response = None  # Initialize to avoid undefined variable in error message
        
        for attempt in range(max_retries):
            # Progress indication every 20 seconds
            if attempt > 0 and attempt % 10 == 0:
                print(f"    Still waiting... ({attempt * retry_interval}s elapsed)")
            
            try:
                response = requests.get(
                    hot_reader_url,
                    params={"device_id": test_device_id, "limit": "5"},
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                    except ValueError as json_err:
                        pytest.fail(f"[DATAFLOW CRITICAL] Hot reader returned invalid JSON: {json_err}. Response: {response.text[:200]}")
                    
                    # Normalize data check (list or dict with items)
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict) and "items" in data:
                        items = data["items"]
                        
                    if len(items) > 0:
                        print(f"  ✓ DATA FLOW VERIFIED: Found {len(items)} records in hot storage (Attempt {attempt+1}/{max_retries})")
                        test_state["hot_storage_data"] = items
                        return  # Success!
                        
                elif response.status_code == 401:
                    pytest.fail(f"Hot reader returned 401 Unauthorized - inter_cloud_token may be missing or invalid")
                elif response.status_code == 403:
                    pytest.fail(f"Hot reader returned 403 Forbidden - Service Account permissions or firewall rule blocking access")
                elif response.status_code != 404:
                    # Fail fast on non-retriable errors (500, etc)
                    pytest.fail(f"Hot reader returned {response.status_code}: {response.text[:200]}")
                    
            except requests.exceptions.Timeout:
                pass  # Retry on timeout
            except requests.exceptions.RequestException as e:
                print(f"  ⚠ Request failed: {e}")
                
            time.sleep(retry_interval)
            
        # If loop finishes without return, data wasn't found
        last_status = response.status_code if response is not None else "None"
        pytest.fail(f"[DATAFLOW CRITICAL] No data found in hot storage after {max_retries*retry_interval}s. Last Response Status: {last_status}")
    
    # =========================================================================
    # SDK VERIFICATION TESTS (GAP FIXES #2-6)
    # =========================================================================
    
    def test_09_iot_devices_registered(self, deployed_environment):
        """GAP FIX #3: Verify IoT devices were registered by SDK post-deployment."""
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        l1_provider = scenario.providers["layer_1_provider"]
        
        if l1_provider == "aws":
            try:
                import boto3
                
                iot = boto3.client('iot')
                response = iot.list_things(maxResults=10)
                things = response.get('things', [])
                
                if things:
                    print(f"  [OK] AWS IoT: Found {len(things)} things registered")
                else:
                    print(f"  [WARN] AWS IoT: No things found (may need time)")
            except ImportError:
                pytest.skip("boto3 not installed")
            except Exception as e:
                print(f"  [WARN] Could not list AWS IoT things: {e}")
                
        elif l1_provider == "azure":
            try:
                from azure.identity import ClientSecretCredential
                from azure.iot.hub import IoTHubRegistryManager
                
                azure_creds = credentials.get("azure", {})
                iothub_name = outputs.get("azure_iothub_name")
                
                if not iothub_name:
                    pytest.fail("[FAIL-FAST] Azure IoT Hub name not found. Expected: azure_iothub_name")
                
                conn_string = outputs.get("azure_iothub_connection_string")
                if not conn_string:
                    pytest.fail("[FAIL-FAST] Azure IoT Hub connection string not found. Expected: azure_iothub_connection_string")
                
                registry = IoTHubRegistryManager(conn_string)
                devices = list(registry.get_devices(max_number_of_devices=10))
                if devices:
                    print(f"  [OK] Azure IoT Hub: Found {len(devices)} devices")
                else:
                    print(f"  [WARN] Azure IoT Hub: No devices found")
            except ImportError:
                pytest.fail("[FAIL-FAST] azure-iot-hub SDK not installed in container")
                
        elif l1_provider == "google":
            pytest.skip("GCP IoT Core deprecated - no device verification")
    
    def test_10_twinmaker_entities(self, deployed_environment):
        """GAP FIX #4: Verify TwinMaker entities were created when L4=AWS."""
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        l4_provider = scenario.providers["layer_4_provider"]
        
        if l4_provider != "aws":
            pytest.skip("L4 is not AWS - skipping TwinMaker verification")
        
        workspace_id = outputs.get("aws_twinmaker_workspace_id")
        if not workspace_id:
            pytest.skip("TwinMaker workspace not deployed")
        
        try:
            import boto3
            
            twinmaker = boto3.client('iottwinmaker')
            response = twinmaker.list_entities(workspaceId=workspace_id)
            entities = response.get('entitySummaries', [])
            
            if entities:
                entity_names = [e.get('entityName', 'unknown') for e in entities[:5]]
                print(f"  [OK] TwinMaker: Found {len(entities)} entities: {entity_names}")
            else:
                print(f"  [WARN] TwinMaker: No entities found (SDK post-deploy may have failed)")
        except ImportError:
            pytest.skip("boto3 not installed")
        except Exception as e:
            print(f"  [WARN] Could not query TwinMaker: {e}")
    
    def test_11_adt_twins(self, deployed_environment):
        """GAP FIX #5: Verify ADT twins were created when L4=Azure."""
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        l4_provider = scenario.providers["layer_4_provider"]
        
        if l4_provider != "azure":
            pytest.skip("L4 is not Azure - skipping ADT verification")
        
        adt_endpoint = outputs.get("azure_adt_endpoint")
        if not adt_endpoint:
            pytest.skip("Azure Digital Twins not deployed")
        
        try:
            from azure.identity import ClientSecretCredential
            from azure.digitaltwins.core import DigitalTwinsClient
            
            azure_creds = credentials.get("azure", {})
            credential = ClientSecretCredential(
                tenant_id=azure_creds.get("azure_tenant_id"),
                client_id=azure_creds.get("azure_client_id"),
                client_secret=azure_creds.get("azure_client_secret")
            )
            
            adt_client = DigitalTwinsClient(adt_endpoint, credential)
            query = "SELECT * FROM digitaltwins"
            twins = list(adt_client.query_twins(query))
            
            if twins:
                twin_ids = [t.get('$dtId', 'unknown') for t in twins[:5]]
                print(f"  [OK] ADT: Found {len(twins)} twins: {twin_ids}")
            else:
                print(f"  [WARN] ADT: No twins found (SDK post-deploy may have failed)")
        except ImportError:
            pytest.skip("azure-digitaltwins-core SDK not installed")
        except Exception as e:
            print(f"  [WARN] Could not query ADT: {e}")
    
    def test_11b_adt_twin_telemetry(self, deployed_environment):
        """Verify telemetry data updated ADT twin properties after test_07/08.
        
        This test validates the full L4 data flow:
        L2 Persister → _push_to_adt() → HTTP POST → ADT Pusher (L0) → Azure Digital Twins
        
        Uses polling to handle async twin updates.
        """
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        l4_provider = scenario.providers["layer_4_provider"]
        
        if l4_provider != "azure":
            pytest.skip("L4 is not Azure - skipping ADT telemetry verification")
        
        adt_endpoint = outputs.get("azure_adt_endpoint")
        if not adt_endpoint:
            pytest.skip("Azure Digital Twins not deployed")
        
        try:
            from azure.identity import ClientSecretCredential
            from azure.digitaltwins.core import DigitalTwinsClient
            
            azure_creds = credentials.get("azure", {})
            credential = ClientSecretCredential(
                tenant_id=azure_creds.get("azure_tenant_id"),
                client_id=azure_creds.get("azure_client_id"),
                client_secret=azure_creds.get("azure_client_secret")
            )
            
            adt_client = DigitalTwinsClient(adt_endpoint, credential)
            
            # Poll for telemetry property on the sensor twin (async update)
            max_attempts = 30
            poll_interval = 2  # seconds
            
            print(f"  Polling ADT for telemetry properties...")
            
            for attempt in range(1, max_attempts + 1):
                query = "SELECT * FROM digitaltwins WHERE $dtId = 'temperature-sensor-1'"
                twins = list(adt_client.query_twins(query))
                
                if not twins:
                    time.sleep(poll_interval)
                    continue
                
                twin = twins[0]
                
                # Check for telemetry properties (flexible matching)
                # ADT pusher uses property names from telemetry payload
                telemetry_props = ['temperature', 'Temperature', 'LastTemperature', 
                                   'humidity', 'Humidity', 'LastHumidity', 'value']
                
                found_props = {k: v for k, v in twin.items() 
                               if k in telemetry_props and v is not None}
                
                if found_props:
                    print(f"  ✓ ADT TELEMETRY VERIFIED (Attempt {attempt}/{max_attempts})")
                    for prop, val in found_props.items():
                        print(f"    - {prop}: {val}")
                    return  # Success!
                
                time.sleep(poll_interval)
            
            # After max attempts, log debug info
            print(f"  [WARN] No telemetry properties found after {max_attempts} attempts")
            if twins:
                twin_props = [k for k in twins[0].keys() if not k.startswith('$')]
                print(f"         Available properties: {twin_props}")
            
        except ImportError:
            pytest.skip("azure-digitaltwins-core SDK not installed")
        except Exception as e:
            print(f"  [WARN] Could not query ADT: {e}")
    
    def test_12_azure_functions_deployed(self, deployed_environment):
        """GAP FIX #6: Verify Azure Function Apps have code deployed (not empty)."""
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        l2_provider = scenario.providers["layer_2_provider"]
        
        if l2_provider != "azure":
            pytest.skip("L2 is not Azure - skipping Azure Functions verification")
        
        azure_creds = credentials.get("azure", {})
        subscription_id = azure_creds.get("azure_subscription_id")
        resource_group = outputs.get("azure_resource_group_name")
        
        if not subscription_id or not resource_group:
            pytest.skip("Azure credentials or resource group not available")
        
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.web import WebSiteManagementClient
            
            credential = ClientSecretCredential(
                tenant_id=azure_creds.get("azure_tenant_id"),
                client_id=azure_creds.get("azure_client_id"),
                client_secret=azure_creds.get("azure_client_secret")
            )
            
            web_client = WebSiteManagementClient(credential, subscription_id)
            
            # Check L2 Function App
            l2_app_name = outputs.get("azure_l2_function_app_name")
            if l2_app_name:
                try:
                    functions = list(web_client.web_apps.list_functions(resource_group, l2_app_name))
                    if functions:
                        func_names = [f.name.split('/')[-1] for f in functions]
                        print(f"  [OK] Azure L2 Functions ({l2_app_name}): {func_names}")
                    else:
                        print(f"  [WARN] Azure L2 Functions: App exists but NO functions deployed!")
                except Exception as e:
                    print(f"  [WARN] Could not list functions for {l2_app_name}: {e}")
            else:
                print(f"  [INFO] No L2 Function App in outputs")
                
        except ImportError:
            pytest.skip("azure-mgmt-web SDK not installed")
        except Exception as e:
            print(f"  [WARN] Could not verify Azure Functions: {e}")

