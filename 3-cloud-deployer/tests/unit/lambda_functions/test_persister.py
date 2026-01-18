
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
        
        event = {"device_id": "device1", "payload": {"temp": 20}, "timestamp": "2023-01-01T00:00:00Z"}
        self.lambda_module.lambda_handler(event, None)
        
        # Verify call to DynamoDB (Persister logic)
        # Assuming table.put_item is called
        # self.mock_dynamodb.Table.return_value.put_item.assert_called() 
        
        # Verify NO invoke
        self.mock_lambda.invoke.assert_not_called()

    def test_invoke_event_checker_enabled(self):
        """Test that Event Checker IS invoked when enabled."""
        os.environ["USE_EVENT_CHECKING"] = "true"
        
        event = {"device_id": "device1", "payload": {"temp": 20}, "timestamp": "2023-01-01T00:00:00Z"}
        self.lambda_module.lambda_handler(event, None)
        
        # Verify invoke
        self.mock_lambda.invoke.assert_called_with(
            FunctionName="test-event-checker",
            InvocationType='Event',
            Payload=unittest.mock.ANY
        )


class TestPersisterAdtPush(unittest.TestCase):
    """Tests for ADT push functionality in Persister Lambda."""
    
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

    def tearDown(self):
        self.boto3_patch.stop()
        self.client_patch.stop()
        if hasattr(self, 'env_patch'):
            self.env_patch.stop()

    def _load_with_env(self, extra_env=None):
        """Load lambda module with specified environment."""
        env = {
            "DIGITAL_TWIN_INFO": '{"name": "test-twin"}',
            "DYNAMODB_TABLE_NAME": "test-dynamodb-table",
            "EVENT_CHECKER_LAMBDA_NAME": "test-event-checker",
            "USE_EVENT_CHECKING": "false"
        }
        if extra_env:
            env.update(extra_env)
        
        self.env_patch = patch.dict(os.environ, env, clear=False)
        self.env_patch.start()
        return load_lambda_module(PERSISTER_PATH)

    def test_should_push_to_adt_returns_false_when_no_url(self):
        """_should_push_to_adt returns False when REMOTE_ADT_PUSHER_URL not set."""
        module = self._load_with_env({
            "ADT_PUSHER_TOKEN": "test-token"
            # No REMOTE_ADT_PUSHER_URL
        })
        result = module._should_push_to_adt()
        self.assertFalse(result)

    def test_should_push_to_adt_returns_false_when_no_token(self):
        """_should_push_to_adt returns False when ADT_PUSHER_TOKEN not set."""
        module = self._load_with_env({
            "REMOTE_ADT_PUSHER_URL": "https://example.com/adt-pusher"
            # No ADT_PUSHER_TOKEN
        })
        result = module._should_push_to_adt()
        self.assertFalse(result)

    def test_should_push_to_adt_returns_true_when_both_set(self):
        """_should_push_to_adt returns True when both URL and token are set."""
        module = self._load_with_env({
            "REMOTE_ADT_PUSHER_URL": "https://example.com/adt-pusher",
            "ADT_PUSHER_TOKEN": "test-token"
        })
        result = module._should_push_to_adt()
        self.assertTrue(result)

    def test_push_to_adt_skips_when_not_configured(self):
        """_push_to_adt does nothing when ADT push is not configured."""
        module = self._load_with_env()  # No ADT config
        
        with patch.object(module, 'post_to_remote') as mock_post:
            event = {"device_id": "device1", "time": "2023-01-01T00:00:00Z", "telemetry": {"temp": 25}}
            module._push_to_adt(event)
            
            mock_post.assert_not_called()

    def test_push_to_adt_calls_remote_when_configured(self):
        """_push_to_adt calls post_to_remote when configured."""
        module = self._load_with_env({
            "REMOTE_ADT_PUSHER_URL": "https://adt-pusher.azurewebsites.net/api/adt-pusher",
            "ADT_PUSHER_TOKEN": "secret-token-123"
        })
        
        with patch.object(module, 'post_to_remote', return_value={"status": "ok"}) as mock_post:
            event = {
                "device_id": "device1", 
                "device_type": "sensor",
                "time": "2023-01-01T00:00:00Z", 
                "telemetry": {"temp": 25, "humidity": 60}
            }
            module._push_to_adt(event)
            
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            self.assertEqual(call_args.kwargs["url"], "https://adt-pusher.azurewebsites.net/api/adt-pusher")
            self.assertEqual(call_args.kwargs["token"], "secret-token-123")
            self.assertEqual(call_args.kwargs["target_layer"], "L4")

    def test_push_to_adt_does_not_fail_on_error(self):
        """_push_to_adt logs error but does not raise when remote call fails."""
        module = self._load_with_env({
            "REMOTE_ADT_PUSHER_URL": "https://adt-pusher.azurewebsites.net/api/adt-pusher",
            "ADT_PUSHER_TOKEN": "secret-token-123"
        })
        
        with patch.object(module, 'post_to_remote', side_effect=Exception("Network error")) as mock_post:
            event = {"device_id": "device1", "time": "2023-01-01T00:00:00Z", "telemetry": {"temp": 25}}
            
            # Should not raise
            module._push_to_adt(event)
            
            # post_to_remote was called (and failed)
            mock_post.assert_called_once()


if __name__ == '__main__':
    unittest.main()

