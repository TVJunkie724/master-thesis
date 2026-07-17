
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
            "DIGITAL_TWIN_INFO": (
                '{"name": "test-twin", "config_providers": '
                '{"layer_4_provider": "aws"}}'
            ),
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
            "DIGITAL_TWIN_INFO": (
                '{"name": "test-twin", "config_providers": '
                '{"layer_4_provider": "aws"}}'
            ),
            "DYNAMODB_TABLE_NAME": "test-dynamodb-table",
            "EVENT_CHECKER_LAMBDA_NAME": "test-event-checker",
            "USE_EVENT_CHECKING": "false"
        }
        if extra_env:
            env.update(extra_env)
        
        self.env_patch = patch.dict(os.environ, env, clear=False)
        self.env_patch.start()
        return load_lambda_module(PERSISTER_PATH)

    def test_adt_delivery_settings_skip_non_azure_l4(self):
        module = self._load_with_env({
            "REMOTE_ADT_PUSHER_URL": "https://example.com/adt-pusher",
            "ADT_PUSHER_TOKEN": "stale-token",
        })
        self.assertIsNone(module._get_adt_delivery_settings())

    def test_azure_l4_requires_url(self):
        module = self._load_with_env({
            "DIGITAL_TWIN_INFO": (
                '{"name": "test-twin", "config_providers": '
                '{"layer_4_provider": "azure"}}'
            ),
            "ADT_PUSHER_TOKEN": "test-token",
            "REMOTE_ADT_PUSHER_URL": "",
        })
        with self.assertRaisesRegex(module.ConfigurationError, "REMOTE_ADT_PUSHER_URL"):
            module._get_adt_delivery_settings()

    def test_azure_l4_requires_token(self):
        module = self._load_with_env({
            "DIGITAL_TWIN_INFO": (
                '{"name": "test-twin", "config_providers": '
                '{"layer_4_provider": "azure"}}'
            ),
            "REMOTE_ADT_PUSHER_URL": "https://example.com/adt-pusher",
            "ADT_PUSHER_TOKEN": "",
        })
        with self.assertRaisesRegex(module.ConfigurationError, "ADT_PUSHER_TOKEN"):
            module._get_adt_delivery_settings()

    def test_push_to_adt_calls_remote_when_configured(self):
        """_push_to_adt calls post_to_remote when configured."""
        module = self._load_with_env({
            "DIGITAL_TWIN_INFO": (
                '{"name": "test-twin", "config_providers": '
                '{"layer_4_provider": "azure"}}'
            ),
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
            self.assertEqual(
                call_args.kwargs["payload"],
                {
                    "device_id": "device1",
                    "device_type": "sensor",
                    "telemetry": {"temp": 25, "humidity": 60},
                    "timestamp": "2023-01-01T00:00:00Z",
                },
            )

    def test_push_to_adt_propagates_stable_delivery_error(self):
        module = self._load_with_env({
            "DIGITAL_TWIN_INFO": (
                '{"name": "test-twin", "config_providers": '
                '{"layer_4_provider": "azure"}}'
            ),
            "REMOTE_ADT_PUSHER_URL": "https://adt-pusher.azurewebsites.net/api/adt-pusher",
            "ADT_PUSHER_TOKEN": "secret-token-123"
        })
        
        with patch.object(module, 'post_to_remote', side_effect=Exception("Network error")) as mock_post:
            event = {"device_id": "device1", "time": "2023-01-01T00:00:00Z", "telemetry": {"temp": 25}}

            with self.assertRaisesRegex(
                module.AdtDeliveryError,
                "Azure Digital Twins update failed",
            ):
                module._push_to_adt(event)

            mock_post.assert_called_once()


if __name__ == '__main__':
    unittest.main()
