"""
Tests for IoT Simulator download endpoint.

Tests GET /twins/{twin_id}/simulator/download which proxies to Deployer API.
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from src.models.twin import DigitalTwin, TwinState
from src.models.optimizer_config import OptimizerConfiguration
from src.models.deployer_config import DeployerConfiguration
from tests.conftest import create_test_twin


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def deployed_twin_with_optimizer(authenticated_client, db_session):
    """Create a deployed twin with optimizer config containing L1."""
    client, headers = authenticated_client
    
    # Create twin
    twin_id = create_test_twin(client, headers, "Simulator Test Twin")
    
    # Get the twin and set to deployed
    twin = db_session.query(DigitalTwin).filter_by(id=twin_id).first()
    twin.state = TwinState.DEPLOYED
    
    # Add deployer config
    deployer_config = DeployerConfiguration(
        twin_id=twin_id,
        deployer_digital_twin_name="sim-test-project"
    )
    db_session.add(deployer_config)
    
    # Add optimizer config with cheapest_l1 (individual columns, not dict)
    opt_config = OptimizerConfiguration(
        twin_id=twin_id,
        cheapest_l1="aws",
        cheapest_l2="azure",
        cheapest_l3_hot="aws",
        cheapest_l3_cool="gcp"
    )
    db_session.add(opt_config)
    db_session.commit()
    
    return client, headers, twin_id


# ============================================================
# Happy Path Tests (3)
# ============================================================

@patch("httpx.AsyncClient.get")
def test_download_simulator_aws_success(mock_get, deployed_twin_with_optimizer):
    """Successfully download AWS simulator package."""
    client, headers, twin_id = deployed_twin_with_optimizer
    
    # Mock Deployer response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"PK\x03\x04mock-zip-content"
    mock_get.return_value = mock_response
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "aws" in response.headers["content-disposition"]
    assert "sim-test-project" in response.headers["content-disposition"]


@patch("httpx.AsyncClient.get")
def test_download_simulator_azure_success(mock_get, authenticated_client, db_session):
    """Successfully download Azure simulator package."""
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers, "Azure Sim Twin")
    
    twin = db_session.query(DigitalTwin).filter_by(id=twin_id).first()
    twin.state = TwinState.DEPLOYED
    
    deployer_config = DeployerConfiguration(twin_id=twin_id, deployer_digital_twin_name="azure-project")
    opt_config = OptimizerConfiguration(twin_id=twin_id, cheapest_l1="azure")
    db_session.add_all([deployer_config, opt_config])
    db_session.commit()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"PK\x03\x04azure-zip"
    mock_get.return_value = mock_response
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 200
    assert "azure" in response.headers["content-disposition"]


@patch("httpx.AsyncClient.get")
def test_download_simulator_gcp_success(mock_get, authenticated_client, db_session):
    """Successfully download GCP simulator package."""
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers, "GCP Sim Twin")
    
    twin = db_session.query(DigitalTwin).filter_by(id=twin_id).first()
    twin.state = TwinState.DEPLOYED
    
    deployer_config = DeployerConfiguration(twin_id=twin_id, deployer_digital_twin_name="gcp-project")
    opt_config = OptimizerConfiguration(twin_id=twin_id, cheapest_l1="gcp")
    db_session.add_all([deployer_config, opt_config])
    db_session.commit()
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"PK\x03\x04gcp-zip"
    mock_get.return_value = mock_response
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 200
    assert "gcp" in response.headers["content-disposition"]


# ============================================================
# Error Tests (5)
# ============================================================

def test_download_simulator_twin_not_found(authenticated_client):
    """404 when twin doesn't exist."""
    client, headers = authenticated_client
    response = client.get("/twins/nonexistent-id/simulator/download", headers=headers)
    assert response.status_code == 404


def test_download_simulator_not_deployed(authenticated_client, db_session):
    """400 when twin is not in deployed state."""
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers, "Not Deployed Twin")
    
    # Twin is in DRAFT state by default
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 400
    assert "deployed" in response.json()["detail"].lower()


def test_download_simulator_no_optimizer(authenticated_client, db_session):
    """404 when optimizer config is missing."""
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers, "No Optimizer Twin")
    
    twin = db_session.query(DigitalTwin).filter_by(id=twin_id).first()
    twin.state = TwinState.DEPLOYED
    db_session.commit()
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 404
    assert "optimization" in response.json()["detail"].lower()


def test_download_simulator_no_l1(authenticated_client, db_session):
    """404 when L1 provider is not in cheapest_path."""
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers, "No L1 Twin")
    
    twin = db_session.query(DigitalTwin).filter_by(id=twin_id).first()
    twin.state = TwinState.DEPLOYED
    
    # Empty cheapest_l1 (no L1 provider set)
    opt_config = OptimizerConfiguration(twin_id=twin_id, cheapest_l1=None)
    db_session.add(opt_config)
    db_session.commit()
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 404
    # Error message says optimization not configured (no L1 in result)
    assert "optimization" in response.json()["detail"].lower()


@patch("httpx.AsyncClient.get")
def test_download_simulator_deployer_404(mock_get, deployed_twin_with_optimizer):
    """404 when Deployer returns 404."""
    client, headers, twin_id = deployed_twin_with_optimizer
    
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Project not found"
    mock_get.return_value = mock_response
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 404
    assert "simulator not available" in response.json()["detail"].lower()


# ============================================================
# Edge Case Tests (4)
# ============================================================

@patch("httpx.AsyncClient.get")
def test_download_simulator_deployer_timeout(mock_get, deployed_twin_with_optimizer):
    """502 when Deployer times out."""
    client, headers, twin_id = deployed_twin_with_optimizer
    
    mock_get.side_effect = httpx.RequestError("Connection timeout")
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 502
    assert "failed to connect" in response.json()["detail"].lower()


@patch("httpx.AsyncClient.get")
def test_download_simulator_deployer_500(mock_get, deployed_twin_with_optimizer):
    """500 when Deployer returns 500."""
    client, headers, twin_id = deployed_twin_with_optimizer
    
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal server error"
    mock_get.return_value = mock_response
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 500


def test_download_simulator_wrong_user(authenticated_client, db_session):
    """404 when accessing another user's twin."""
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers, "User A Twin")
    
    twin = db_session.query(DigitalTwin).filter_by(id=twin_id).first()
    twin.state = TwinState.DEPLOYED
    twin.user_id = "different-user-id"  # Change owner
    db_session.commit()
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 404


def test_download_simulator_inactive_twin(authenticated_client, db_session):
    """404 when twin is inactive (soft deleted)."""
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers, "Inactive Twin")
    
    twin = db_session.query(DigitalTwin).filter_by(id=twin_id).first()
    twin.state = TwinState.DEPLOYED
    twin.is_active = False
    db_session.commit()
    
    response = client.get(f"/twins/{twin_id}/simulator/download", headers=headers)
    
    assert response.status_code == 404
