"""Twin configuration read/write use cases."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.twin import TwinState
from src.models.twin_config import TwinConfiguration
from src.repositories.twin_repository import TwinRepository
from src.schemas.twin_config import TwinConfigResponse, TwinConfigUpdate
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.services.wizard_configuration_service import WizardConfigurationService


BLOCKED_CONFIG_STATES = {TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING}
REGRESS_CONFIG_STATES = {TwinState.CONFIGURED, TwinState.ERROR, TwinState.DESTROYED}


class TwinConfigurationService:
    """Owns Step-1 configuration persistence and response shaping."""

    def __init__(self, db: Session, twin_repository: TwinRepository):
        self.db = db
        self.twin_repository = twin_repository

    def get_config(self, twin_id: str, user_id: str) -> TwinConfigResponse:
        """Return an existing config or create a default one."""
        twin = self._require_twin(twin_id, user_id)
        config = self._ensure_config(twin_id, twin)
        return TwinConfigResponse.from_db(config, twin.optimizer_config, twin_state=twin.state.value)

    def update_config(self, twin_id: str, user_id: str, update: TwinConfigUpdate) -> dict[str, Any]:
        """Persist config changes, encrypting credentials and regressing state when required."""
        twin = self._require_twin(twin_id, user_id)
        try:
            config = WizardConfigurationService(self.db).apply_twin_config_update(
                twin,
                update,
                user_id,
            )
        except HTTPException as exc:
            if exc.status_code == 404:
                raise EntityNotFoundError(str(exc.detail)) from exc
            raise ValidationError(str(exc.detail)) from exc
        self.db.commit()
        self.db.refresh(config)
        self.db.refresh(twin)

        response = TwinConfigResponse.from_db(config, twin.optimizer_config)
        return {**response.model_dump(), "twin_state": twin.state.value}

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    def _ensure_config(self, twin_id: str, twin, *, commit: bool = True) -> TwinConfiguration:
        if twin.configuration:
            return twin.configuration

        config = TwinConfiguration(twin_id=twin_id)
        self.db.add(config)
        if commit:
            self.db.commit()
            self.db.refresh(config)
        return config
