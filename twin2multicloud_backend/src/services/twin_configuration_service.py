"""Twin configuration read/write use cases."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import TwinState
from src.models.twin_config import TwinConfiguration
from src.repositories.twin_repository import TwinRepository
from src.schemas.twin_config import TwinConfigResponse, TwinConfigUpdate
from src.services.optimizer_config_projection import set_cheapest_columns_from_payload
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.utils.crypto import encrypt


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
        return TwinConfigResponse.from_db(config, twin.optimizer_config)

    def update_config(self, twin_id: str, user_id: str, update: TwinConfigUpdate) -> dict[str, Any]:
        """Persist config changes, encrypting credentials and regressing state when required."""
        twin = self._require_twin(twin_id, user_id)
        if twin.state in BLOCKED_CONFIG_STATES:
            raise ValidationError(f"Cannot modify twin in '{twin.state.value}' state")

        should_regress = twin.state in REGRESS_CONFIG_STATES
        config = self._ensure_config(twin_id, twin, commit=False)

        if update.debug_mode is not None:
            config.debug_mode = update.debug_mode
        if update.aws:
            self._apply_aws(config, update, user_id, twin_id)
        if update.azure:
            self._apply_azure(config, update, user_id, twin_id)
        if update.gcp:
            self._apply_gcp(config, update, user_id, twin_id)
        if update.highest_step_reached is not None:
            config.highest_step_reached = update.highest_step_reached

        if update.optimizer_params is not None or update.optimizer_result is not None:
            self._apply_optimizer_result(twin_id, twin, update)

        if should_regress:
            twin.state = TwinState.DRAFT

        self.db.commit()
        self.db.refresh(config)
        self.db.refresh(twin)

        response = TwinConfigResponse.from_db(config, twin.optimizer_config)
        return {**response.model_dump(), "twin_state": twin.state.value}

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self.twin_repository.get_for_user(twin_id, user_id)
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

    @staticmethod
    def _apply_aws(config: TwinConfiguration, update: TwinConfigUpdate, user_id: str, twin_id: str) -> None:
        config.aws_access_key_id = encrypt(update.aws.access_key_id, user_id, twin_id)
        config.aws_secret_access_key = encrypt(update.aws.secret_access_key, user_id, twin_id)
        config.aws_region = update.aws.region
        config.aws_sso_region = update.aws.sso_region
        config.aws_session_token = encrypt(update.aws.session_token, user_id, twin_id) if update.aws.session_token else None
        config.aws_validated = False

    @staticmethod
    def _apply_azure(config: TwinConfiguration, update: TwinConfigUpdate, user_id: str, twin_id: str) -> None:
        config.azure_subscription_id = encrypt(update.azure.subscription_id, user_id, twin_id)
        config.azure_client_id = encrypt(update.azure.client_id, user_id, twin_id)
        config.azure_client_secret = encrypt(update.azure.client_secret, user_id, twin_id)
        config.azure_tenant_id = encrypt(update.azure.tenant_id, user_id, twin_id)
        config.azure_region = update.azure.region
        config.azure_region_iothub = update.azure.region_iothub or None
        config.azure_region_digital_twin = update.azure.region_digital_twin or None
        config.azure_validated = False

    @staticmethod
    def _apply_gcp(config: TwinConfiguration, update: TwinConfigUpdate, user_id: str, twin_id: str) -> None:
        config.gcp_project_id = update.gcp.project_id
        config.gcp_billing_account = (
            encrypt(update.gcp.billing_account, user_id, twin_id) if update.gcp.billing_account else None
        )
        config.gcp_region = update.gcp.region
        if update.gcp.service_account_json:
            config.gcp_service_account_json = encrypt(update.gcp.service_account_json, user_id, twin_id)
        config.gcp_validated = False

    def _apply_optimizer_result(self, twin_id: str, twin, update: TwinConfigUpdate) -> None:
        optimizer_config = twin.optimizer_config
        if not optimizer_config:
            optimizer_config = OptimizerConfiguration(twin_id=twin_id)
            self.db.add(optimizer_config)
            twin.optimizer_config = optimizer_config

        if update.optimizer_params is not None:
            optimizer_config.params = json.dumps(update.optimizer_params)
        if update.optimizer_result is not None:
            optimizer_config.result_json = json.dumps(update.optimizer_result)
            set_cheapest_columns_from_payload(optimizer_config, optimizer_result=update.optimizer_result)
