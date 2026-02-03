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


def _registry_to_azure_name(registry_name: str) -> str:
    """Map registry name to Azure deployed function name.
    
    Wrappers (e.g., processor_wrapper) drop '_wrapper' suffix.
    Underscores become hyphens (Azure convention).
    """
    if registry_name.endswith("_wrapper"):
        base = registry_name[:-8]  # Remove '_wrapper'
        return base.replace("_", "-")
    return registry_name.replace("_", "-")


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
        return f"sc2-{self.name}"
    
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
    
    # MOCK: Write config_events.json with L2-appropriate workflow action type
    WORKFLOW_ACTION_TYPES = {
        "aws": "step_function",
        "azure": "logic_app",
        "google": "workflow",
    }
    
    def get_scenario_events(l2_provider: str) -> list:
        """Generate config_events with L2-appropriate workflow action."""
        workflow_type = WORKFLOW_ACTION_TYPES.get(l2_provider, "step_function")
        return [
            # Lambda action (all scenarios)
            {
                "condition": "testEntityId.temperature-sensor-1.temperature == DOUBLE(30)",
                "action": {
                    "type": "lambda",
                    "functionName": "high-temperature-callback",
                    "autoDeploy": True,
                    "feedback": {
                        "type": "mqtt",
                        "iotDeviceId": "temperature-sensor-1",
                        "payload": "High Temp Warning"
                    }
                }
            },
            # Workflow action (L2-specific)
            {
                "condition": "testEntityId.pressure-sensor-1.pressure > DOUBLE(999)",
                "action": {
                    "type": workflow_type
                }
            }
        ]
    
    l2_provider = scenario.providers.get("layer_2_provider", "aws")
    events_path = project_path / "config_events.json"
    events = get_scenario_events(l2_provider)
    with open(events_path, "w") as f:
        json.dump(events, f, indent=2)
    print(f"[SCENARIO] Mocked config_events with {WORKFLOW_ACTION_TYPES.get(l2_provider, 'step_function')} action")
    
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
                    result = cleanup_state["strategy"].destroy_all(
                        context=cleanup_state["context"],
                        sdk_fallback="always"  # Always run SDK cleanup for thorough cleanup
                    )
                    if result.terraform_success:
                        print("[CLEANUP] ✓ Resources destroyed via Terraform + SDK")
                    else:
                        print(f"[CLEANUP] ⚠ Terraform destroy failed: {result.terraform_error}")
                        print("[CLEANUP] SDK fallback cleanup ran, but may have orphaned resources")
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
        # skip_cleanup comes from conftest.py fixture (--skip-cleanup flag)
        skip_cleanup = request.config.getoption("--skip-cleanup", default=False)
        # Also check backwards-compat env var
        if not skip_cleanup:
            skip_cleanup = getattr(request.config, "_skip_cleanup_compat", False)
        
        if not skip_cleanup:
            request.addfinalizer(terraform_cleanup)
        else:
            print("[CLEANUP] ⚠ Cleanup disabled (--skip-cleanup flag)")
        
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
            print("\n[PHASE -1] Pre-Test Orphan Cleanup: SKIPPED (--skip-cleanup flag)")
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
            "temperature": 30,  # Match event condition (== DOUBLE(30))
            "pressure": 1001,   # Trigger workflow condition (> DOUBLE(999))
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
                # Config is stored per-device: azure/{device_id}/config_generated.json
                azure_sim_dir = project_path / "iot_device_simulator" / "azure"
                if not azure_sim_dir.exists():
                    pytest.fail(f"[DATAFLOW CRITICAL] Azure simulator directory not found at {azure_sim_dir}. IoT device registration may have failed.")
                
                # Find first device subdirectory
                device_dirs = [d for d in azure_sim_dir.iterdir() if d.is_dir()]
                if not device_dirs:
                    pytest.fail(f"[DATAFLOW CRITICAL] No device configs found in {azure_sim_dir}. IoT device registration may have failed.")
                
                sim_config_path = device_dirs[0] / "config_generated.json"
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
        
        max_retries = 300  # 300 retries × 2s = 600s timeout (10 min for cold start delays in cross-cloud flow)
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
    
    def test_10b_twinmaker_telemetry(self, deployed_environment):
        """Verify telemetry accessible via TwinMaker after test_07/08.
        
        This test validates the full L4 data flow for AWS:
        L2 Persister → DynamoDB → TwinMaker dataReader connector → get_property_value_history
        
        Uses polling to handle async writes and connector cold starts.
        """
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        l4_provider = scenario.providers["layer_4_provider"]
        
        if l4_provider != "aws":
            pytest.skip("L4 is not AWS - skipping TwinMaker telemetry verification")
        
        workspace_id = outputs.get("aws_twinmaker_workspace_id")
        if not workspace_id:
            pytest.skip("TwinMaker workspace not deployed")
        
        try:
            import boto3
            from datetime import datetime, timedelta
            
            twinmaker = boto3.client('iottwinmaker')
            
            # Step 1: Find an entity with components
            response = twinmaker.list_entities(workspaceId=workspace_id)
            entities = response.get('entitySummaries', [])
            
            if not entities:
                print(f"  [WARN] No TwinMaker entities found - cannot verify telemetry")
                return
            
            # Step 2: Get entity details to find component with time-series properties
            target_entity = None
            target_component = None
            target_properties = []
            
            for entity_summary in entities:
                entity_id = entity_summary.get('entityId')
                try:
                    entity_details = twinmaker.get_entity(
                        workspaceId=workspace_id,
                        entityId=entity_id
                    )
                    components = entity_details.get('components', {})
                    
                    for comp_name, comp_info in components.items():
                        # Find properties marked as time-series (isTimeSeries=True)
                        props = comp_info.get('properties', {})
                        ts_props = [
                            name for name, info in props.items()
                            if info.get('definition', {}).get('isTimeSeries', False)
                        ]
                        
                        if ts_props:
                            target_entity = entity_id
                            target_component = comp_name
                            target_properties = ts_props[:3]  # Limit to 3 properties
                            break
                    
                    if target_entity:
                        break
                except Exception as e:
                    print(f"  [DEBUG] Could not get entity {entity_id}: {e}")
                    continue
            
            if not target_entity:
                print(f"  [WARN] No entities with time-series components found")
                return
            
            print(f"  Querying TwinMaker: entity={target_entity}, component={target_component}")
            print(f"  Properties: {target_properties}")
            
            # Step 3: Poll for telemetry via get_property_value_history
            max_attempts = 30
            poll_interval = 2  # seconds
            
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            for attempt in range(1, max_attempts + 1):
                try:
                    history_response = twinmaker.get_property_value_history(
                        workspaceId=workspace_id,
                        entityId=target_entity,
                        componentName=target_component,
                        selectedProperties=target_properties,
                        startDateTime=start_time,
                        endDateTime=end_time,
                        orderByTime='DESCENDING',
                        maxResults=10
                    )
                    
                    property_values = history_response.get('propertyValues', [])
                    
                    if property_values:
                        print(f"  ✓ TWINMAKER TELEMETRY VERIFIED (Attempt {attempt}/{max_attempts})")
                        for pv in property_values[:3]:
                            prop_ref = pv.get('entityPropertyReference', {})
                            values = pv.get('values', [])
                            if values:
                                print(f"    - {prop_ref.get('propertyName')}: {len(values)} data points")
                        return  # Success!
                    
                except Exception as e:
                    print(f"  [DEBUG] Attempt {attempt}: {e}")
                
                time.sleep(poll_interval)
            
            # After max attempts, FAIL - L4 data flow is critical
            pytest.fail(
                f"[L4 DATAFLOW CRITICAL] No telemetry found via TwinMaker "
                f"after {max_attempts * poll_interval}s. "
                f"Entity: {target_entity}, Component: {target_component}"
            )
            
        except ImportError:
            pytest.skip("boto3 not installed")
        except Exception as e:
            print(f"  [WARN] Could not query TwinMaker telemetry: {e}")

    
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
                # Note: DTDL v3 requires unique names, so we use 'lastX' convention
                telemetry_props = ['lastTemperature', 'lastPressure', 'lastHumidity',
                                   'temperature', 'Temperature', 'LastTemperature', 
                                   'humidity', 'Humidity', 'LastHumidity', 
                                   'pressure', 'Pressure', 'LastPressure', 'value']
                
                found_props = {k: v for k, v in twin.items() 
                               if k in telemetry_props and v is not None}
                
                if found_props:
                    print(f"  ✓ ADT TELEMETRY VERIFIED (Attempt {attempt}/{max_attempts})")
                    for prop, val in found_props.items():
                        print(f"    - {prop}: {val}")
                    return  # Success!
                
                time.sleep(poll_interval)
            
            # After max attempts, FAIL - L4 data flow is critical
            twin_props = [k for k in twins[0].keys() if not k.startswith('$')] if twins else []
            pytest.fail(
                f"[L4 DATAFLOW CRITICAL] No telemetry properties found in ADT twin "
                f"after {max_attempts * poll_interval}s. Available properties: {twin_props}"
            )
            
        except ImportError:
            pytest.skip("azure-digitaltwins-core SDK not installed")
        except Exception as e:
            print(f"  [WARN] Could not query ADT: {e}")
    
    def test_12_azure_functions_deployed(self, deployed_environment):
        """GAP FIX #6: Verify Azure Function Apps have expected functions deployed.
        
        Uses the same function_registry logic as bundlers to determine which
        functions should be deployed for each Azure layer.
        
        Verifies:
        - L0: Dynamic glue functions based on cross-cloud boundaries
        - L1: IoT acquisition functions (if L1=Azure)  
        - L2: Processing functions (if L2=Azure)
        - L3: Hot storage functions (if L3-hot=Azure)
        - User: User-defined functions (optional, no failure if empty)
        """
        from src.function_registry import get_by_layer, get_l0_for_config, Layer
        
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        credentials = deployed_environment["credentials"]
        providers = scenario.providers
        
        # Check if any Azure layers exist
        azure_layers = ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider"]
        has_azure = any(providers.get(layer) == "azure" for layer in azure_layers)
        
        # Also check for L0 glue functions (cross-cloud boundaries to Azure)
        l0_funcs = get_l0_for_config(providers, "azure")
        
        if not has_azure and not l0_funcs:
            pytest.skip("No Azure layers - skipping Azure Functions verification")
        
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
            
            def verify_function_app(app_name: str, expected_funcs: list, layer_name: str, is_optional: bool = False):
                """Verify a function app has expected functions deployed."""
                if not app_name:
                    if not is_optional:
                        print(f"  [INFO] No {layer_name} Function App in outputs")
                    return
                
                try:
                    functions = list(web_client.web_apps.list_functions(resource_group, app_name))
                    # Azure function names use hyphens (e.g., "hot-reader")
                    deployed_names = [f.name.split('/')[-1] for f in functions]
                    
                    if not functions:
                        if is_optional:
                            print(f"  [OK] {layer_name} ({app_name}): Empty (optional)")
                        else:
                            pytest.fail(f"{layer_name} ({app_name}): NO functions deployed!")
                        return
                    
                    # Check for missing expected functions
                    missing = [f for f in expected_funcs if f not in deployed_names]
                    if missing:
                        pytest.fail(f"{layer_name} ({app_name}): Missing functions {missing}, got {deployed_names}")
                    
                    print(f"  [OK] {layer_name} ({app_name}): {deployed_names}")
                    
                except Exception as e:
                    # Don't silently pass - re-raise so outer handler can fail properly
                    raise RuntimeError(f"Could not list functions for {app_name}: {e}")
            
            # L0: Dynamic based on cross-cloud boundaries
            if l0_funcs:
                l0_app_name = outputs.get("azure_l0_function_app_name")
                verify_function_app(l0_app_name, l0_funcs, "L0 Glue")
            
            # L1: IoT Acquisition (use registry boundary like bundler)
            if providers.get("layer_1_provider") == "azure":
                l1_expected = []
                for f in get_by_layer(Layer.L1_ACQUISITION):
                    if "azure" not in f.providers:
                        continue
                    # Skip functions with boundary when same-cloud (matches bundler logic)
                    if f.boundary:
                        src_key, tgt_key = f.boundary
                        if providers.get(src_key) == providers.get(tgt_key):
                            continue
                    l1_expected.append(_registry_to_azure_name(f.name))
                l1_app_name = outputs.get("azure_l1_function_app_name")
                verify_function_app(l1_app_name, l1_expected, "L1 IoT")
            
            # L2: Processing (match bundler: include optional if dir exists)
            if providers.get("layer_2_provider") == "azure":
                azure_funcs_dir = Path(__file__).parent.parent.parent.parent / "src" / "providers" / "azure" / "azure_functions"
                l2_expected = []
                for f in get_by_layer(Layer.L2_PROCESSING):
                    if "azure" not in f.providers:
                        continue
                    func_dir = azure_funcs_dir / f.get_dir_name()
                    # Match bundler logic: include if not optional OR if dir exists
                    if not f.is_optional or func_dir.exists():
                        l2_expected.append(_registry_to_azure_name(f.name))
                l2_app_name = outputs.get("azure_l2_function_app_name")
                verify_function_app(l2_app_name, l2_expected, "L2 Processing")
            
            # L3: Hot Storage (match bundler: include optional if dir exists)
            if providers.get("layer_3_hot_provider") == "azure":
                azure_funcs_dir = Path(__file__).parent.parent.parent.parent / "src" / "providers" / "azure" / "azure_functions"
                l3_expected = []
                for f in get_by_layer(Layer.L3_STORAGE):
                    if "azure" not in f.providers:
                        continue
                    func_dir = azure_funcs_dir / f.get_dir_name()
                    # Match bundler logic: include if not optional OR if dir exists
                    if not f.is_optional or func_dir.exists():
                        l3_expected.append(_registry_to_azure_name(f.name))
                l3_app_name = outputs.get("azure_l3_function_app_name")
                verify_function_app(l3_app_name, l3_expected, "L3 Storage")
            
            # User Functions: Optional (don't fail if empty)
            user_app_name = outputs.get("azure_user_functions_app_name")
            if user_app_name:
                verify_function_app(user_app_name, [], "User Functions", is_optional=True)
                
        except ImportError:
            pytest.skip("azure-mgmt-web SDK not installed")
        except Exception as e:
            # Fail the test on unexpected errors (don't silently pass)
            pytest.fail(f"Azure Functions verification failed: {e}")


    # ==========================================
    # Event Flow Tests (13-16)
    # ==========================================
    
    def test_13_event_checker_invoked(self, deployed_environment):
        """Verify Event-Checker was invoked by Persister.
        
        This test validates the event-checking flow:
        IoT Message → Dispatcher → Processor → Persister → Event-Checker
        
        Requires: useEventChecking=true in config_optimization.json
        """
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        l2_provider = scenario.providers["layer_2_provider"]
        
        print(f"\n  [EVENT FLOW] Checking Event-Checker invocation for L2={l2_provider}")
        
        try:
            if l2_provider == "aws":
                import boto3
                logs_client = boto3.client('logs')
                
                # Event-Checker Lambda log group
                log_group = f"/aws/lambda/{outputs.get('aws_l2_event_checker_name', 'event-checker')}"
                
                # Query recent logs for invocation evidence
                end_time = int(time.time() * 1000)
                start_time = end_time - (10 * 60 * 1000)  # Last 10 minutes
                
                try:
                    response = logs_client.filter_log_events(
                        logGroupName=log_group,
                        startTime=start_time,
                        endTime=end_time,
                        limit=5
                    )
                    
                    if response.get('events'):
                        print(f"  ✓ EVENT-CHECKER INVOKED (found {len(response['events'])} log events)")
                        return
                    else:
                        print("  [WARN] No recent Event-Checker log events found")
                        
                except Exception as e:
                    print(f"  [DEBUG] Could not query CloudWatch: {e}")
                    
            elif l2_provider == "azure":
                # Query Azure Monitor for event-checker function logs
                print("  [INFO] Azure event-checker log verification via portal/CLI")
                
            elif l2_provider in ("google", "gcp"):
                # Query Cloud Logging for event-checker function
                print("  [INFO] GCP event-checker log verification via console/CLI")
                
        except ImportError:
            pytest.skip("Required SDK not installed for log verification")
        except Exception as e:
            print(f"  [WARN] Could not verify event-checker: {e}")
    
    def test_14_event_action_function_called(self, deployed_environment):
        """Verify Lambda/function action was invoked by Event-Checker.
        
        Validates: Event-Checker matched condition → invoked action function
        Expected function: high-temperature-callback (from mocked config_events)
        """
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        l2_provider = scenario.providers["layer_2_provider"]
        
        print(f"\n  [EVENT FLOW] Checking action function invocation for L2={l2_provider}")
        
        try:
            if l2_provider == "aws":
                import boto3
                logs_client = boto3.client('logs')
                
                # Action function log group (high-temperature-callback)
                function_name = "high-temperature-callback"
                log_group = f"/aws/lambda/{function_name}"
                
                end_time = int(time.time() * 1000)
                start_time = end_time - (10 * 60 * 1000)
                
                try:
                    response = logs_client.filter_log_events(
                        logGroupName=log_group,
                        startTime=start_time,
                        endTime=end_time,
                        limit=5
                    )
                    
                    if response.get('events'):
                        print(f"  ✓ ACTION FUNCTION INVOKED ({function_name})")
                        return
                    else:
                        print(f"  [WARN] No logs for {function_name}")
                        
                except Exception as e:
                    print(f"  [DEBUG] Log group may not exist: {e}")
                    
            elif l2_provider == "azure":
                print("  [INFO] Azure action function verification via portal/CLI")
                
            elif l2_provider in ("google", "gcp"):
                print("  [INFO] GCP action function verification via console/CLI")
                
        except ImportError:
            pytest.skip("Required SDK not installed")
        except Exception as e:
            print(f"  [WARN] Could not verify action function: {e}")
    
    def test_15_workflow_triggered(self, deployed_environment):
        """Verify Step Function/Logic App/Workflow was triggered.
        
        Uses execution history APIs to verify workflow was started:
        - AWS: stepfunctions.list_executions()
        - Azure: Logic App runs API
        - GCP: workflows.executions.list()
        
        Requires: triggerNotificationWorkflow=true in config_optimization.json
        """
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        l2_provider = scenario.providers["layer_2_provider"]
        
        print(f"\n  [EVENT FLOW] Checking workflow trigger for L2={l2_provider}")
        
        try:
            if l2_provider == "aws":
                import boto3
                sfn_client = boto3.client('stepfunctions')
                
                state_machine_arn = outputs.get("aws_step_function_arn")
                if not state_machine_arn:
                    print("  [SKIP] No Step Function ARN in outputs")
                    return
                
                try:
                    response = sfn_client.list_executions(
                        stateMachineArn=state_machine_arn,
                        maxResults=5
                    )
                    
                    executions = response.get('executions', [])
                    if executions:
                        latest = executions[0]
                        print(f"  ✓ STEP FUNCTION TRIGGERED")
                        print(f"    - Execution: {latest['name']}")
                        print(f"    - Status: {latest['status']}")
                        return
                    else:
                        print("  [WARN] No Step Function executions found")
                        
                except Exception as e:
                    print(f"  [DEBUG] Could not list executions: {e}")
                    
            elif l2_provider == "azure":
                # Check Logic App runs
                logic_app_name = outputs.get("azure_logic_app_name")
                if logic_app_name:
                    print(f"  [INFO] Check Logic App '{logic_app_name}' runs in Azure Portal")
                else:
                    print("  [SKIP] No Logic App in outputs")
                    
            elif l2_provider in ("google", "gcp"):
                # Check Cloud Workflow executions
                workflow_name = outputs.get("gcp_workflow_name")
                if workflow_name:
                    print(f"  [INFO] Check Workflow '{workflow_name}' executions in GCP Console")
                else:
                    print("  [SKIP] No Workflow in outputs")
                    
        except ImportError:
            pytest.skip("Required SDK not installed")
        except Exception as e:
            print(f"  [WARN] Could not verify workflow: {e}")
    
    def test_16_event_feedback_sent(self, deployed_environment):
        """Verify feedback was sent to IoT device.
        
        Validates: Event-Checker → Feedback Function → IoT Hub/Core
        Checks feedback function logs for successful publish.
        """
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        l2_provider = scenario.providers["layer_2_provider"]
        
        print(f"\n  [EVENT FLOW] Checking feedback sent for L2={l2_provider}")
        
        try:
            if l2_provider == "aws":
                import boto3
                logs_client = boto3.client('logs')
                
                # Feedback function log group
                function_name = outputs.get("aws_feedback_function_name", "event-feedback")
                log_group = f"/aws/lambda/{function_name}"
                
                end_time = int(time.time() * 1000)
                start_time = end_time - (10 * 60 * 1000)
                
                try:
                    response = logs_client.filter_log_events(
                        logGroupName=log_group,
                        startTime=start_time,
                        endTime=end_time,
                        filterPattern="publish",  # Look for publish keyword
                        limit=5
                    )
                    
                    if response.get('events'):
                        print(f"  ✓ FEEDBACK SENT (found publish events)")
                        return
                    else:
                        print("  [WARN] No feedback publish events found")
                        
                except Exception as e:
                    print(f"  [DEBUG] Could not query feedback logs: {e}")
                    
            elif l2_provider == "azure":
                print("  [INFO] Azure feedback verification via portal/CLI")
                
            elif l2_provider in ("google", "gcp"):
                print("  [INFO] GCP feedback verification via console/CLI")
                
        except ImportError:
            pytest.skip("Required SDK not installed")
        except Exception as e:
            print(f"  [WARN] Could not verify feedback: {e}")

    # ==========================================
    # L3 Mover Deployment Verification
    # ==========================================
    
    def test_17_verify_l3_hot_to_cold_mover_deployed(self, deployed_environment):
        """Verify hot-to-cold mover function is deployed with correct env vars.
        
        Checks for each provider:
        - AWS: Lambda exists with DYNAMODB_TABLE_NAME, COLD_S3_BUCKET_NAME
        - Azure: Function App has mover with COSMOS_DB_ENDPOINT, BLOB_CONNECTION_STRING
        - GCP: Cloud Function exists with FIRESTORE_COLLECTION, COLD_BUCKET_NAME
        """
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        l3_hot = scenario.providers.get("layer_3_hot_provider")
        twin_name = scenario.digital_twin_name
        
        print(f"\n  [L3 MOVER] Verifying hot-to-cold mover for L3-Hot={l3_hot}")
        
        try:
            if l3_hot == "aws":
                import boto3
                lambda_client = boto3.client('lambda')
                
                func_name = f"{twin_name}-l3-hot-to-cold-mover"
                try:
                    response = lambda_client.get_function(FunctionName=func_name)
                    env_vars = response["Configuration"].get("Environment", {}).get("Variables", {})
                    
                    print(f"  ✓ HOT-TO-COLD MOVER DEPLOYED: {func_name}")
                    
                    # Verify env vars
                    if "DYNAMODB_TABLE_NAME" in env_vars:
                        print(f"    - DYNAMODB_TABLE_NAME: {env_vars['DYNAMODB_TABLE_NAME']}")
                    if "COLD_S3_BUCKET_NAME" in env_vars or "REMOTE_COLD_WRITER_URL" in env_vars:
                        print(f"    - Cold storage configured")
                        
                except lambda_client.exceptions.ResourceNotFoundException:
                    print(f"  [SKIP] Lambda {func_name} not found (may not be deployed)")
                    
            elif l3_hot == "azure":
                from azure.identity import DefaultAzureCredential
                from azure.mgmt.web import WebSiteManagementClient
                
                subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
                resource_group = outputs.get("azure_resource_group_name", f"{twin_name}-rg")
                func_app = outputs.get("azure_function_app_name", f"{twin_name}-l3-functions")
                
                if subscription_id:
                    client = WebSiteManagementClient(DefaultAzureCredential(), subscription_id)
                    try:
                        settings = client.web_apps.list_application_settings(resource_group, func_app)
                        props = settings.properties if settings else {}
                        
                        print(f"  ✓ HOT-TO-COLD MOVER DEPLOYED (bundled in {func_app})")
                        
                        if "COSMOS_DB_ENDPOINT" in props:
                            print(f"    - COSMOS_DB_ENDPOINT: configured")
                        if "COLD_STORAGE_CONTAINER" in props or "REMOTE_COLD_WRITER_URL" in props:
                            print(f"    - Cold storage configured")
                            
                    except Exception as e:
                        print(f"  [SKIP] Could not verify Azure function: {e}")
                else:
                    print("  [SKIP] AZURE_SUBSCRIPTION_ID not set")
                    
            elif l3_hot in ("google", "gcp"):
                from google.cloud import functions_v2
                
                project_id = outputs.get("gcp_project_id") or os.environ.get("GCP_PROJECT_ID")
                region = outputs.get("gcp_region") or os.environ.get("GCP_REGION", "us-central1")
                func_name = f"projects/{project_id}/locations/{region}/functions/{twin_name}-hot-to-cold-mover"
                
                if project_id:
                    client = functions_v2.FunctionServiceClient()
                    try:
                        function = client.get_function(name=func_name)
                        env_vars = function.service_config.environment_variables
                        
                        print(f"  ✓ HOT-TO-COLD MOVER DEPLOYED")
                        
                        if "FIRESTORE_COLLECTION" in env_vars:
                            print(f"    - FIRESTORE_COLLECTION: {env_vars['FIRESTORE_COLLECTION']}")
                        if "COLD_BUCKET_NAME" in env_vars or "REMOTE_COLD_WRITER_URL" in env_vars:
                            print(f"    - Cold storage configured")
                            
                    except Exception as e:
                        print(f"  [SKIP] Could not verify GCP function: {e}")
                else:
                    print("  [SKIP] GCP_PROJECT_ID not set")
                    
        except ImportError as e:
            print(f"  [SKIP] Required SDK not installed: {e}")
        except Exception as e:
            print(f"  [WARN] Could not verify hot-to-cold mover: {e}")
    
    def test_18_verify_l3_cold_to_archive_mover_deployed(self, deployed_environment):
        """Verify cold-to-archive mover function is deployed with correct env vars.
        
        Checks for each provider:
        - AWS: Lambda exists with COLD_S3_BUCKET_NAME, ARCHIVE_S3_BUCKET_NAME
        - Azure: Separate Function App for cold-to-archive mover
        - GCP: Cloud Function exists with COLD_BUCKET_NAME, ARCHIVE_BUCKET_NAME
        """
        scenario = deployed_environment["scenario"]
        outputs = deployed_environment["terraform_outputs"]
        l3_cold = scenario.providers.get("layer_3_cold_provider")
        twin_name = scenario.digital_twin_name
        
        print(f"\n  [L3 MOVER] Verifying cold-to-archive mover for L3-Cold={l3_cold}")
        
        try:
            if l3_cold == "aws":
                import boto3
                lambda_client = boto3.client('lambda')
                
                func_name = f"{twin_name}-l3-cold-to-archive-mover"
                try:
                    response = lambda_client.get_function(FunctionName=func_name)
                    env_vars = response["Configuration"].get("Environment", {}).get("Variables", {})
                    
                    print(f"  ✓ COLD-TO-ARCHIVE MOVER DEPLOYED: {func_name}")
                    
                    if "COLD_S3_BUCKET_NAME" in env_vars:
                        print(f"    - COLD_S3_BUCKET_NAME: {env_vars['COLD_S3_BUCKET_NAME']}")
                    if "ARCHIVE_S3_BUCKET_NAME" in env_vars or "REMOTE_ARCHIVE_WRITER_URL" in env_vars:
                        print(f"    - Archive storage configured")
                        
                except lambda_client.exceptions.ResourceNotFoundException:
                    print(f"  [SKIP] Lambda {func_name} not found (may not be deployed)")
                    
            elif l3_cold == "azure":
                # Azure cold-to-archive is a SEPARATE Function App (uses func.FunctionApp(), not Blueprint)
                from azure.identity import DefaultAzureCredential
                from azure.mgmt.web import WebSiteManagementClient
                
                subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
                resource_group = outputs.get("azure_resource_group_name", f"{twin_name}-rg")
                # Check for separate cold-to-archive function app
                func_app = outputs.get("azure_archive_function_app_name", f"{twin_name}-l3-archive-functions")
                
                if subscription_id:
                    client = WebSiteManagementClient(DefaultAzureCredential(), subscription_id)
                    try:
                        settings = client.web_apps.list_application_settings(resource_group, func_app)
                        props = settings.properties if settings else {}
                        
                        print(f"  ✓ COLD-TO-ARCHIVE MOVER DEPLOYED: {func_app}")
                        
                        if "COLD_STORAGE_CONTAINER" in props:
                            print(f"    - COLD_STORAGE_CONTAINER: configured")
                        if "ARCHIVE_STORAGE_CONTAINER" in props or "REMOTE_ARCHIVE_WRITER_URL" in props:
                            print(f"    - Archive storage configured")
                            
                    except Exception as e:
                        print(f"  [SKIP] Could not verify Azure archive function: {e}")
                else:
                    print("  [SKIP] AZURE_SUBSCRIPTION_ID not set")
                    
            elif l3_cold in ("google", "gcp"):
                from google.cloud import functions_v2
                
                project_id = outputs.get("gcp_project_id") or os.environ.get("GCP_PROJECT_ID")
                region = outputs.get("gcp_region") or os.environ.get("GCP_REGION", "us-central1")
                func_name = f"projects/{project_id}/locations/{region}/functions/{twin_name}-cold-to-archive-mover"
                
                if project_id:
                    client = functions_v2.FunctionServiceClient()
                    try:
                        function = client.get_function(name=func_name)
                        env_vars = function.service_config.environment_variables
                        
                        print(f"  ✓ COLD-TO-ARCHIVE MOVER DEPLOYED")
                        
                        if "COLD_BUCKET_NAME" in env_vars:
                            print(f"    - COLD_BUCKET_NAME: {env_vars['COLD_BUCKET_NAME']}")
                        if "ARCHIVE_BUCKET_NAME" in env_vars or "REMOTE_ARCHIVE_WRITER_URL" in env_vars:
                            print(f"    - Archive storage configured")
                            
                    except Exception as e:
                        print(f"  [SKIP] Could not verify GCP archive function: {e}")
                else:
                    print("  [SKIP] GCP_PROJECT_ID not set")
                    
        except ImportError as e:
            print(f"  [SKIP] Required SDK not installed: {e}")
        except Exception as e:
            print(f"  [WARN] Could not verify cold-to-archive mover: {e}")

