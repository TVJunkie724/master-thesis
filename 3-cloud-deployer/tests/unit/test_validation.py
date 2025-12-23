import unittest
import json
import io
import zipfile
import sys
import os
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

import constants as CONSTANTS
import file_manager
import validator

class TestValidation(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    # ==========================================
    # 1. Config Content Validation Tests
    # ==========================================
    def test_validate_config_content_valid_config(self):
        """Test valid config.json"""
        content = {
            "digital_twin_name": "test-twin",
            "hot_storage_size_in_days": 30,
            "cold_storage_size_in_days": 90,
            "mode": "advanced"
        }
        validator.validate_config_content(CONSTANTS.CONFIG_FILE, json.dumps(content))
        # Test distinct input types (dict)
        validator.validate_config_content(CONSTANTS.CONFIG_FILE, content)

    def test_validate_config_content_invalid_json(self):
        """Test invalid JSON string"""
        with self.assertRaises(ValueError) as cm:
            validator.validate_config_content(CONSTANTS.CONFIG_FILE, "{invalid")
        self.assertIn("Invalid JSON content", str(cm.exception))

    def test_validate_config_content_invalid_key(self):
        """Test missing key in config.json"""
        content = {"digital_twin_name": "test-twin"}
        with self.assertRaises(ValueError) as cm:
            validator.validate_config_content(CONSTANTS.CONFIG_FILE, content)
        self.assertIn("Missing key", str(cm.exception))

    def test_validate_config_credentials_valid(self):
        """Test valid credentials config"""
        content = {
            "aws": {"aws_access_key_id": "x", "aws_secret_access_key": "x", "aws_region": "x"},
            "azure": {"azure_subscription_id": "x", "azure_tenant_id": "x", "azure_client_id": "x", "azure_client_secret": "x", "azure_region": "x", "azure_region_iothub": "x", "azure_region_digital_twin": "x"},
            "gcp": {"gcp_billing_account": "x", "gcp_credentials_file": "x", "gcp_region": "x"}
        }
        validator.validate_config_content(CONSTANTS.CONFIG_CREDENTIALS_FILE, content)

    def test_validate_config_credentials_missing_field(self):
        """Test missing field in credentials"""
        content = {
            "aws": {"aws_access_key_id": "x"} # Missing secret & region
        }
        with self.assertRaises(ValueError) as cm:
             validator.validate_config_content(CONSTANTS.CONFIG_CREDENTIALS_FILE, content)
        self.assertIn("Missing required credential field 'aws_secret_access_key'", str(cm.exception))

    def test_validate_config_file_list_malformed(self):
        """Test list-based config receiving dict or missing keys"""
        # IOT file expects list of objects with required keys (id, properties)
        with self.assertRaises(ValueError) as cm:
             validator.validate_config_content(CONSTANTS.CONFIG_IOT_DEVICES_FILE, [{"other": "1"}]) # Missing required keys
        self.assertIn("Missing key 'id'", str(cm.exception))

    def test_validate_config_events_complex(self):
        """Test nested validation in config_events.json"""
        # 1. Missing Action Fields (functionName)
        content = [{"condition": "x", "action": {"type": "lambda"}}]
        with self.assertRaises(ValueError) as cm:
            validator.validate_config_content(CONSTANTS.CONFIG_EVENTS_FILE, content)
        self.assertIn("missing 'type' or 'functionName'", str(cm.exception))

        # 2. Missing Feedback Fields
        content = [{"condition": "x", "action": {"type": "lambda", "functionName": "x", "feedback": {"iotDeviceId": "d"}}}] # Missing payload
        with self.assertRaises(ValueError) as cm:
            validator.validate_config_content(CONSTANTS.CONFIG_EVENTS_FILE, content)
        self.assertIn("missing 'iotDeviceId' or 'payload'", str(cm.exception))

        # 3. Valid
        content = [{"condition": "x", "action": {"type": "lambda", "functionName": "x", "feedback": {"iotDeviceId": "d", "payload": "p"}}}]
        validator.validate_config_content(CONSTANTS.CONFIG_EVENTS_FILE, content)

    def test_validate_config_hierarchy(self):
        """Test AWS hierarchy validation using the new dedicated function"""
        # Component invalid - missing componentTypeId/iotDeviceId
        content = [{"id": "1", "type": "component", "name": "c1"}]
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("must have 'componentTypeId' or 'iotDeviceId'", str(cm.exception))

        # Component Valid
        content = [{"id": "1", "type": "component", "name": "c1", "iotDeviceId": "d1"}]
        validator.validate_aws_hierarchy_content(content)
        
        # Missing type field
        content = [{"id": "1", "name": "c1"}]
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("missing required 'type' field", str(cm.exception))
        
        # Not an array
        content = {"id": "1", "type": "entity"}
        with self.assertRaises(ValueError) as cm:
            validator.validate_aws_hierarchy_content(content)
        self.assertIn("must be a JSON array", str(cm.exception))

    # ==========================================
    # 2. State Machine Content Tests
    # ==========================================
    def test_validate_state_machine_invalid_json(self):
        with self.assertRaises(ValueError):
            validator.validate_state_machine_content(CONSTANTS.AWS_STATE_MACHINE_FILE, "{")

    def test_validate_state_machine_content_azure_special(self):
        """Test Azure with and without 'definition' key behavior"""
        # 1. Valid with definition
        validator.validate_state_machine_content(CONSTANTS.AZURE_STATE_MACHINE_FILE, {"definition": {}})
        
        # 2. Invalid without definition
        with self.assertRaises(ValueError) as cm:
             validator.validate_state_machine_content(CONSTANTS.AZURE_STATE_MACHINE_FILE, {"other": {}})
        self.assertIn("Invalid State Machine format", str(cm.exception))

    def test_validate_state_machine_content_google(self):
        """Test GCP workflow validation - 'main' at top level, 'steps' inside 'main'."""
        # 1. Missing 'main' entirely
        with self.assertRaises(ValueError) as cm:
             validator.validate_state_machine_content(CONSTANTS.GOOGLE_STATE_MACHINE_FILE, {"steps": []})
        self.assertIn("missing required 'main' block", str(cm.exception))
        
        # 2. 'main' present but missing 'steps' inside
        with self.assertRaises(ValueError) as cm:
             validator.validate_state_machine_content(CONSTANTS.GOOGLE_STATE_MACHINE_FILE, {"main": {}})
        self.assertIn("missing required 'steps' array", str(cm.exception))
        
        # 3. Valid - 'main' with 'steps' inside (nested structure)
        valid_gcp = {"main": {"steps": [{"init": {"assign": [{"result": "ok"}]}}]}}
        validator.validate_state_machine_content(CONSTANTS.GOOGLE_STATE_MACHINE_FILE, valid_gcp)

    # ==========================================
    # 3. Code Validation Tests (Azure/Google)
    # ==========================================
    def test_validate_python_code_azure_valid(self):
        code = "def main(req): pass"
        validator.validate_python_code_azure(code)

    def test_validate_python_code_azure_invalid(self):
        code = "def other_func(): pass"
        with self.assertRaises(ValueError) as cm:
            validator.validate_python_code_azure(code)
        self.assertIn("must have a 'main(req)'", str(cm.exception))
        
        code_args = "def main(other): pass"
        with self.assertRaises(ValueError) as cm:
            validator.validate_python_code_azure(code_args)
        self.assertIn("main(req)", str(cm.exception))  # Updated: new message uses "signature: main(req)"

    def test_validate_python_code_google_valid(self):
        code = "def any_func(request): pass"
        validator.validate_python_code_google(code)

    def test_validate_python_code_google_invalid(self):
        code = "x = 1" # No function
        with self.assertRaises(ValueError) as cm:
            validator.validate_python_code_google(code)
        self.assertIn("must define at least one function", str(cm.exception))

    # ==========================================
    # 4. Project Structure (Zip & Disk)
    # ==========================================
    def _create_zip_with_configs(self, configs=None, extra_files=None):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            # Write all required config files
            for req in CONSTANTS.REQUIRED_CONFIG_FILES:
                content = "{}"
                if req in [CONSTANTS.CONFIG_IOT_DEVICES_FILE, CONSTANTS.CONFIG_EVENTS_FILE, CONSTANTS.CONFIG_HIERARCHY_FILE]:
                     content = "[]"
                elif req == CONSTANTS.CONFIG_FILE:
                    content = json.dumps({
                        "digital_twin_name": "t", 
                        "hot_storage_size_in_days": 1, "cold_storage_size_in_days": 1, "mode": "b"
                    })
                elif req == CONSTANTS.CONFIG_PROVIDERS_FILE:
                    content = json.dumps({
                        "layer_1_provider": "aws",
                        "layer_2_provider": "aws",
                        "layer_3_hot_provider": "aws",
                        "layer_4_provider": "aws"
                    })
                
                if configs and req in configs:
                    content = json.dumps(configs[req])
                
                zf.writestr(req, content)
            
            # Explicitly add optimization file (not in REQUIRED_CONFIG_FILES)
            opt_content = json.dumps({"result": {}})
            if configs and CONSTANTS.CONFIG_OPTIMIZATION_FILE in configs:
                opt_content = json.dumps(configs[CONSTANTS.CONFIG_OPTIMIZATION_FILE])
            zf.writestr(CONSTANTS.CONFIG_OPTIMIZATION_FILE, opt_content)
            
            # Add hierarchy file for L4 provider (required by new cross-config validation)
            # Default providers config sets layer_4_provider=aws
            # Skip if already in extra_files to avoid duplicate warnings
            providers_config = configs.get(CONSTANTS.CONFIG_PROVIDERS_FILE) if configs else None
            layer_4_provider = (providers_config or {}).get("layer_4_provider", "aws")
            
            aws_hierarchy_path = "twin_hierarchy/aws_hierarchy.json"
            azure_hierarchy_path = "twin_hierarchy/azure_hierarchy.json"
            
            already_in_extras = extra_files and (
                aws_hierarchy_path in extra_files or azure_hierarchy_path in extra_files
            )
            
            if not already_in_extras:
                if layer_4_provider == "aws":
                    zf.writestr(aws_hierarchy_path, "[]")
                elif layer_4_provider == "azure":
                    zf.writestr(azure_hierarchy_path, json.dumps({
                        "models": [], "twins": [], "relationships": []
                    }))
            
            # Add function directory placeholder for L2 provider (required by check_provider_function_directory)
            layer_2_provider = (providers_config or {}).get("layer_2_provider", "aws")
            func_dir_map = {"aws": "lambda_functions", "azure": "azure_functions", "google": "cloud_functions", "gcp": "cloud_functions"}
            func_dir = func_dir_map.get(layer_2_provider)
            
            # Add processor folders for each device (required by check_processor_folders_match_devices)
            iot_config = configs.get(CONSTANTS.CONFIG_IOT_DEVICES_FILE) if configs else None
            if iot_config and func_dir:
                # Map provider to expected file in processor folder
                processor_file_map = {"aws": "lambda_function.py", "azure": "function_app.py", "google": "main.py", "gcp": "main.py"}
                proc_file = processor_file_map.get(layer_2_provider, "lambda_function.py")
                for device in iot_config:
                    device_id = device.get("id")
                    if device_id:
                        proc_path = f"{func_dir}/processors/{device_id}/{proc_file}"
                        # Only add if not already in extra_files
                        if not extra_files or proc_path not in extra_files:
                            zf.writestr(proc_path, "def process(data: dict) -> dict:\n    return data\n")
            
            if func_dir:
                func_placeholder = f"{func_dir}/placeholder.txt"
                # Only add if not already in extra_files
                if not extra_files or not any(f.startswith(func_dir + "/") for f in extra_files):
                    zf.writestr(func_placeholder, "placeholder")
            
            if extra_files:
                for name, content in extra_files.items():
                    zf.writestr(name, content)
        zip_buffer.seek(0)
        return zip_buffer

    def test_validate_zip_feedback_missing(self):
        """Test zip with returnFeedbackToDevice=True but missing feedback logic"""
        opt = {"result": {"inputParamsUsed": {"returnFeedbackToDevice": True}}}
        zip_buf = self._create_zip_with_configs({CONSTANTS.CONFIG_OPTIMIZATION_FILE: opt})
        with self.assertRaises(ValueError) as cm:
             validator.validate_project_zip(zip_buf)
        self.assertIn("Missing event-feedback function", str(cm.exception))

    def test_validate_zip_feedback_success(self):
        """Test zip with returnFeedbackToDevice=True AND feedback logic present"""
        opt = {"result": {"inputParamsUsed": {"returnFeedbackToDevice": True}}}
        extras = {f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/event-feedback/lambda_function.py": ""}
        zip_buf = self._create_zip_with_configs({CONSTANTS.CONFIG_OPTIMIZATION_FILE: opt}, extras)
        validator.validate_project_zip(zip_buf)

    def test_validate_zip_event_checks_missing_code(self):
        """Test useEventChecking=True but missing function code"""
        opt = {"result": {"inputParamsUsed": {"useEventChecking": True}}}
        events = [{"condition": "x", "action": {"type": "lambda", "functionName": "my-func"}}]
        configs = {CONSTANTS.CONFIG_OPTIMIZATION_FILE: opt, CONSTANTS.CONFIG_EVENTS_FILE: events}
        
        zip_buf = self._create_zip_with_configs(configs)
        with self.assertRaises(ValueError) as cm:
            validator.validate_project_zip(zip_buf)
        self.assertIn("Missing code for event action", str(cm.exception))

    def test_validate_zip_workflow_missing_provider_conf(self):
        """Test triggerNotificationWorkflow check defaulting to AWS if provider config missing/empty"""
        opt = {"result": {"inputParamsUsed": {"triggerNotificationWorkflow": True}}}
        # Default AWS -> expects aws_step_function.json
        configs = {CONSTANTS.CONFIG_OPTIMIZATION_FILE: opt}
        zip_buf = self._create_zip_with_configs(configs)
        
        with self.assertRaises(ValueError) as cm:
             validator.validate_project_zip(zip_buf)
        self.assertIn("Missing state machine definition", str(cm.exception))
        self.assertIn("aws_step_function.json", str(cm.exception))

    def test_validate_zip_workflow_disabled_skips_state_machine_validation(self):
        """Test state machine validation is SKIPPED when triggerNotificationWorkflow=False."""
        # triggerNotificationWorkflow=False means state machine file is NOT required
        opt = {"result": {"inputParamsUsed": {"triggerNotificationWorkflow": False}}}
        configs = {CONSTANTS.CONFIG_OPTIMIZATION_FILE: opt}
        # No state machine file included - should still pass
        zip_buf = self._create_zip_with_configs(configs)
        validator.validate_project_zip(zip_buf)  # Should NOT raise

    def test_validate_project_directory_corrupt_configs(self):
        """Test validation with invalid JSON content on disk."""
        import tempfile
        from pathlib import Path
        from src.validation.directory_validator import validate_project_directory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            (project_dir / "config.json").write_text("{invalid")
            
            with self.assertRaises(ValueError) as cm:
                validate_project_directory(project_dir)
            # Should fail on invalid JSON
            error_msg = str(cm.exception).lower()
            self.assertTrue("json" in error_msg or "invalid" in error_msg)

    def test_validate_project_directory_workflow_checks(self):
        """Test workflow flag requires state machine."""
        import tempfile
        from pathlib import Path
        from src.validation.directory_validator import validate_project_directory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            # Create minimal project with triggerNotificationWorkflow=True
            (project_dir / "config.json").write_text(json.dumps({
                "digital_twin_name": "t", "hot_storage_size_in_days": 1,
                "cold_storage_size_in_days": 1, "mode": "b"
            }))
            (project_dir / "config_providers.json").write_text(json.dumps({
                "layer_1_provider": "aws", "layer_2_provider": "aws",
                "layer_3_hot_provider": "aws", "layer_4_provider": "aws"
            }))
            (project_dir / "config_iot_devices.json").write_text("[]")
            (project_dir / "config_events.json").write_text("[]")
            (project_dir / "config_credentials.json").write_text(json.dumps({
                "aws": {"aws_access_key_id": "x", "aws_secret_access_key": "x", "aws_region": "us-east-1"}
            }))
            (project_dir / "config_optimization.json").write_text(json.dumps({
                "result": {"inputParamsUsed": {"triggerNotificationWorkflow": True}}
            }))
            (project_dir / "twin_hierarchy").mkdir()
            (project_dir / "twin_hierarchy/aws_hierarchy.json").write_text("[]")
            (project_dir / "lambda_functions").mkdir()
            (project_dir / "lambda_functions/placeholder.txt").write_text("dummy")  # Needs a file to pass check_provider_function_directory
            # Missing state_machines directory - should fail
            
            with self.assertRaises(ValueError) as cm:
                validate_project_directory(project_dir)
            self.assertIn("state machine", str(cm.exception).lower())

    # ==========================================
    # 5. Project Provider Resolution
    # ==========================================
    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_get_provider_corrupt_config(self, mock_json, mock_open, mock_exists):
        mock_exists.return_value = True
        mock_json.side_effect = json.JSONDecodeError("msg", "doc", 0)
        with self.assertRaises(ValueError) as cm:
             validator.get_provider_for_function("p", "f", project_path="/app")
        self.assertIn("is corrupted", str(cm.exception))

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_get_provider_missing_layer_key(self, mock_json, mock_open, mock_exists):
        mock_exists.return_value = True
        # Config exists but missing key for L2
        mock_json.return_value = {"layer_1_provider": "aws"}
        
        with self.assertRaises(ValueError) as cm:
             # persister -> layer_2
             validator.get_provider_for_function("p", "persister", project_path="/app") 
        self.assertIn("configuration missing for layer", str(cm.exception))

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_get_provider_unknown_func_raises(self, mock_json, mock_open, mock_exists):
        """Unknown function now raises ValueError instead of silent fallback."""
        mock_exists.return_value = True
        mock_json.return_value = {"layer_2_provider": "google"}
        
        # Unknown func -> Raises ValueError (fail-fast, no silent fallback)
        with self.assertRaises(ValueError) as cm:
            validator.get_provider_for_function("p", "unknown-func", project_path="/app")
        self.assertIn("Unknown function", str(cm.exception))
        self.assertIn("Cannot determine provider layer", str(cm.exception))

    # ==========================================
    # 6. Cross-Config Validation (NEW TESTS)
    # ==========================================
    
    def test_validate_zip_payloads_valid_device_reference(self):
        """Test payloads.json with valid iotDeviceId reference."""
        iot = [{"id": "device-1", "properties": []}]
        configs = {CONSTANTS.CONFIG_IOT_DEVICES_FILE: iot}
        extras = {
            f"{CONSTANTS.IOT_DEVICE_SIMULATOR_DIR_NAME}/{CONSTANTS.PAYLOADS_FILE}": json.dumps([
                {"iotDeviceId": "device-1", "payload": {}}
            ])
        }
        zip_buf = self._create_zip_with_configs(configs, extras)
        validator.validate_project_zip(zip_buf)  # Should pass

    def test_validate_zip_payloads_invalid_device_reference(self):
        """Test payloads.json with unknown iotDeviceId raises error."""
        iot = [{"id": "device-1", "properties": []}]
        configs = {CONSTANTS.CONFIG_IOT_DEVICES_FILE: iot}
        extras = {
            CONSTANTS.PAYLOADS_FILE: json.dumps([
                {"iotDeviceId": "unknown-device", "payload": {}}
            ])
        }
        zip_buf = self._create_zip_with_configs(configs, extras)
        with self.assertRaises(ValueError) as cm:
            validator.validate_project_zip(zip_buf)
        self.assertIn("unknown device", str(cm.exception).lower())
        self.assertIn("unknown-device", str(cm.exception))

    def test_validate_zip_payloads_multiple_devices(self):
        """Test payloads.json with multiple valid devices."""
        iot = [
            {"id": "device-1", "properties": []},
            {"id": "device-2", "properties": []}
        ]
        configs = {CONSTANTS.CONFIG_IOT_DEVICES_FILE: iot}
        extras = {
            f"{CONSTANTS.IOT_DEVICE_SIMULATOR_DIR_NAME}/{CONSTANTS.PAYLOADS_FILE}": json.dumps([
                {"iotDeviceId": "device-1", "payload": {}},
                {"iotDeviceId": "device-2", "payload": {}}
            ])
        }
        zip_buf = self._create_zip_with_configs(configs, extras)
        validator.validate_project_zip(zip_buf)  # Should pass

    def test_validate_zip_credentials_missing_for_provider(self):
        """Test credentials missing for a configured provider raises error."""
        providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure",  # Needs azure credentials
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }
        # AWS credentials present but missing azure entirely
        credentials = {"aws": {
            "aws_access_key_id": "x", 
            "aws_secret_access_key": "y", 
            "aws_region": "us-east-1"
        }}
        configs = {
            CONSTANTS.CONFIG_PROVIDERS_FILE: providers,
            CONSTANTS.CONFIG_CREDENTIALS_FILE: credentials
        }
        extras = {"twin_hierarchy/azure_hierarchy.json": json.dumps({"models": [], "twins": [], "relationships": []})}
        zip_buf = self._create_zip_with_configs(configs, extras)
        with self.assertRaises(ValueError) as cm:
            validator.validate_project_zip(zip_buf)
        self.assertIn("Missing credentials", str(cm.exception))
        self.assertIn("azure", str(cm.exception))

    def test_validate_zip_credentials_all_providers_present(self):
        """Test credentials present for all configured providers."""
        providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "azure"
        }
        credentials = {
            "aws": {
                "aws_access_key_id": "x", 
                "aws_secret_access_key": "y", 
                "aws_region": "us-east-1"
            },
            "azure": {
                "azure_subscription_id": "z",
                "azure_tenant_id": "t",
                "azure_client_id": "c",
                "azure_client_secret": "s",
                "azure_region": "eastus",
                "azure_region_iothub": "eastus",
                "azure_region_digital_twin": "eastus"
            }
        }
        configs = {
            CONSTANTS.CONFIG_PROVIDERS_FILE: providers,
            CONSTANTS.CONFIG_CREDENTIALS_FILE: credentials
        }
        extras = {"twin_hierarchy/azure_hierarchy.json": json.dumps({"models": [], "twins": [], "relationships": []})}
        zip_buf = self._create_zip_with_configs(configs, extras)
        validator.validate_project_zip(zip_buf)  # Should pass

    def test_validate_zip_hierarchy_aws_missing(self):
        """Test aws_hierarchy.json missing when layer_4_provider=aws."""
        providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }
        configs = {CONSTANTS.CONFIG_PROVIDERS_FILE: providers}
        # Note: We need to override the helper's auto-add of hierarchy
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for req in CONSTANTS.REQUIRED_CONFIG_FILES:
                content = "{}"
                if req in [CONSTANTS.CONFIG_IOT_DEVICES_FILE, CONSTANTS.CONFIG_EVENTS_FILE]:
                    content = "[]"
                elif req == CONSTANTS.CONFIG_FILE:
                    content = json.dumps({"digital_twin_name": "t", "hot_storage_size_in_days": 1, "cold_storage_size_in_days": 1, "mode": "b"})
                elif req == CONSTANTS.CONFIG_PROVIDERS_FILE:
                    content = json.dumps(providers)
                zf.writestr(req, content)
            zf.writestr(CONSTANTS.CONFIG_OPTIMIZATION_FILE, json.dumps({"result": {}}))
            # Add function directory placeholder for L2 provider
            zf.writestr("lambda_functions/placeholder.txt", "placeholder")
            # Deliberately NOT adding aws_hierarchy.json
        zip_buffer.seek(0)
        
        with self.assertRaises(ValueError) as cm:
            validator.validate_project_zip(zip_buffer)
        self.assertIn("Missing hierarchy file", str(cm.exception))
        self.assertIn("aws_hierarchy.json", str(cm.exception))

    def test_validate_zip_hierarchy_azure_present(self):
        """Test azure_hierarchy.json present when layer_4_provider=azure."""
        providers = {
            "layer_1_provider": "azure",
            "layer_2_provider": "azure",
            "layer_3_hot_provider": "azure",
            "layer_4_provider": "azure"
        }
        configs = {CONSTANTS.CONFIG_PROVIDERS_FILE: providers}
        extras = {"twin_hierarchy/azure_hierarchy.json": json.dumps({
            "models": [], "twins": [], "relationships": []
        })}
        zip_buf = self._create_zip_with_configs(configs, extras)
        validator.validate_project_zip(zip_buf)  # Should pass

    def test_validate_zip_hierarchy_google_no_file_required(self):
        """Test Google provider doesn't require hierarchy file."""
        providers = {
            "layer_1_provider": "google",
            "layer_2_provider": "google",
            "layer_3_hot_provider": "google",
            "layer_4_provider": "google"
        }
        configs = {CONSTANTS.CONFIG_PROVIDERS_FILE: providers}
        # No hierarchy file added - should still pass for Google
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for req in CONSTANTS.REQUIRED_CONFIG_FILES:
                content = "{}"
                if req in [CONSTANTS.CONFIG_IOT_DEVICES_FILE, CONSTANTS.CONFIG_EVENTS_FILE]:
                    content = "[]"
                elif req == CONSTANTS.CONFIG_FILE:
                    content = json.dumps({"digital_twin_name": "t", "hot_storage_size_in_days": 1, "cold_storage_size_in_days": 1, "mode": "b"})
                elif req == CONSTANTS.CONFIG_PROVIDERS_FILE:
                    content = json.dumps(providers)
                zf.writestr(req, content)
            zf.writestr(CONSTANTS.CONFIG_OPTIMIZATION_FILE, json.dumps({"result": {}}))
            # Add function directory placeholder for L2 provider (google)
            zf.writestr("cloud_functions/placeholder.txt", "placeholder")
        zip_buffer.seek(0)
        validator.validate_project_zip(zip_buffer)  # Should pass for Google (no L4 hierarchy)


