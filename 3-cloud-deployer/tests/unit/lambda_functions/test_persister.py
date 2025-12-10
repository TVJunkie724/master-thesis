
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import importlib.util

# Helper to import the lambda module dynamically
def load_lambda_module(path):
    spec = importlib.util.spec_from_file_location("lambda_function", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lambda_function"] = module
    spec.loader.exec_module(module)
    return module

# Path to the lambda function
PERSISTER_PATH = "src/providers/aws/lambda_functions/persister/lambda_function.py"

class TestPersisterLambda(unittest.TestCase):
    def setUp(self):
        self.mock_dynamodb = MagicMock()
        self.mock_lambda = MagicMock()
        self.mock_boto3 = MagicMock()
        self.mock_boto3.resource.return_value = self.mock_dynamodb
        self.mock_boto3.client.return_value = self.mock_lambda
        
        self.boto3_patch = patch('boto3.resource', return_value=self.mock_dynamodb)
        self.client_patch = patch('boto3.client', return_value=self.mock_lambda)
        self.boto3_patch.start()
        self.client_patch.start()
        
        # Patch environment BEFORE loading module
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": '{"name": "test-twin"}',
            "DYNAMODB_TABLE_NAME": "test-dynamodb-table",
            "EVENT_CHECKER_LAMBDA_NAME": "test-event-checker",
            "USE_EVENT_CHECKING": "false" 
        })
        self.env_patch.start()
        
        # Load module AFTER environment is set
        self.lambda_module = load_lambda_module(PERSISTER_PATH)

    def tearDown(self):
        self.boto3_patch.stop()
        self.client_patch.stop()
        self.env_patch.stop()

    def test_invoke_event_checker_disabled(self):
        """Test that Event Checker is NOT invoked when disabled."""
        os.environ["USE_EVENT_CHECKING"] = "false"
        
        event = {"iotDeviceId": "device1", "payload": {"temp": 20}, "time": "2023-01-01T00:00:00Z"}
        self.lambda_module.lambda_handler(event, None)
        
        # Verify call to DynamoDB (Persister logic)
        # Assuming table.put_item is called
        # self.mock_dynamodb.Table.return_value.put_item.assert_called() 
        
        # Verify NO invoke
        self.mock_lambda.invoke.assert_not_called()

    def test_invoke_event_checker_enabled(self):
        """Test that Event Checker IS invoked when enabled."""
        os.environ["USE_EVENT_CHECKING"] = "true"
        
        event = {"iotDeviceId": "device1", "payload": {"temp": 20}, "time": "2023-01-01T00:00:00Z"}
        self.lambda_module.lambda_handler(event, None)
        
        # Verify invoke
        self.mock_lambda.invoke.assert_called_with(
            FunctionName="test-event-checker",
            InvocationType='Event',
            Payload=unittest.mock.ANY
        )

if __name__ == '__main__':
    unittest.main()
