import pytest
import boto3
from unittest.mock import MagicMock, patch, ANY
import src.providers.aws.layers.layer_2_compute as event_action_aws

@patch("time.sleep")
def test_redeploy_event_actions(mock_sleep):
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
    
    # Setup Mock Provider
    mock_provider = MagicMock()
    mock_iam = MagicMock()
    mock_lambda = MagicMock()
    mock_provider.clients = {
        "iam": mock_iam,
        "lambda": mock_lambda
    }
    
    # Mock util.compile_lambda_function to avoid needing real files
    with patch("src.util.compile_lambda_function", return_value=b"mock-zip"):
        # 1. Deploy
        mock_iam.get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test-action-func"}}
        
        mock_config = MagicMock()
        mock_config.events = mock_event_config
        mock_config.digital_twin_name = "test-twin"
        mock_config.hot_storage_size_in_days = 7
        mock_config.cold_storage_size_in_days = 30
        mock_config.mode = "dev"
        mock_config.iot_devices = []
        mock_config.get_digital_twin_info.return_value = {}

        event_action_aws.deploy_lambda_actions(
            provider=mock_provider,
            config=mock_config,
            project_path="/mock/path"
        )
        
        # Verify Creation
        mock_iam.create_role.assert_called_with(
            RoleName="test-action-func",
            AssumeRolePolicyDocument=ANY
        )
        import json
        expected_info = {
            "config": {
                "digital_twin_name": "test-twin",
                "hot_storage_size_in_days": 7,
                "cold_storage_size_in_days": 30,
                "mode": "dev",
            },
            "config_iot_devices": [],
            "config_events": mock_event_config
        }

        mock_lambda.create_function.assert_called_with(
            FunctionName="test-action-func",
            Role="arn:aws:iam::123:role/test-action-func",
            Runtime="python3.13",
            Handler="lambda_function.lambda_handler", 
            Code={"ZipFile": b"mock-zip"},
            Description="Event action Lambda function",
            Timeout=3,
            MemorySize=128,
            Publish=True,
            Environment={'Variables': {'DIGITAL_TWIN_INFO': json.dumps(expected_info)}}
        )

        
        # 2. Destroy
        # Mock finding policies to detach
        mock_iam.list_attached_role_policies.return_value = {"AttachedPolicies": []}
        mock_iam.list_role_policies.return_value = {"PolicyNames": []}
        mock_iam.list_instance_profiles_for_role.return_value = {"InstanceProfiles": []}
        
        event_action_aws.destroy_lambda_actions(
            provider=mock_provider,
            config=mock_config
        )
        
        # Verify Destruction
        mock_iam.delete_role.assert_called_with(RoleName="test-action-func")
        mock_lambda.delete_function.assert_called_with(FunctionName="test-action-func")


@patch("time.sleep")
def test_event_actions_uses_new_path(mock_sleep):
    """Verify event actions use the new path: lambda_functions/event_actions."""
    import constants as CONSTANTS
    
    # Verify constant has been updated
    assert "lambda_functions" in CONSTANTS.EVENT_ACTIONS_DIR_NAME
    assert CONSTANTS.EVENT_ACTIONS_DIR_NAME == "lambda_functions/event_actions"


@patch("time.sleep")
def test_compile_uses_correct_path(mock_sleep):
    """Verify event_action_deployer references the correct constant."""
    import constants as CONSTANTS
    import inspect
    import src.providers.aws.layers.layer_2_compute as deployer
    
    # Verify the deployer source uses EVENT_ACTIONS_DIR_NAME constant
    source = inspect.getsource(deployer)
    assert "EVENT_ACTIONS_DIR_NAME" in source
    
    # Verify the constant value is correct
    assert CONSTANTS.EVENT_ACTIONS_DIR_NAME == "lambda_functions/event_actions"

