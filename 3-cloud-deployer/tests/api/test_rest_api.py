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
    assert response.json() == {"status": "API is running"}

@patch("deployers.core_deployer.deploy_l1")
def test_deploy_l1(mock_deploy_l1):
    response = client.post("/deploy_l1?provider=aws")
    assert response.status_code == 200
    assert "completed successfully" in response.json()["message"]
    mock_deploy_l1.assert_called_once_with("aws")

@patch("deployers.core_deployer.destroy_l1")
def test_destroy_l1(mock_destroy_l1):
    response = client.post("/destroy_l1?provider=aws")
    assert response.status_code == 200
    mock_destroy_l1.assert_called_once_with("aws")

@patch("aws.lambda_manager.invoke_function")
def test_lambda_invoke(mock_invoke):
    payload = {"local_function_name": "test-func", "payload": {}, "sync": True}
    response = client.post("/lambda_invoke", json=payload)
    assert response.status_code == 200
    mock_invoke.assert_called_once_with("test-func", {}, True)

client = TestClient(rest_api.app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "API is running"}

@patch("deployers.core_deployer.deploy_l1")
def test_deploy_l1(mock_deploy_l1):
    response = client.post("/deploy_l1?provider=aws")
    assert response.status_code == 200
    assert "completed successfully" in response.json()["message"]
    mock_deploy_l1.assert_called_once_with("aws")

@patch("deployers.core_deployer.destroy_l1")
def test_destroy_l1(mock_destroy_l1):
    response = client.post("/destroy_l1?provider=aws")
    assert response.status_code == 200
    mock_destroy_l1.assert_called_once_with("aws")

@patch("aws.lambda_manager.invoke_function")
def test_lambda_invoke(mock_invoke):
    payload = {"local_function_name": "test-func", "payload": {}, "sync": True}
    response = client.post("/lambda_invoke", json=payload)
    assert response.status_code == 200
    mock_invoke.assert_called_once_with("test-func", {}, True)

@patch("rest_api.event_action_deployer")
@patch("rest_api.core_deployer")
def test_recreate_updated_events(mock_core, mock_actions):
    """Verify redeploy events endpoint deployment sequence."""
    response = client.post("/recreate_updated_events?provider=aws")
    assert response.status_code == 200
    assert response.json() == {"message": "Events recreated successfully"}
    
    mock_actions.redeploy.assert_called_once_with("aws")
    mock_core.redeploy_l2_event_checker.assert_called_once_with("aws")
