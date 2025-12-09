import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import sys
import os

# Ensure rest_api can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import rest_api

client = TestClient(rest_api.app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "API is running", "active_project": "template"}

@patch("src.api.deployment.create_context")
@patch("src.api.deployment.core_deployer.deploy_l1")
def test_deploy_l1(mock_deploy_l1, mock_create_context):
    mock_context = mock_create_context.return_value
    response = client.post("/deploy_l1?provider=aws")
    assert response.status_code == 200
    assert "completed successfully" in response.json()["message"]
    mock_deploy_l1.assert_called_once_with(mock_context, "aws")

@patch("src.api.deployment.create_context")
@patch("src.api.deployment.core_deployer.destroy_l1")
def test_destroy_l1(mock_destroy_l1, mock_create_context):
    mock_context = mock_create_context.return_value
    response = client.post("/destroy_l1?provider=aws")
    assert response.status_code == 200
    mock_destroy_l1.assert_called_once_with(mock_context, "aws")

@patch("src.api.aws_gateway.create_context")
@patch("src.api.aws_gateway.lambda_manager.invoke_function")
def test_lambda_invoke(mock_invoke, mock_create_context):
    mock_context = mock_create_context.return_value
    mock_provider = mock_context.providers.__getitem__.return_value
    
    payload = {"local_function_name": "test-func", "payload": {}, "sync": True}
    response = client.post("/lambda_invoke", json=payload)
    assert response.status_code == 200
    from unittest.mock import ANY
    mock_invoke.assert_called_once_with("test-func", {}, True, provider=ANY)



@patch("src.api.deployment.create_context")
@patch("src.api.deployment.event_action_deployer_aws.deploy_lambda_actions")
@patch("src.api.deployment.event_action_deployer_aws.destroy_lambda_actions")
@patch("src.api.deployment.core_deployer.redeploy_event_checker")
def test_recreate_updated_events(mock_redeploy_checker, mock_destroy, mock_deploy, mock_create_context):
    """Verify redeploy events endpoint deployment sequence."""
    mock_context = mock_create_context.return_value
    response = client.post("/recreate_updated_events?provider=aws")
    assert response.status_code == 200
    assert response.json() == {"message": "Events recreated successfully"}
    
    # Verify aws modules called directly
    mock_destroy.assert_called_once()
    mock_deploy.assert_called_once()
    mock_redeploy_checker.assert_called_once_with(mock_context, "aws")

@patch("src.validator.verify_project_structure")
@patch("src.api.deployment.create_context")
@patch("src.api.deployment.core_deployer.deploy_all")
@patch("src.api.deployment.iot_deployer.deploy")
@patch("src.api.deployment.hierarchy_deployer_aws.create_twinmaker_hierarchy")
@patch("src.api.deployment.event_action_deployer_aws.deploy_lambda_actions")
@patch("src.api.deployment.init_values_deployer_aws.post_init_values_to_iot_core")
def test_deploy_all_verification(mock_init, mock_event, mock_hier, mock_iot, mock_core, mock_create_context, mock_verify):
    """Verify deploy_all calls verify_project_structure."""
    mock_context = mock_create_context.return_value
    response = client.post("/deploy?provider=aws&project_name=template")
    assert response.status_code == 200
    mock_verify.assert_called_once_with("template")
    mock_core.assert_called_once_with(mock_context, "aws")


@patch("src.validator.validate_state_machine_content")
def test_upload_state_machine_success(mock_validate):
    """Test successful state machine upload."""
    files = {'file': ('aws_step_function.json', '{"StartAt": "x", "States": {}}', 'application/json')}
    response = client.put("/projects/template/state_machines/aws", files=files)
    assert response.status_code == 200
    assert "uploaded and verified" in response.json()["message"]
    mock_validate.assert_called_once()

@patch("src.validator.validate_state_machine_content")
def test_upload_state_machine_invalid_provider(mock_validate):
    """Test upload with invalid provider."""
    files = {'file': ('aws_step_function.json', '{}', 'application/json')}
    response = client.put("/projects/template/state_machines/unknown", files=files)
    assert response.status_code == 422
    # Just verify it's a validation error structure (list of errors)
    assert isinstance(response.json()["detail"], list)

@patch("src.validator.validate_state_machine_content")
def test_upload_state_machine_validation_fail(mock_validate):
    """Test upload validation failure."""
    mock_validate.side_effect = ValueError("Missing content")
    files = {'file': ('aws_step_function.json', '{}', 'application/json')}
    response = client.put("/projects/template/state_machines/aws", files=files)
    assert response.status_code == 400
    assert "Missing content" in response.json()["detail"]

