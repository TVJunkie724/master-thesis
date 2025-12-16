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

