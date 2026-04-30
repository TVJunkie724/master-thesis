"""Distributed validation for finishing Digital Twin configuration."""

import asyncio
import json
import logging
from typing import Any

from src.clients.deployer_client import DeployerClient
from src.clients.optimizer_client import OptimizerClient
from src.models.twin import DigitalTwin
from src.services.errors import ConfigurationValidationFailed, ExternalServiceError, ExternalServiceUnavailable

logger = logging.getLogger(__name__)


class ConfigurationValidationService:
    """Validates whether a twin can transition to CONFIGURED."""

    def __init__(
        self,
        optimizer_client: OptimizerClient | None = None,
        deployer_client: DeployerClient | None = None,
    ):
        self.optimizer_client = optimizer_client or OptimizerClient()
        self.deployer_client = deployer_client or DeployerClient()

    async def validate_configured_transition(self, twin: DigitalTwin) -> None:
        errors: list[dict[str, Any]] = []
        errors.extend(self._validate_local_step(twin))

        optimizer_payload, deployer_payload, payload_errors = self._build_validation_payloads(twin)
        errors.extend(payload_errors)

        if not payload_errors:
            optimizer_task = self.optimizer_client.validate_optimizer_config(optimizer_payload)
            deployer_task = self.deployer_client.validate_deployer_complete(deployer_payload)
            optimizer_result, deployer_result = await asyncio.gather(
                optimizer_task,
                deployer_task,
                return_exceptions=True,
            )
            errors.extend(self._collect_optimizer_errors(optimizer_result))
            errors.extend(self._collect_deployer_errors(deployer_result))

        if errors:
            logger.warning(
                "Twin %s validation failed with %d errors: %s",
                twin.id,
                len(errors),
                json.dumps(errors, indent=2, default=str),
            )
            raise ConfigurationValidationFailed(
                message=f"Cannot mark as configured: {len(errors)} validation errors",
                errors=errors,
            )

    def _validate_local_step(self, twin: DigitalTwin) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        if not twin.name or not twin.name.strip():
            errors.append({
                "step": 1,
                "code": "EMPTY_NAME",
                "field": "twin_name",
                "message": "Twin name is required",
            })

        config = twin.configuration if twin.configuration else None
        has_creds = False
        if config:
            has_creds = any([
                config.aws_cloud_connection_id,
                config.aws_access_key_id,
                config.azure_cloud_connection_id,
                config.azure_subscription_id,
                config.gcp_cloud_connection_id,
                config.gcp_project_id or config.gcp_billing_account,
            ])
        if not has_creds:
            errors.append({
                "step": 1,
                "code": "MISSING_CREDENTIALS",
                "field": "credentials",
                "message": "At least one cloud provider credentials required",
            })
        return errors

    def _build_validation_payloads(
        self,
        twin: DigitalTwin,
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        errors: list[dict[str, Any]] = []
        optimizer_config = twin.optimizer_config
        deployer_config = twin.deployer_config

        optimizer_params = self._parse_json_field(
            optimizer_config.params if optimizer_config else None,
            step=2,
            field="optimizer.params",
            errors=errors,
        )
        optimizer_result = self._parse_json_field(
            optimizer_config.result_json if optimizer_config else None,
            step=2,
            field="optimizer.result",
            errors=errors,
        )
        cheapest_path = {}
        if isinstance(optimizer_result, dict):
            cheapest_path = optimizer_result.get("calculationResult", {})

        optimizer_payload = {
            "params": optimizer_params,
            "result": optimizer_result,
        }

        deployer_payload = {
            "deployer_digital_twin_name": deployer_config.deployer_digital_twin_name if deployer_config else None,
            "config_events": deployer_config.config_events_json if deployer_config else None,
            "config_iot_devices": deployer_config.config_iot_devices_json if deployer_config else None,
            "payloads": deployer_config.payloads_json if deployer_config else None,
            "processors": self._parse_json_field(
                deployer_config.processor_contents if deployer_config else None,
                step=3,
                field="deployer.processors",
                errors=errors,
            ),
            "event_feedback": deployer_config.event_feedback_content if deployer_config else None,
            "event_actions": self._parse_json_field(
                deployer_config.event_action_contents if deployer_config else None,
                step=3,
                field="deployer.event_actions",
                errors=errors,
            ),
            "hierarchy": deployer_config.hierarchy_content if deployer_config else None,
            "scene_config": deployer_config.scene_config_content if deployer_config else None,
            "scene_glb_uploaded": deployer_config.scene_glb_uploaded if deployer_config else False,
            "state_machine": deployer_config.state_machine_content if deployer_config else None,
            "user_config": deployer_config.user_config_content if deployer_config else None,
            "optimizer_params": optimizer_params,
            "cheapest_path": cheapest_path,
        }

        return optimizer_payload, deployer_payload, errors

    def _parse_json_field(
        self,
        value: str | None,
        *,
        step: int,
        field: str,
        errors: list[dict[str, Any]],
    ) -> Any:
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            errors.append({
                "step": step,
                "code": "INVALID_JSON",
                "field": field,
                "message": f"Invalid JSON: {exc.msg}",
            })
            return None

    def _collect_optimizer_errors(self, result: Any) -> list[dict[str, Any]]:
        if isinstance(result, ExternalServiceUnavailable):
            return [{
                "step": 2,
                "code": "OPTIMIZER_UNAVAILABLE",
                "field": "optimizer",
                "message": f"Optimizer API error: {result.message}",
            }]
        if isinstance(result, ExternalServiceError):
            return [{
                "step": 2,
                "code": "OPTIMIZER_ERROR",
                "field": "optimizer",
                "message": f"Optimizer validation failed: {result.message}",
            }]
        if isinstance(result, Exception):
            return [{
                "step": 2,
                "code": "OPTIMIZER_UNAVAILABLE",
                "field": "optimizer",
                "message": f"Optimizer API error: {result}",
            }]
        if not result.get("valid"):
            return [{"step": 2, **error} for error in result.get("errors", [])]
        return []

    def _collect_deployer_errors(self, result: Any) -> list[dict[str, Any]]:
        if isinstance(result, ExternalServiceUnavailable):
            return [{
                "step": 3,
                "code": "DEPLOYER_UNAVAILABLE",
                "field": "deployer",
                "message": f"Deployer API error: {result.message}",
            }]
        if isinstance(result, ExternalServiceError):
            return [{
                "step": 3,
                "code": "DEPLOYER_ERROR",
                "field": "deployer",
                "message": f"Deployer validation failed: {result.message}",
            }]
        if isinstance(result, Exception):
            return [{
                "step": 3,
                "code": "DEPLOYER_UNAVAILABLE",
                "field": "deployer",
                "message": f"Deployer API error: {result}",
            }]
        if not result.get("valid"):
            return [{"step": 3, **error} for error in result.get("errors", [])]
        return []
