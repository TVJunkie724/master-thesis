
import os
import sys
import json
import unittest
from unittest.mock import MagicMock, patch
import importlib.util

def load_lambda_module(path):
    spec = importlib.util.spec_from_file_location("lambda_function", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lambda_function"] = module
    spec.loader.exec_module(module)
    return module

EVENT_CHECKER_PATH = "src/aws/lambda_functions/event-checker/lambda_function.py"

class TestEventCheckerLambda(unittest.TestCase):
    def setUp(self):
        self.mock_lambda = MagicMock()
        self.mock_sf = MagicMock()
        
        self.boto3_patch = patch('boto3.client')
        self.mock_boto3_client = self.boto3_patch.start()
        
        def side_effect(service, **kwargs):
            if service == 'lambda':
                return self.mock_lambda
            if service == 'stepfunctions':
                return self.mock_sf
            return MagicMock()
            
        # Config events for tests
        self.step_function_event = {
            "condition": "DOUBLE(5) < DOUBLE(10)", # Always true
            "action": {
                "type": "step_function",
                "functionName": "irrelevant"
            }
        }
        
        self.feedback_event = {
            "condition": "DOUBLE(5) < DOUBLE(10)",
            "action": {
                "type": "lambda",
                "functionName": "irrelevant",
                "feedback": {
                    "iotDeviceId": "d1",
                    "payload": "cool down"
                }
            }
        }

        # Patch Env variables BEFORE loading module so top-level reads succeed
        # We start with empty config_events and override in specific tests
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({"name": "test-twin", "config_events": [], "config": {"digital_twin_name": "test-twin"}}),
            "TWINMAKER_WORKSPACE_NAME": "test-workspace",
            "LAMBDA_CHAIN_STEP_FUNCTION_ARN": "arn:aws:states:us-east-1:123:stateMachine:test-sf",
            "EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN": "arn:aws:lambda:us-east-1:123:function:test-feedback",
            "USE_STEP_FUNCTIONS": "true",
            "USE_FEEDBACK": "true"
        })
        self.env_patch.start()
        
        self.lambda_module = load_lambda_module(EVENT_CHECKER_PATH)
        
        # Overwrite clients directly on the loaded module to ensure we assert on the right mock
        self.lambda_module.lambda_client = self.mock_lambda
        self.lambda_module.stepfunctions_client = self.mock_sf

    def tearDown(self):
        self.boto3_patch.stop()
        self.env_patch.stop()

    def test_trigger_step_function_enabled(self):
        """Test Step Function trigger when enabled."""
        # Inject config with step function event
        self.lambda_module.DIGITAL_TWIN_INFO["config_events"] = [self.step_function_event]
        self.lambda_module.USE_STEP_FUNCTIONS = True

        event = {"iotDeviceId": "d1", "payload": {"temp": 90}}
        self.lambda_module.lambda_handler(event, None)
             
        self.mock_sf.start_execution.assert_called_with(
            stateMachineArn="arn:aws:states:us-east-1:123:stateMachine:test-sf",
            input=unittest.mock.ANY
        )

    def test_trigger_step_function_disabled(self):
        """Test Step Function trigger skipped when disabled."""
        self.lambda_module.DIGITAL_TWIN_INFO["config_events"] = [self.step_function_event]
        self.lambda_module.USE_STEP_FUNCTIONS = False # Simulate env var being false
        
        event = {"iotDeviceId": "d1", "payload": {"temp": 90}}
        self.lambda_module.lambda_handler(event, None)
             
        self.mock_sf.start_execution.assert_not_called()

    def test_trigger_feedback_enabled(self):
        """Test Feedback trigger when enabled."""
        self.lambda_module.DIGITAL_TWIN_INFO["config_events"] = [self.feedback_event]
        self.lambda_module.USE_FEEDBACK = True
        
        event = {"iotDeviceId": "d1", "payload": {"temp": 90}}
        self.lambda_module.lambda_handler(event, None)
             
        self.mock_lambda.invoke.assert_called_with(
            FunctionName="arn:aws:lambda:us-east-1:123:function:test-feedback",
            InvocationType='Event',
            Payload=unittest.mock.ANY
        )

    def test_trigger_feedback_disabled(self):
        """Test Feedback trigger skipped when disabled."""
        self.lambda_module.DIGITAL_TWIN_INFO["config_events"] = [self.feedback_event]
        self.lambda_module.USE_FEEDBACK = False
        
        event = {"iotDeviceId": "d1", "payload": {"temp": 90}}
        self.lambda_module.lambda_handler(event, None)
             
        # Verify that invoke was NOT called with the feedback function ARN
        feedback_arn = "arn:aws:lambda:us-east-1:123:function:test-feedback"
        
        # Get all calls
        calls = self.mock_lambda.invoke.call_args_list
        
        # Check if any call matches the feedback ARN
        feedback_called = any(call.kwargs.get("FunctionName") == feedback_arn for call in calls)
        
        self.assertFalse(feedback_called, "Feedback Lambda incorrectly invoked")

if __name__ == '__main__':
    unittest.main()
