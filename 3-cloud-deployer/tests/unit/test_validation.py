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
            "gcp": {"gcp_project_id": "x", "gcp_credentials_file": "x", "gcp_region": "x"}
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
        # Missing main
        with self.assertRaises(ValueError) as cm:
             validator.validate_state_machine_content(CONSTANTS.GOOGLE_STATE_MACHINE_FILE, {"steps": []})
        self.assertIn("Missing required keys", str(cm.exception))

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
        self.assertIn("must have a 'main(req)'", str(cm.exception))

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
        self.assertIn("Missing event-feedback function in zip", str(cm.exception))

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

    def test_verify_project_structure_corrupt_configs(self):
        """Test verify structure with invalid content on disk"""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data="{invalid")), \
             self.assertRaises(ValueError) as cm:
                 validator.verify_project_structure("p", project_path="/app")
        self.assertIn("Invalid content", str(cm.exception))

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_verify_project_structure_workflow_checks(self, mock_json, mock_open, mock_exists):
        # Scenario: Optimization needs workflow, Provider is Azure via config
        mock_exists.return_value = True
        
        opt_conf = {"result": {"optimization": {"triggerNotificationWorkflow": True}}}
        # verify_project_structure logic:
        # 1. Basic Verify (reads all config files via open, calls validate_config_content)
        # 2. Open optimization -> return opt_conf
        # 3. Read Providers -> return azure
        # 4. Check State Machine File -> must exist and validate
        
        # We need a robust side_effect for json.load to handle different files being opened
        # But open() returns the same mock object in simplest form.
        
        # Simulating file reads by path is hard with standard mock_open. 
        # Using a specialized side_effect for open logic:
        
        file_contents = {
            CONSTANTS.CONFIG_OPTIMIZATION_FILE: json.dumps(opt_conf),
            CONSTANTS.CONFIG_PROVIDERS_FILE: json.dumps({"layer_2_provider": "azure"}),
            CONSTANTS.AZURE_STATE_MACHINE_FILE: json.dumps({"definition": {}}) # Valid Azure
        }
        
        def open_side_effect(file, mode='r'):
            # Extract basename to match our simple map
            basename = os.path.basename(file)
            if basename in file_contents:
                return io.StringIO(file_contents[basename])
            return io.StringIO("{}") # Default empty JSON for others
        
        mock_open.side_effect = open_side_effect
        
        # We also need json.load to work with StringIO
        mock_json.side_effect = json.load # Use real json.load on StringIO
        
        # Mocking validate_config_content to pass (too complex to mock its internal json.loads)
        with patch('validator.validate_config_content'):
             validator.verify_project_structure("test-proj", project_path="/app")
             # Should pass if Azure State Machine is found and valid

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

if __name__ == '__main__':
    unittest.main()
