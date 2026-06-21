"""Deployer configuration read/write use cases."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from src.models.deployer_config import DeployerConfiguration
from src.models.twin import TwinState
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployer_config import DeployerConfigResponse, DeployerConfigUpdate
from src.services.service_errors import EntityNotFoundError, ValidationError


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
MAX_DEPLOYER_TWIN_NAME_LENGTH = 15


class DeployerConfigurationService:
    """Owns Step-3 deployer configuration persistence and response shaping."""

    def __init__(self, db: Session, twin_repository: TwinRepository):
        self.db = db
        self.twin_repository = twin_repository

    def get_config(self, twin_id: str, user_id: str) -> DeployerConfigResponse:
        """Return an existing deployer config or create a default one."""
        twin = self._require_twin(twin_id, user_id)
        config = self._ensure_config(twin_id, twin)
        return DeployerConfigResponse.from_db(config)

    def update_config(
        self,
        twin_id: str,
        user_id: str,
        update: DeployerConfigUpdate,
    ) -> dict[str, Any]:
        """Persist deployer config changes and regress mutable configured states."""
        twin = self._require_twin(twin_id, user_id)
        if twin.state in BLOCKED_DEPLOYER_CONFIG_STATES:
            raise ValidationError(f"Cannot modify twin in '{twin.state.value}' state")

        should_regress = twin.state in REGRESS_DEPLOYER_CONFIG_STATES
        config = self._ensure_config(twin_id, twin, commit=False)
        self._apply_update(config, update)

        if should_regress:
            twin.state = TwinState.DRAFT

        self.db.commit()
        self.db.refresh(config)
        self.db.refresh(twin)

        response = DeployerConfigResponse.from_db(config)
        return {**response.model_dump(), "twin_state": twin.state.value}

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self.twin_repository.get_for_user(twin_id, user_id)
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

    def _apply_update(self, config: DeployerConfiguration, update: DeployerConfigUpdate) -> None:
        if update.deployer_digital_twin_name is not None:
            if len(update.deployer_digital_twin_name) > MAX_DEPLOYER_TWIN_NAME_LENGTH:
                raise ValidationError("Digital twin name exceeds 15 characters")
            config.deployer_digital_twin_name = update.deployer_digital_twin_name

        string_fields = (
            "config_events_json",
            "config_iot_devices_json",
            "payloads_json",
            "event_feedback_content",
            "event_feedback_requirements",
            "state_machine_content",
            "hierarchy_content",
            "scene_config_content",
            "user_config_content",
        )
        bool_fields = (
            "config_json_validated",
            "config_events_validated",
            "config_iot_devices_validated",
            "payloads_validated",
            "event_feedback_validated",
            "state_machine_validated",
            "hierarchy_validated",
            "scene_glb_uploaded",
            "scene_config_validated",
            "user_config_validated",
        )
        json_dict_fields = (
            "processor_contents",
            "processor_validated",
            "processor_requirements",
            "event_action_contents",
            "event_action_validated",
            "event_action_requirements",
        )

        for field_name in string_fields + bool_fields:
            value = getattr(update, field_name)
            if value is not None:
                setattr(config, field_name, value)

        for field_name in json_dict_fields:
            value = getattr(update, field_name)
            if value is not None:
                setattr(config, field_name, json.dumps(value))
