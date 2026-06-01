"""Backend-owned update semantics for wizard configuration persistence."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.deployer_config import DeployerConfiguration
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.twin_config import TwinConfiguration
from src.schemas.deployer_config import DeployerConfigUpdate
from src.schemas.twin_config import TwinConfigUpdate
from src.services.cloud_connection_service import CloudConnectionService

BLOCKED_EDIT_STATES = {TwinState.DEPLOYED, TwinState.DEPLOYING, TwinState.DESTROYING}
REGRESS_TO_DRAFT_STATES = {TwinState.CONFIGURED, TwinState.ERROR, TwinState.DESTROYED}
LEGACY_CREDENTIAL_WRITE_DISABLED_DETAIL = (
    "Direct per-twin credential storage is disabled. "
    "Create or import a Cloud Connection and bind it via cloud_connections."
)


class WizardConfigurationService:
    """Apply typed wizard update commands to canonical backend state."""

    def __init__(self, db: Session):
        self.db = db

    def apply_twin_config_update(
        self,
        twin: DigitalTwin,
        update: TwinConfigUpdate,
        user_id: str,
    ) -> TwinConfiguration:
        self._assert_twin_editable(twin)
        should_regress = twin.state in REGRESS_TO_DRAFT_STATES

        config = self._ensure_twin_config(twin)

        if update.debug_mode is not None:
            config.debug_mode = update.debug_mode

        self._apply_provider_configuration(config, update)
        self._apply_cloud_connection_bindings(config, update, user_id)

        if update.highest_step_reached is not None:
            config.highest_step_reached = update.highest_step_reached

        self._apply_optimizer_update(twin, update)

        if should_regress:
            twin.state = TwinState.DRAFT

        return config

    def apply_deployer_config_update(
        self,
        twin: DigitalTwin,
        update: DeployerConfigUpdate,
    ) -> DeployerConfiguration:
        self._assert_twin_editable(twin)
        should_regress = twin.state in REGRESS_TO_DRAFT_STATES

        config = self._ensure_deployer_config(twin)

        if self._field_present(update, "deployer_digital_twin_name"):
            value = update.deployer_digital_twin_name
            if value is not None and len(value) > 15:
                raise HTTPException(
                    status_code=400,
                    detail="Digital twin name exceeds 15 characters",
                )
            config.deployer_digital_twin_name = value

        for field in _DEPLOYER_TEXT_FIELDS:
            self._apply_scalar_field(config, update, field)

        for field in _DEPLOYER_BOOL_FIELDS:
            self._apply_bool_field(config, update, field)

        for field in _DEPLOYER_JSON_MAP_FIELDS:
            self._apply_json_map_field(config, update, field)

        if should_regress:
            twin.state = TwinState.DRAFT

        return config

    def _assert_twin_editable(self, twin: DigitalTwin) -> None:
        if twin.state in BLOCKED_EDIT_STATES:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot modify twin in '{twin.state.value}' state",
            )

    def _ensure_twin_config(self, twin: DigitalTwin) -> TwinConfiguration:
        if twin.configuration:
            return twin.configuration
        config = TwinConfiguration(twin_id=twin.id)
        self.db.add(config)
        twin.configuration = config
        return config

    def _ensure_deployer_config(self, twin: DigitalTwin) -> DeployerConfiguration:
        if twin.deployer_config:
            return twin.deployer_config
        config = DeployerConfiguration(twin_id=twin.id)
        self.db.add(config)
        twin.deployer_config = config
        return config

    def _apply_provider_configuration(
        self,
        config: TwinConfiguration,
        update: TwinConfigUpdate,
    ) -> None:
        if self._field_present(update, "aws") and update.aws is None:
            self._clear_provider_configuration(config, "aws")
        elif update.aws:
            raise HTTPException(status_code=400, detail=LEGACY_CREDENTIAL_WRITE_DISABLED_DETAIL)

        if self._field_present(update, "azure") and update.azure is None:
            self._clear_provider_configuration(config, "azure")
        elif update.azure:
            raise HTTPException(status_code=400, detail=LEGACY_CREDENTIAL_WRITE_DISABLED_DETAIL)

        if self._field_present(update, "gcp") and update.gcp is None:
            self._clear_provider_configuration(config, "gcp")
        elif update.gcp:
            raise HTTPException(status_code=400, detail=LEGACY_CREDENTIAL_WRITE_DISABLED_DETAIL)

    def _apply_cloud_connection_bindings(
        self,
        config: TwinConfiguration,
        update: TwinConfigUpdate,
        user_id: str,
    ) -> None:
        if not self._field_present(update, "cloud_connections"):
            return

        if update.cloud_connections is None:
            for provider in ("aws", "azure", "gcp"):
                self._bind_cloud_connection(config, user_id, provider, None)
            return

        for provider in ("aws", "azure", "gcp"):
            if self._field_present(update.cloud_connections, provider):
                self._bind_cloud_connection(
                    config,
                    user_id,
                    provider,
                    getattr(update.cloud_connections, provider),
                )

    def _apply_optimizer_update(self, twin: DigitalTwin, update: TwinConfigUpdate) -> None:
        has_params = self._field_present(update, "optimizer_params")
        has_result = self._field_present(update, "optimizer_result")
        if not has_params and not has_result:
            return

        opt_config = twin.optimizer_config
        if not opt_config:
            opt_config = OptimizerConfiguration(twin_id=twin.id)
            self.db.add(opt_config)
            twin.optimizer_config = opt_config

        if has_params:
            opt_config.params = (
                self._json_dumps(update.optimizer_params)
                if update.optimizer_params is not None
                else None
            )
        if has_result:
            opt_config.result_json = (
                self._json_dumps(update.optimizer_result)
                if update.optimizer_result is not None
                else None
            )
            if update.optimizer_result is None:
                self._clear_cheapest_columns(opt_config)
            else:
                self._populate_cheapest_columns(opt_config, update.optimizer_result)

    def _bind_cloud_connection(
        self,
        config: TwinConfiguration,
        user_id: str,
        provider: str,
        connection_id: str | None,
    ) -> None:
        if connection_id is None:
            setattr(config, self._connection_id_attr(provider), None)
            setattr(config, self._validation_attr(provider), False)
            return

        service = CloudConnectionService(self.db)
        connection = service.get_connection(connection_id, user_id)
        if not connection:
            raise HTTPException(status_code=404, detail=f"{provider.upper()} Cloud connection not found")
        if connection.provider != provider:
            raise HTTPException(status_code=400, detail=f"Cloud connection provider must be {provider}")

        setattr(config, self._connection_id_attr(provider), connection.id)
        setattr(config, self._validation_attr(provider), connection.validation_status == "valid")
        self._clear_legacy_credentials(config, provider)
        self._copy_connection_metadata(config, provider, service.decrypt_payload(connection, user_id))

    def _clear_provider_configuration(self, config: TwinConfiguration, provider: str) -> None:
        setattr(config, self._connection_id_attr(provider), None)
        setattr(config, self._validation_attr(provider), False)
        self._clear_legacy_credentials(config, provider)

        if provider == "aws":
            config.aws_region = "eu-central-1"
        elif provider == "azure":
            config.azure_region = "westeurope"
            config.azure_region_iothub = None
            config.azure_region_digital_twin = None
        elif provider == "gcp":
            config.gcp_project_id = None
            config.gcp_region = "europe-west1"

    def _clear_legacy_credentials(self, config: TwinConfiguration, provider: str) -> None:
        legacy_fields = {
            "aws": [
                "aws_access_key_id",
                "aws_secret_access_key",
                "aws_session_token",
                "aws_sso_region",
            ],
            "azure": [
                "azure_subscription_id",
                "azure_client_id",
                "azure_client_secret",
                "azure_tenant_id",
            ],
            "gcp": [
                "gcp_billing_account",
                "gcp_service_account_json",
            ],
        }
        for field in legacy_fields[provider]:
            setattr(config, field, None)

    def _copy_connection_metadata(self, config: TwinConfiguration, provider: str, payload: dict) -> None:
        if provider == "aws":
            config.aws_region = payload.get("aws_region") or config.aws_region
            config.aws_sso_region = payload.get("aws_sso_region")
        elif provider == "azure":
            azure_region = payload.get("azure_region") or config.azure_region
            config.azure_region = azure_region
            config.azure_region_iothub = payload.get("azure_region_iothub") or azure_region
            config.azure_region_digital_twin = payload.get("azure_region_digital_twin") or azure_region
        elif provider == "gcp":
            config.gcp_project_id = payload.get("gcp_project_id") or config.gcp_project_id
            config.gcp_region = payload.get("gcp_region") or config.gcp_region

    def _apply_scalar_field(
        self,
        config: DeployerConfiguration,
        update: DeployerConfigUpdate,
        field: str,
    ) -> None:
        if self._field_present(update, field):
            setattr(config, field, getattr(update, field))

    def _apply_bool_field(
        self,
        config: DeployerConfiguration,
        update: DeployerConfigUpdate,
        field: str,
    ) -> None:
        if self._field_present(update, field):
            setattr(config, field, bool(getattr(update, field)))

    def _apply_json_map_field(
        self,
        config: DeployerConfiguration,
        update: DeployerConfigUpdate,
        field: str,
    ) -> None:
        if self._field_present(update, field):
            value = getattr(update, field)
            setattr(config, field, self._json_dumps(value) if value is not None else None)

    @staticmethod
    def _populate_cheapest_columns(opt_config: OptimizerConfiguration, optimizer_result: dict | None) -> None:
        if not optimizer_result or not isinstance(optimizer_result, dict):
            return

        def _from_path(prefix: str) -> str | None:
            path = optimizer_result.get("cheapestPath")
            if not isinstance(path, list):
                return None
            for segment in path:
                if isinstance(segment, str) and segment.startswith(prefix):
                    return segment[len(prefix):].lower() or None
            return None

        def _from_calc(*keys: str) -> str | None:
            node: Any = optimizer_result.get("calculationResult")
            for key in keys:
                if not isinstance(node, dict):
                    return None
                node = node.get(key)
            return node.lower() if isinstance(node, str) and node else None

        opt_config.cheapest_l1 = _from_path("L1_") or _from_calc("L1")
        opt_config.cheapest_l2 = _from_path("L2_") or _from_calc("L2")
        opt_config.cheapest_l3_hot = _from_path("L3_hot_") or _from_calc("L3", "Hot")
        opt_config.cheapest_l3_cool = _from_path("L3_cool_") or _from_calc("L3", "Cool")
        opt_config.cheapest_l3_archive = _from_path("L3_archive_") or _from_calc("L3", "Archive")
        opt_config.cheapest_l4 = _from_path("L4_") or _from_calc("L4")
        opt_config.cheapest_l5 = _from_path("L5_") or _from_calc("L5")

    @staticmethod
    def _clear_cheapest_columns(opt_config: OptimizerConfiguration) -> None:
        opt_config.cheapest_l1 = None
        opt_config.cheapest_l2 = None
        opt_config.cheapest_l3_hot = None
        opt_config.cheapest_l3_cool = None
        opt_config.cheapest_l3_archive = None
        opt_config.cheapest_l4 = None
        opt_config.cheapest_l5 = None

    @staticmethod
    def _connection_id_attr(provider: str) -> str:
        return f"{provider}_cloud_connection_id"

    @staticmethod
    def _validation_attr(provider: str) -> str:
        return f"{provider}_validated"

    @staticmethod
    def _field_present(model, field: str) -> bool:
        return field in model.model_fields_set

    @staticmethod
    def _json_dumps(value) -> str:
        return json.dumps(value)


_DEPLOYER_TEXT_FIELDS = (
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

_DEPLOYER_BOOL_FIELDS = (
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

_DEPLOYER_JSON_MAP_FIELDS = (
    "processor_contents",
    "processor_validated",
    "processor_requirements",
    "event_action_contents",
    "event_action_validated",
    "event_action_requirements",
)
