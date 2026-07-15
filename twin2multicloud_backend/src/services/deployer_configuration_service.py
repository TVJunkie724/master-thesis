"""Deployer configuration read/write use cases."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.deployer_config import DeployerConfiguration
from src.models.twin import TwinState
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployer_config import (
    DeployerConfigReadModelResponse,
    DeployerConfigResponse,
    DeployerConfigUpdate,
)
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.services.wizard_configuration_service import WizardConfigurationService


BLOCKED_DEPLOYER_CONFIG_STATES = {
    TwinState.DEPLOYED,
    TwinState.DEPLOYING,
    TwinState.DESTROYING,
}
REGRESS_DEPLOYER_CONFIG_STATES = {
    TwinState.CONFIGURED,
    TwinState.ERROR,
    TwinState.DESTROYED,
}
class DeployerConfigurationService:
    """Owns Step-3 deployer configuration persistence and response shaping."""

    def __init__(self, db: Session, twin_repository: TwinRepository):
        self.db = db
        self.twin_repository = twin_repository

    def get_config(self, twin_id: str, user_id: str) -> DeployerConfigResponse:
        """Return an existing deployer config or create a default one."""
        twin = self._require_twin(twin_id, user_id)
        config = self._ensure_config(twin_id, twin)
        return DeployerConfigResponse.from_db(config, twin_state=twin.state.value)

    def get_read_model(
        self,
        twin_id: str,
        user_id: str,
    ) -> DeployerConfigReadModelResponse:
        """Return the typed Flutter read model from the canonical config record."""
        twin = self._require_twin(twin_id, user_id)
        config = self._ensure_config(twin_id, twin)
        return DeployerConfigReadModelResponse.from_db(
            config,
            twin_state=twin.state.value,
        )

    def update_config(
        self,
        twin_id: str,
        user_id: str,
        update: DeployerConfigUpdate,
    ) -> dict[str, Any]:
        """Persist deployer config changes and regress mutable configured states."""
        twin = self._require_twin(twin_id, user_id)
        try:
            config = WizardConfigurationService(self.db).apply_deployer_config_update(twin, update)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise EntityNotFoundError(str(exc.detail)) from exc
            raise ValidationError(str(exc.detail)) from exc
        self.db.commit()
        self.db.refresh(config)
        self.db.refresh(twin)

        response = DeployerConfigResponse.from_db(config)
        return {**response.model_dump(), "twin_state": twin.state.value}

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    def _ensure_config(self, twin_id: str, twin, *, commit: bool = True) -> DeployerConfiguration:
        if twin.deployer_config:
            return twin.deployer_config

        config = DeployerConfiguration(twin_id=twin_id)
        self.db.add(config)
        if commit:
            self.db.commit()
            self.db.refresh(config)
        return config
