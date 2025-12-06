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

if __name__ == '__main__':
    unittest.main()
