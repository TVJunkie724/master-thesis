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

    @patch('src.validator.get_provider_for_function')
    @patch('src.validator.validate_python_code_aws')
    def test_validate_function_endpoint(self, mock_validate_aws, mock_get_provider):
        mock_get_provider.return_value = "aws"
        mock_validate_aws.return_value = None
        
        payload = {
            "project_name": "test-proj",
            "function_name": "dispatcher",
            "filename": "lambda_function.py",
            "code": "def lambda_handler..."
        }
        
        response = client.post("/validate/function", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("valid for provider 'aws'", response.json()["message"])

if __name__ == '__main__':
    unittest.main()
