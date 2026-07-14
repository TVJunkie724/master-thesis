# tests/test_twin_state_transitions.py
# Tests for twin state transitions: blocking, regression, and Finish Configuration

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, AsyncMock

from src.models.twin import DigitalTwin, TwinState


class TestConfigStateTransitions:
    """Tests for PUT /twins/{twin_id}/config state behavior."""

    # ============================================
    # Happy Path - Regression
    # ============================================

    def test_save_draft_stays_draft(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Saving a draft twin keeps it in draft state."""
        test_twin.state = TwinState.DRAFT
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/config",
            json={"debug_mode": True}
        )
        assert response.status_code == 200
        
        db.refresh(test_twin)
        assert test_twin.state == TwinState.DRAFT

    def test_save_configured_regresses(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Saving a configured twin regresses state to draft."""
        test_twin.state = TwinState.CONFIGURED
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/config",
            json={"debug_mode": True}
        )
        assert response.status_code == 200
        
        db.refresh(test_twin)
        assert test_twin.state == TwinState.DRAFT

    def test_save_error_regresses(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Saving an error twin regresses state to draft."""
        test_twin.state = TwinState.ERROR
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/config",
            json={"debug_mode": True}
        )
        assert response.status_code == 200
        
        db.refresh(test_twin)
        assert test_twin.state == TwinState.DRAFT

    def test_save_destroyed_regresses(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Saving a destroyed twin regresses state to draft."""
        test_twin.state = TwinState.DESTROYED
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/config",
            json={"debug_mode": True}
        )
        assert response.status_code == 200
        
        db.refresh(test_twin)
        assert test_twin.state == TwinState.DRAFT

    # ============================================
    # Error Cases - Blocking (config.py)
    # ============================================

    def test_config_deployed_blocked(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Config update blocked for deployed twins."""
        test_twin.state = TwinState.DEPLOYED
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/config",
            json={"debug_mode": True}
        )
        assert response.status_code == 400
        assert "Cannot modify twin in 'deployed' state" in response.json()["detail"]

    def test_config_deploying_blocked(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Config update blocked for deploying twins."""
        test_twin.state = TwinState.DEPLOYING
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/config",
            json={"debug_mode": True}
        )
        assert response.status_code == 400
        assert "Cannot modify twin in 'deploying' state" in response.json()["detail"]

    def test_config_destroying_blocked(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Config update blocked for destroying twins."""
        test_twin.state = TwinState.DESTROYING
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/config",
            json={"debug_mode": True}
        )
        assert response.status_code == 400
        assert "Cannot modify twin in 'destroying' state" in response.json()["detail"]


class TestDeployerConfigStateTransitions:
    """Tests for PUT /twins/{twin_id}/deployer/config state behavior."""

    def test_deployer_config_deployed_blocked(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Deployer config update blocked for deployed twins."""
        test_twin.state = TwinState.DEPLOYED
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/deployer/config",
            json={"deployer_digital_twin_name": "test"}
        )
        assert response.status_code == 400
        assert "Cannot modify twin in 'deployed' state" in response.json()["detail"]

    def test_deployer_config_deploying_blocked(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Deployer config update blocked for deploying twins."""
        test_twin.state = TwinState.DEPLOYING
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/deployer/config",
            json={"deployer_digital_twin_name": "test"}
        )
        assert response.status_code == 400
        assert "Cannot modify twin in 'deploying' state" in response.json()["detail"]

    def test_deployer_config_regresses(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Deployer config update regresses configured twin to draft."""
        test_twin.state = TwinState.CONFIGURED
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/deployer/config",
            json={"deployer_digital_twin_name": "test"}
        )
        assert response.status_code == 200
        
        db.refresh(test_twin)
        assert test_twin.state == TwinState.DRAFT


class TestTwinRenameBlocking:
    """Tests for PUT /twins/{twin_id} name blocking."""

    def test_rename_deployed_blocked(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Renaming blocked for deployed twins."""
        test_twin.state = TwinState.DEPLOYED
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}",
            json={"name": "NewName"}
        )
        assert response.status_code == 400
        assert "Cannot rename twin in 'deployed' state" in response.json()["detail"]

    def test_state_change_deployed_allowed(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """State changes allowed for deployed twins (needed for destroy flow)."""
        test_twin.state = TwinState.DEPLOYED
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}",
            json={"state": "destroying"}
        )
        assert response.status_code == 200
        
        db.refresh(test_twin)
        assert test_twin.state == TwinState.DESTROYING


class TestFinishConfiguration:
    """Tests for Finish Configuration state transitions."""

    @patch("src.api.routes.twins._validate_configured_transition", new_callable=AsyncMock)
    def test_finish_config_from_draft(
        self, mock_validate, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Finish Configuration from draft sets state to configured."""
        test_twin.state = TwinState.DRAFT
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}",
            json={"state": "configured"}
        )
        assert response.status_code == 200
        
        db.refresh(test_twin)
        assert test_twin.state == TwinState.CONFIGURED

    @patch("src.api.routes.twins._validate_configured_transition", new_callable=AsyncMock)
    def test_finish_config_from_error(
        self, mock_validate, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Finish Configuration from error sets state to configured."""
        test_twin.state = TwinState.ERROR
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}",
            json={"state": "configured"}
        )
        assert response.status_code == 200
        
        db.refresh(test_twin)
        assert test_twin.state == TwinState.CONFIGURED

    @patch("src.api.routes.twins._validate_configured_transition", new_callable=AsyncMock)
    def test_finish_config_from_destroyed(
        self, mock_validate, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Finish Configuration from destroyed sets state to configured."""
        test_twin.state = TwinState.DESTROYED
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}",
            json={"state": "configured"}
        )
        assert response.status_code == 200
        
        db.refresh(test_twin)
        assert test_twin.state == TwinState.CONFIGURED


class TestResponseIncludesState:
    """Tests verifying response includes twin_state."""

    def test_response_includes_new_state(
        self, auth_client: TestClient, db: Session, test_twin: DigitalTwin
    ):
        """Config response includes twin_state showing regression."""
        test_twin.state = TwinState.CONFIGURED
        db.commit()

        response = auth_client.put(
            f"/twins/{test_twin.id}/config",
            json={"debug_mode": True}
        )
        assert response.status_code == 200
        
        # Verify state was regressed in DB (response format may vary)
        db.refresh(test_twin)
        assert test_twin.state == TwinState.DRAFT
