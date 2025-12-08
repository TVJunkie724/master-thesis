import pytest
import boto3
from unittest.mock import MagicMock, patch
import aws.event_action_deployer_aws as event_action_aws
import aws.globals_aws as globals_aws
import globals

@patch("time.sleep")
def test_redeploy_event_actions(mock_sleep, mock_aws_context):
    """Verify deployment and destruction of event action Lambdas (Redeploy logic)."""
    
    # Mock configuration
    mock_event_config = [
        {
            "action": {
                "type": "lambda",
                "functionName": "test-action-func",
                "autoDeploy": True
            }
        }
    ]
    
    # Mock util.compile_lambda_function to avoid needing real files
    with patch.object(globals, "config_events", mock_event_config), \
         patch("util.compile_lambda_function", return_value=b"mock-zip"):
         
        # 1. Deploy
        globals_aws.aws_iam_client.attach_role_policy = MagicMock()
        event_action_aws.deploy_lambda_actions()
        
        # Verify Creation
        client_iam = boto3.client("iam")
        assert client_iam.get_role(RoleName="test-action-func")
        
        client_lambda = boto3.client("lambda")
        assert client_lambda.get_function(FunctionName="test-action-func")
        
        # 2. Destroy
        event_action_aws.destroy_lambda_actions()
        
        # Verify Destruction
        with pytest.raises(client_iam.exceptions.NoSuchEntityException):
            client_iam.get_role(RoleName="test-action-func")
            
        with pytest.raises(client_lambda.exceptions.ResourceNotFoundException):
            client_lambda.get_function(FunctionName="test-action-func")


@patch("time.sleep")
def test_event_actions_uses_new_path(mock_sleep, mock_aws_context):
    """Verify event actions use the new path: lambda_functions/event_actions."""
    import constants as CONSTANTS
    
    # Verify constant has been updated
    assert "lambda_functions" in CONSTANTS.EVENT_ACTIONS_DIR_NAME
    assert CONSTANTS.EVENT_ACTIONS_DIR_NAME == "lambda_functions/event_actions"


@patch("time.sleep")
def test_compile_uses_correct_path(mock_sleep, mock_aws_context):
    """Verify event_action_deployer references the correct constant."""
    import constants as CONSTANTS
    import inspect
    import aws.event_action_deployer_aws as deployer
    
    # Verify the deployer source uses EVENT_ACTIONS_DIR_NAME constant
    source = inspect.getsource(deployer)
    assert "EVENT_ACTIONS_DIR_NAME" in source
    
    # Verify the constant value is correct
    assert CONSTANTS.EVENT_ACTIONS_DIR_NAME == "lambda_functions/event_actions"

