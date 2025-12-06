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

class TestValidation(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_validate_config_content_valid_config(self):
        """Test valid config.json"""
        content = {
            "digital_twin_name": "test-twin",
            "auth_files_path": "/tmp",
            "endpoint": "iot.amazonaws.com",
            "root_ca_cert_path": "root.pem",
            "topic": "topic",
            "payload_file_path": "payload.json",
            "hot_storage_size_in_days": 30,
            "cold_storage_size_in_days": 90,
            "mode": "advanced"
        }
        # Should not raise
        file_manager.validate_config_content(CONSTANTS.CONFIG_FILE, json.dumps(content))

    def test_validate_config_content_invalid_key(self):
        """Test missing key in config.json"""
        content = {
            "digital_twin_name": "test-twin"
            # Missing other keys
        }
        with self.assertRaises(ValueError) as cm:
            file_manager.validate_config_content(CONSTANTS.CONFIG_FILE, json.dumps(content))
        self.assertIn("Missing key", str(cm.exception))

    def test_validate_config_events_nested(self):
        """Test nested validation in config_events.json"""
        # Invalid Action
        content = [{
            "condition": "x > 5",
            "action": { "type": "lambda" } # Missing functionName
        }]
        with self.assertRaises(ValueError) as cm:
            file_manager.validate_config_content(CONSTANTS.CONFIG_EVENTS_FILE, json.dumps(content))
        self.assertIn("missing 'type' or 'functionName'", str(cm.exception))

        # Valid Action
        valid_content = [{
            "condition": "x > 5",
            "action": { "type": "lambda", "functionName": "my-func" }
        }]
        file_manager.validate_config_content(CONSTANTS.CONFIG_EVENTS_FILE, json.dumps(valid_content))

    def test_validate_zip_slip_prevention(self):
        """Test prevention of Zip Slip vulnerability"""
        # Create malicious zip in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            # Add malicious file FIRST to ensure it's checked before content validation
            zf.writestr('../../../evil.txt', 'evil')

            # Add ALL required files to pass the first check (Missing Files)
            for req_file in CONSTANTS.REQUIRED_CONFIG_FILES:
                 # Minimal valid content is NOT needed if malicious file is checked first
                 zf.writestr(req_file, "{}")
        
        zip_buffer.seek(0)
        
        with self.assertRaises(ValueError) as cm:
            file_manager.validate_project_zip(zip_buffer)
        
        self.assertIn("Zip Slip Prevention", str(cm.exception))

    @patch('file_manager.get_provider_for_function')
    def test_validate_python_code_aws_valid(self, mock_provider):
        code = """
import json
def lambda_handler(event, context):
    return "ok"
"""
        file_manager.validate_python_code_aws(code)

    def test_validate_python_code_aws_invalid(self):
        code = """
def main():
    pass
"""
        with self.assertRaises(ValueError) as cm:
            file_manager.validate_python_code_aws(code)
        self.assertIn("must have a 'lambda_handler(event, context)'", str(cm.exception))

    def test_validate_python_code_syntax_error(self):
        """Test handling of Python syntax errors"""
        code = "def invalid_syntax("
        with self.assertRaises(ValueError) as cm:
            file_manager.validate_python_code_aws(code)
        self.assertIn("Python Syntax Error", str(cm.exception))

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_get_provider_for_function(self, mock_json_load, mock_open, mock_exists):
        # Setup mocks
        mock_exists.return_value = True # config_providers.json exists
        mock_json_load.return_value = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws"
        }
        
        # Test Direct Mapping
        provider = file_manager.get_provider_for_function("my-proj", "dispatcher")
        self.assertEqual(provider, "aws")
        
        # Test Implicit Mapping
        provider = file_manager.get_provider_for_function("my-proj", "data-processor")
        self.assertEqual(provider, "aws")

    @patch('os.path.exists')
    def test_get_provider_missing_config(self, mock_exists):
        mock_exists.return_value = False
        with self.assertRaises(ValueError) as cm:
             file_manager.get_provider_for_function("my-proj", "dispatcher")
        self.assertIn("Missing Project Configuration", str(cm.exception))

    @patch('file_manager.validate_config_content')
    @patch('builtins.open')
    @patch('os.path.exists')
    @patch('json.load')
    def test_verify_project_structure_success(self, mock_json, mock_exists, mock_open, mock_validate):
        # Mock ALL config files existing
        mock_exists.return_value = True 
        mock_json.return_value = {} # Default empty config
        
        file_manager.verify_project_structure("test-proj")
        
    @patch('os.path.exists')
    def test_verify_project_structure_missing_project(self, mock_exists):
        mock_exists.return_value = False
        with self.assertRaises(ValueError) as cm:
            file_manager.verify_project_structure("missing-proj")
        self.assertIn("does not exist", str(cm.exception))

    @patch('os.path.exists')
    def test_verify_project_structure_missing_config(self, mock_exists):
        # Mock project dir exists, but config.json missing
        mock_exists.side_effect = lambda p: "upload" in p if CONSTANTS.CONFIG_FILE in p else True
        # Logic: if path contains config file, return False. Else True (dir exists).
        # Actually easier to use side_effect list or map if paths known.
        # But verify_project_structure builds paths dynamically.
        
        def exists_side_effect(path):
            if path.endswith(CONSTANTS.CONFIG_FILE):
                return False
            return True
        mock_exists.side_effect = exists_side_effect
        
        with self.assertRaises(ValueError) as cm:
            file_manager.verify_project_structure("test-proj")
        self.assertIn("Missing required configuration file", str(cm.exception))

    @patch('json.load')
    @patch('builtins.open')
    @patch('os.path.exists')
    @patch('file_manager.validate_config_content')
    def test_verify_project_structure_optimization_events_missing(self, mock_valid, mock_exists, mock_open, mock_json):
        # Setup: Configs exist. Optimization has useEventChecking=True.
        # But config_events.json mapping/load fails or missing items?
        # Actually verify_project_structure reads config_optimization.
        
        # Mocks
        mock_exists.return_value = True
        
        # Mock JSON loads
        def json_side_effect(f):
            # If reading optimization
            if "config_optimization" in str(f):  # Mock file object or use path? 
                # open() returns a magic mock, not path. 
                # Need to inspect call args of open?
                pass
            return {}

        # Simpler: Mock return values based on call order is fragile.
        # Let's mock json.load to return specific dicts based on what open was called with?
        # Too complex.
        
        # Strategy: verify_project_structure reads opt, then events.
        # We set json.load side effect to return sequence.
        
        opt_config = {"result": {"optimization": {"useEventChecking": True}}}
        events_config = [{"action": {"type": "lambda", "functionName": "missing-func"}}]
        
        # Verify loop starts...
        # 1. Basic Config Verification uses open().read() and json.loads(), NOT json.load().
        # 2. Optimization Dependency Checks calls json.load() for optimization file.
        # 3. Then calls json.load() for events file if optimization enabled.
        
        mock_json.side_effect = [
            opt_config, # 1. Optimization File
            events_config # 2. Events File
        ]
        
        # Mock exists to return False for the function folder
        def exists_side_effect(path):
            if "missing-func" in path:
                return False
            return True
        mock_exists.side_effect = exists_side_effect
        
        with self.assertRaises(ValueError) as cm:
            file_manager.verify_project_structure("test-proj")
        self.assertIn("Missing code for event action", str(cm.exception))


    def test_validate_state_machine_content_aws_success(self):
        """Test valid AWS ASL content"""
        content = json.dumps({"StartAt": "A", "States": {}})
        file_manager.validate_state_machine_content(CONSTANTS.AWS_STATE_MACHINE_FILE, content)

    def test_validate_state_machine_content_aws_fail(self):
        """Test invalid AWS ASL content (missing States)"""
        content = json.dumps({"StartAt": "A"})
        with self.assertRaises(ValueError) as cm:
            file_manager.validate_state_machine_content(CONSTANTS.AWS_STATE_MACHINE_FILE, content)
        self.assertIn("Missing required keys", str(cm.exception))

    def test_validate_state_machine_content_azure_success(self):
        """Test valid Azure Logic App content"""
        content = json.dumps({"definition": {"$schema": "..."}})
        file_manager.validate_state_machine_content(CONSTANTS.AZURE_STATE_MACHINE_FILE, content)

    def test_validate_state_machine_content_mismatch(self):
        """Test uploading AWS content as Azure file"""
        content = json.dumps({"StartAt": "A", "States": {}})
        # Valid AWS content, but checking against Azure requirements (needs definition)
        with self.assertRaises(ValueError) as cm:
            file_manager.validate_state_machine_content(CONSTANTS.AZURE_STATE_MACHINE_FILE, content)
        self.assertIn("Missing required keys", str(cm.exception))

    def test_validate_state_machine_content_google_success(self):
        """Test valid Google Workflow content"""
        CONSTANTS.GOOGLE_STATE_MACHINE_FILE = "google_cloud_workflow.json"
        CONSTANTS.STATE_MACHINE_SIGNATURES[CONSTANTS.GOOGLE_STATE_MACHINE_FILE] = ["main"] 
        content = json.dumps({"main": {"steps": []}, "steps": []}) # Mock valid
        file_manager.validate_state_machine_content(CONSTANTS.GOOGLE_STATE_MACHINE_FILE, content)

    def _create_valid_minimal_config_content(self, filename):
        if filename in [CONSTANTS.CONFIG_IOT_DEVICES_FILE, CONSTANTS.CONFIG_EVENTS_FILE, CONSTANTS.CONFIG_HIERARCHY_FILE]:
            return "[]"
        elif filename == CONSTANTS.CONFIG_FILE:
             return json.dumps({
                "digital_twin_name": "test", "auth_files_path": ".", "endpoint": "e", 
                "root_ca_cert_path": "r", "topic": "t", "payload_file_path": "p",
                "hot_storage_size_in_days": 1, "cold_storage_size_in_days": 1, "mode": "basic"
            })
        elif filename == CONSTANTS.CONFIG_OPTIMIZATION_FILE:
            return json.dumps({"result": {}})
        else:
            return "{}"

    def test_validate_project_zip_invalid_state_machine(self):
        """Test zip containing invalid state machine file"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            # required files
            for req in CONSTANTS.REQUIRED_CONFIG_FILES:
                zf.writestr(req, self._create_valid_minimal_config_content(req))
                
            # Valid filename but invalid content for AWS
            # Must put it in correct folder structure if we rely on "state_machines" in path? 
            # Logic uses basename match for signature check.
            zf.writestr(f"template/state_machines/{CONSTANTS.AWS_STATE_MACHINE_FILE}", '{"StartAt": "A"}') # Missing States

        zip_buffer.seek(0)
        with self.assertRaises(ValueError) as cm:
            file_manager.validate_project_zip(zip_buffer)
        self.assertIn("State Machine validation failed", str(cm.exception))

    def test_validate_project_zip_missing_dependency(self):
        """Test zip with optimization enabled but missing state machine"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            # required files
            for req in CONSTANTS.REQUIRED_CONFIG_FILES:
                if req == CONSTANTS.CONFIG_OPTIMIZATION_FILE:
                    zf.writestr(req, json.dumps({"result": {"optimization": {"triggerNotificationWorkflow": True}}}))
                else:
                    zf.writestr(req, self._create_valid_minimal_config_content(req))
            
            # Missing state machine file!
            
        zip_buffer.seek(0)
        with self.assertRaises(ValueError) as cm:
            file_manager.validate_project_zip(zip_buffer)
        self.assertIn("Missing state machine definition", str(cm.exception))


if __name__ == '__main__':
    unittest.main()