class TestProviderDirectoryValidation(unittest.TestCase):
    """Tests for provider directory validation logic."""
    
    def test_provider_directory_exists(self):
        """Test validation passes when provider directory exists with files."""
        from src.validation.core import check_provider_function_directory, ValidationContext
        import constants as CONSTANTS
        
        ctx = ValidationContext()
        # Mock file list correctly
        ctx.all_files = [f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/func/process.py"]
        mock_accessor = MagicMock()
        
        # Should not raise
        check_provider_function_directory(mock_accessor, ctx, "aws")

    def test_provider_directory_missing(self):
        """Test validation fails when provider directory has no files."""
        from src.validation.core import check_provider_function_directory, ValidationContext
        
        ctx = ValidationContext()
        ctx.all_files = ["azure_functions/func/process.py"] # Wrong provider
        mock_accessor = MagicMock()
        
        with self.assertRaises(ValueError) as cm:
            check_provider_function_directory(mock_accessor, ctx, "aws")
        self.assertIn("Missing function directory", str(cm.exception))
        self.assertIn("lambda_functions", str(cm.exception))

    def test_provider_directory_skipped_if_no_provider(self):
        """Test check is skipped if no provider configured."""
        from src.validation.core import check_provider_function_directory, ValidationContext
        
        ctx = ValidationContext()
        ctx.all_files = [] 
        mock_accessor = MagicMock()
        
        # Should return early, not raise
        check_provider_function_directory(mock_accessor, ctx, "")

    def test_provider_directory_unknown_provider_raises(self):
        """Test check raises for unknown provider."""
        from src.validation.core import check_provider_function_directory, ValidationContext
        
        ctx = ValidationContext()
        ctx.all_files = []
        mock_accessor = MagicMock()
        
        with self.assertRaises(ValueError) as cm:
            check_provider_function_directory(mock_accessor, ctx, "invalid_provider")
        self.assertIn("Unknown layer_2_provider", str(cm.exception))


class TestPayloadsValidation(unittest.TestCase):
    """Tests for payloads.json validation."""
    
    def test_check_payloads_vs_devices_invalid_json_raises(self):
        """Test that invalid JSON in payloads.json raises ValueError."""
        import tempfile
        from pathlib import Path
        from src.validation.directory_validator import validate_project_directory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            # Create minimal valid project structure (matching test_validate_project_directory_workflow_checks pattern)
            (project_dir / "config.json").write_text(json.dumps({
                "digital_twin_name": "t", "hot_storage_size_in_days": 1,
                "cold_storage_size_in_days": 1, "mode": "b"
            }))
            (project_dir / "config_providers.json").write_text(json.dumps({
                "layer_1_provider": "aws", "layer_2_provider": "aws",
                "layer_3_hot_provider": "aws", "layer_4_provider": "aws"
            }))
            (project_dir / "config_iot_devices.json").write_text("[]")
            (project_dir / "config_events.json").write_text("[]")
            (project_dir / "config_credentials.json").write_text(json.dumps({
                "aws": {"aws_access_key_id": "x", "aws_secret_access_key": "x", "aws_region": "us-east-1"}
            }))
            (project_dir / "config_optimization.json").write_text(json.dumps({"result": {"inputParamsUsed": {}}}))
            (project_dir / "twin_hierarchy").mkdir()
            (project_dir / "twin_hierarchy/aws_hierarchy.json").write_text("[]")
            (project_dir / "lambda_functions").mkdir()
            (project_dir / "lambda_functions/placeholder.txt").write_text("dummy")
            # Create INVALID payloads.json
            (project_dir / "payloads.json").write_text("{invalid json")
            
            with self.assertRaises(ValueError) as cm:
                validate_project_directory(project_dir)
            self.assertIn("payloads.json", str(cm.exception))


class TestStateMachineValidation(unittest.TestCase):
    """Comprehensive tests for check_state_machines in core.py."""
    
    def test_state_machine_skipped_when_workflow_disabled(self):
        """Test state machine validation is SKIPPED when triggerNotificationWorkflow=False."""
        from src.validation.core import check_state_machines, ValidationContext
        
        ctx = ValidationContext()
        ctx.opt_config = {"result": {"inputParamsUsed": {"triggerNotificationWorkflow": False}}}
        ctx.prov_config = {"layer_2_provider": "aws"}
        ctx.all_files = []  # No state machine file
        mock_accessor = MagicMock()
        
        # Should NOT raise - validation is skipped
        check_state_machines(mock_accessor, ctx)
    
    def test_state_machine_skipped_when_no_opt_config(self):
        """Test state machine validation is SKIPPED when opt_config is empty."""
        from src.validation.core import check_state_machines, ValidationContext
        
        ctx = ValidationContext()
        ctx.opt_config = {}  # Empty - no triggerNotificationWorkflow key
        ctx.prov_config = {"layer_2_provider": "aws"}
        ctx.all_files = []
        mock_accessor = MagicMock()
        
        # Should NOT raise - no workflow flag defaults to skip
        check_state_machines(mock_accessor, ctx)
    
    def test_state_machine_aws_validates_correct_file(self):
        """Test AWS provider validates aws_step_function.json only."""
        from src.validation.core import check_state_machines, ValidationContext
        import constants as CONSTANTS
        
        ctx = ValidationContext()
        ctx.opt_config = {"result": {"inputParamsUsed": {"triggerNotificationWorkflow": True}}}
        ctx.prov_config = {"layer_2_provider": "aws"}
        ctx.all_files = [f"state_machines/{CONSTANTS.AWS_STATE_MACHINE_FILE}"]
        
        mock_accessor = MagicMock()
        # Return valid AWS step function content
        mock_accessor.read_text.return_value = json.dumps({"StartAt": "Init", "States": {}})
        
        # Should NOT raise - valid AWS state machine
        check_state_machines(mock_accessor, ctx)
        mock_accessor.read_text.assert_called_once()
    
    def test_state_machine_azure_validates_correct_file(self):
        """Test Azure provider validates azure_logic_app.json only."""
        from src.validation.core import check_state_machines, ValidationContext
        import constants as CONSTANTS
        
        ctx = ValidationContext()
        ctx.opt_config = {"result": {"inputParamsUsed": {"triggerNotificationWorkflow": True}}}
        ctx.prov_config = {"layer_2_provider": "azure"}
        ctx.all_files = [f"state_machines/{CONSTANTS.AZURE_STATE_MACHINE_FILE}"]
        
        mock_accessor = MagicMock()
        mock_accessor.read_text.return_value = json.dumps({"definition": {}})
        
        check_state_machines(mock_accessor, ctx)
        mock_accessor.read_text.assert_called_once()
    
    def test_state_machine_google_validates_correct_file(self):
        """Test Google provider validates google_cloud_workflow.json with nested steps."""
        from src.validation.core import check_state_machines, ValidationContext
        import constants as CONSTANTS
        
        ctx = ValidationContext()
        ctx.opt_config = {"result": {"inputParamsUsed": {"triggerNotificationWorkflow": True}}}
        ctx.prov_config = {"layer_2_provider": "google"}
        ctx.all_files = [f"state_machines/{CONSTANTS.GOOGLE_STATE_MACHINE_FILE}"]
        
        mock_accessor = MagicMock()
        # Valid GCP workflow - 'steps' is INSIDE 'main'
        mock_accessor.read_text.return_value = json.dumps({"main": {"steps": []}})
        
        check_state_machines(mock_accessor, ctx)
        mock_accessor.read_text.assert_called_once()
    
    def test_state_machine_google_invalid_missing_steps(self):
        """Test Google workflow fails when 'main' exists but 'steps' is missing."""
        from src.validation.core import check_state_machines, ValidationContext
        import constants as CONSTANTS
        
        ctx = ValidationContext()
        ctx.opt_config = {"result": {"inputParamsUsed": {"triggerNotificationWorkflow": True}}}
        ctx.prov_config = {"layer_2_provider": "google"}
        ctx.all_files = [f"state_machines/{CONSTANTS.GOOGLE_STATE_MACHINE_FILE}"]
        
        mock_accessor = MagicMock()
        # Invalid - 'main' exists but no 'steps' inside
        mock_accessor.read_text.return_value = json.dumps({"main": {}})
        
        with self.assertRaises(ValueError) as cm:
            check_state_machines(mock_accessor, ctx)
        self.assertIn("missing required 'steps'", str(cm.exception))
    
    def test_state_machine_ignores_other_providers_files(self):
        """Test AWS validation ignores GCP/Azure state machine files present."""
        from src.validation.core import check_state_machines, ValidationContext
        import constants as CONSTANTS
        
        ctx = ValidationContext()
        ctx.opt_config = {"result": {"inputParamsUsed": {"triggerNotificationWorkflow": True}}}
        ctx.prov_config = {"layer_2_provider": "aws"}
        # AWS file present, GCP file also present but should be IGNORED
        ctx.all_files = [
            f"state_machines/{CONSTANTS.AWS_STATE_MACHINE_FILE}",
            f"state_machines/{CONSTANTS.GOOGLE_STATE_MACHINE_FILE}"
        ]
        
        mock_accessor = MagicMock()
        mock_accessor.read_text.return_value = json.dumps({"StartAt": "Init", "States": {}})
        
        check_state_machines(mock_accessor, ctx)
        # Should only read AWS file, not GCP
        self.assertEqual(mock_accessor.read_text.call_count, 1)


class TestDigitalTwinNameValidation(unittest.TestCase):
    """Tests for validate_digital_twin_name in validator.py."""
    
    def test_valid_name(self):
        """Test valid digital twin name passes."""
        validator.validate_digital_twin_name("my-twin-123")
        validator.validate_digital_twin_name("test_twin")
        validator.validate_digital_twin_name("Twin-Name_01")
    
    def test_name_too_long(self):
        """Test name exceeding 30 characters raises error."""
        long_name = "a" * 31
        with self.assertRaises(ValueError) as cm:
            validator.validate_digital_twin_name(long_name)
        self.assertIn("exceeds", str(cm.exception))
    
    def test_name_invalid_characters(self):
        """Test name with invalid characters raises error."""
        with self.assertRaises(ValueError) as cm:
            validator.validate_digital_twin_name("my twin")  # Space
        self.assertIn("invalid characters", str(cm.exception))
        
        with self.assertRaises(ValueError) as cm:
            validator.validate_digital_twin_name("my.twin")  # Period
        self.assertIn("invalid characters", str(cm.exception))


class TestAzureRegionValidation(unittest.TestCase):
    """Tests for validate_azure_region_for_consumption_plan in validator.py."""
    
    def test_valid_region_passes(self):
        """Test supported regions pass validation."""
        validator.validate_azure_region_for_consumption_plan("westeurope")
        validator.validate_azure_region_for_consumption_plan("eastus")
        validator.validate_azure_region_for_consumption_plan("northeurope")
    
    def test_unsupported_region_raises(self):
        """Test unsupported region (italynorth) raises error."""
        with self.assertRaises(ValueError) as cm:
            validator.validate_azure_region_for_consumption_plan("italynorth")
        self.assertIn("does NOT support Consumption Plan", str(cm.exception))
        self.assertIn("westeurope", str(cm.exception))  # Should suggest alternative


class TestSceneAssetsValidation(unittest.TestCase):
    """Tests for check_scene_assets in core.py."""
    
    def test_scene_assets_skipped_when_disabled(self):
        """Test scene assets check is SKIPPED when needs3DModel=False."""
        from src.validation.core import check_scene_assets, ValidationContext
        
        ctx = ValidationContext()
        ctx.opt_config = {"result": {"inputParamsUsed": {"needs3DModel": False}}}
        ctx.prov_config = {"layer_4_provider": "aws"}
        mock_accessor = MagicMock()
        
        # Should NOT raise - check is skipped
        check_scene_assets(mock_accessor, ctx)
    
    def test_scene_assets_aws_required_files(self):
        """Test AWS scene assets requires scene.glb and scene.json."""
        from src.validation.core import check_scene_assets, ValidationContext
        
        ctx = ValidationContext()
        ctx.opt_config = {"result": {"inputParamsUsed": {"needs3DModel": True}}}
        ctx.prov_config = {"layer_4_provider": "aws"}
        
        mock_accessor = MagicMock()
        mock_accessor.file_exists.return_value = False  # Files missing
        
        with self.assertRaises(ValueError) as cm:
            check_scene_assets(mock_accessor, ctx)
        self.assertIn("Missing scene asset", str(cm.exception))
    
    def test_scene_assets_google_skipped(self):
        """Test Google L4 provider does not require scene assets."""
        from src.validation.core import check_scene_assets, ValidationContext
        
        ctx = ValidationContext()
        ctx.opt_config = {"result": {"inputParamsUsed": {"needs3DModel": True}}}
        ctx.prov_config = {"layer_4_provider": "google"}  # Google has no managed L4
        mock_accessor = MagicMock()
        
        # Should NOT raise - Google doesn't have scene requirements
        check_scene_assets(mock_accessor, ctx)


if __name__ == '__main__':
    unittest.main()
