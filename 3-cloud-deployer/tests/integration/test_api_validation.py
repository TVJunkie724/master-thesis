from fastapi.testclient import TestClient
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add root and src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from rest_api import app 

client = TestClient(app)

class TestValidationAPI(unittest.TestCase):

    @patch('src.validator.validate_project_zip')
    def test_validate_zip_endpoint(self, mock_validate):
        # Mock successful validation
        mock_validate.return_value = None 
        
        files = {'file': ('test.zip', b'dummy content', 'application/zip')}
        response = client.post("/validate/zip", files=files)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("valid and secure", response.json()["message"])

    @patch('src.validator.validate_project_zip')
    def test_validate_zip_endpoint_failure(self, mock_validate):
        # Mock validation failure
        mock_validate.side_effect = ValueError("Zip Slip deteced")
        
        files = {'file': ('test.zip', b'dummy content', 'application/zip')}
        response = client.post("/validate/zip", files=files)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("Zip Slip deteced", response.json()["detail"])

    @patch('src.validator.validate_config_content')
    def test_validate_config_endpoint_enum(self, mock_validate):
        # Test that Enum works (e.g. 'events' is accepted)
        mock_validate.return_value = None
        
        files = {'file': ('config.json', b'{}', 'application/json')}
        # Using correct enum value
        response = client.post("/validate/config/events", files=files)
        
        self.assertEqual(response.status_code, 200)
        
        # Test Invalid Enum
        response = client.post("/validate/config/invalid_type", files=files)
        self.assertEqual(response.status_code, 422) # FastAPI validation error for Enum

    @patch('src.validator.validate_python_code_aws')
    def test_validate_function_code_endpoint(self, mock_validate_aws):
        """Test new function-code endpoint with file upload."""
        mock_validate_aws.return_value = None
        
        code = b"def lambda_handler(event, context):\n    return {'statusCode': 200}"
        files = {'file': ('lambda_function.py', code, 'text/x-python')}
        
        response = client.post("/validate/function-code?provider=aws", files=files)
        self.assertEqual(response.status_code, 200)
        self.assertIn("valid for aws", response.json()["message"])

    @patch('src.validator.validate_state_machine_content')
    def test_validate_state_machine_endpoint(self, mock_validate):
        """Test state machine validation with required file."""
        mock_validate.return_value = None
        
        sm_content = b'{"StartAt": "Init", "States": {}}'
        files = {'file': ('aws_step_function.json', sm_content, 'application/json')}
        
        response = client.post("/validate/state-machine?provider=aws", files=files)
        self.assertEqual(response.status_code, 200)
        self.assertIn("valid for aws", response.json()["message"])

    @patch('src.validator.validate_simulator_payloads')
    def test_validate_payloads_endpoint(self, mock_validate):
        """Test payload structure validation."""
        mock_validate.return_value = (True, [], [])
        
        payload_content = b'[{"iotDeviceId": "device-1"}]'
        files = {'file': ('payloads.json', payload_content, 'application/json')}
        
        response = client.post("/validate/simulator/payloads", files=files)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])

    def test_validate_payloads_with_devices_endpoint(self):
        """Test cross-validation of payloads against devices config."""
        payloads = b'[{"iotDeviceId": "device-1"}]'
        devices = b'[{"id": "device-1", "properties": []}]'
        
        files = [
            ('payloads_file', ('payloads.json', payloads, 'application/json')),
            ('devices_file', ('config_iot_devices.json', devices, 'application/json'))
        ]
        
        response = client.post("/validate/payloads-with-devices", files=files)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertIn("device-1", response.json()["devices_found"])

    def test_validate_payloads_with_devices_invalid_device(self):
        """Test that missing device IDs are detected."""
        payloads = b'[{"iotDeviceId": "device-unknown"}]'
        devices = b'[{"id": "device-1", "properties": []}]'
        
        files = [
            ('payloads_file', ('payloads.json', payloads, 'application/json')),
            ('devices_file', ('config_iot_devices.json', devices, 'application/json'))
        ]
        
        response = client.post("/validate/payloads-with-devices", files=files)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["valid"])
        self.assertTrue(any("device-unknown" in e for e in response.json()["errors"]))

if __name__ == '__main__':
    unittest.main()
