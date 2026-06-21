"""Deployer configuration validation use cases."""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from src.config import settings
from src.models.deployer_config import DeployerConfiguration
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployer_config import ConfigValidationRequest, ConfigValidationResponse
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import EntityNotFoundError, ValidationError


CONFIG_TYPE_ENDPOINTS = {
    "events": "config/events",
    "iot": "config/iot",
    "config": "config/config",
    "hierarchy": "hierarchy",
    "payloads": "simulator/payloads",
    "function-code": "function-code",
    "state-machine": "state-machine",
    "scene-config": "scene-config",
    "user-config": "user-config",
}
L2_CONFIG_TYPES = {"function-code", "state-machine"}
L4_CONFIG_TYPES = {"hierarchy", "scene-config", "user-config"}


class DeployerConfigValidationService:
    """Owns deployer config validation proxying and validation flag persistence."""

    def __init__(self, db: Session, twin_repository: TwinRepository):
        self.db = db
        self.twin_repository = twin_repository

    async def validate_config(
        self,
        twin_id: str,
        user_id: str,
        config_type: str,
        request: ConfigValidationRequest,
    ) -> ConfigValidationResponse:
        """Validate a Step-3 config section through the Deployer API."""
        self._validate_config_type(config_type, request.provider)
        twin = self.twin_repository.get_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")

        try:
            async with httpx.AsyncClient() as client:
                response = await self._post_validation_request(client, twin, config_type, request)
        except httpx.ConnectError:
            return ConfigValidationResponse(
                valid=False,
                message="Cannot connect to Deployer API. Is it running on port 5004?",
            )
        except httpx.RequestError as exc:
            return ConfigValidationResponse(
                valid=False,
                message=f"Request error: {redact_secret_like_text(str(exc))}",
            )

        if response.status_code != 200:
            return ConfigValidationResponse(valid=False, message=self._extract_error_detail(response))

        result = response.json()
        message = result.get("message", "Valid")
        if config_type not in L2_CONFIG_TYPES:
            self._mark_validation_success(twin_id, twin, config_type)
        return ConfigValidationResponse(valid=True, message=message)

    @staticmethod
    def _validate_config_type(config_type: str, provider: str | None) -> None:
        if config_type not in CONFIG_TYPE_ENDPOINTS:
            raise ValidationError(f"Invalid config_type. Use: {list(CONFIG_TYPE_ENDPOINTS.keys())}")
        if config_type in L2_CONFIG_TYPES and not provider:
            raise ValidationError(f"provider is required for {config_type} validation (aws, azure, google)")
        if config_type in L4_CONFIG_TYPES and not provider:
            raise ValidationError(f"provider is required for {config_type} validation (aws or azure)")

    async def _post_validation_request(
        self,
        client: httpx.AsyncClient,
        twin,
        config_type: str,
        request: ConfigValidationRequest,
    ) -> httpx.Response:
        deployer_endpoint = CONFIG_TYPE_ENDPOINTS[config_type]
        if config_type in L2_CONFIG_TYPES:
            files = {"file": self._l2_upload_file(config_type, request.content)}
            return await client.post(
                f"{settings.DEPLOYER_URL}/validate/{deployer_endpoint}?provider={request.provider}",
                files=files,
                timeout=30.0,
            )

        if config_type in L4_CONFIG_TYPES:
            files = self._l4_upload_files(twin, config_type, request.content)
            return await client.post(
                f"{settings.DEPLOYER_URL}/validate/{deployer_endpoint}?provider={request.provider}",
                files=files,
                timeout=30.0,
            )

        files = {"file": (f"config_{config_type}.json", request.content.encode(), "application/json")}
        return await client.post(
            f"{settings.DEPLOYER_URL}/validate/{deployer_endpoint}",
            files=files,
            timeout=30.0,
        )

    @staticmethod
    def _l2_upload_file(config_type: str, content: str) -> tuple[str, bytes, str]:
        if config_type == "function-code":
            extension = ".py"
        else:
            extension = ".json" if content.strip().startswith(("{", "[")) else ".yaml"
        return (f"code{extension}", content.encode(), "text/plain")

    @staticmethod
    def _l4_upload_files(twin, config_type: str, content: str) -> dict[str, tuple[str, bytes, str]]:
        if config_type != "scene-config":
            return {"file": (f"{config_type}.json", content.encode(), "application/json")}

        config = twin.deployer_config
        hierarchy_content = config.hierarchy_content if config else ""
        return {
            "scene_file": ("scene.json", content.encode(), "application/json"),
            "hierarchy_file": ("hierarchy.json", (hierarchy_content or "").encode(), "application/json"),
        }

    def _mark_validation_success(self, twin_id: str, twin, config_type: str) -> None:
        config = twin.deployer_config
        if not config:
            config = DeployerConfiguration(twin_id=twin_id)
            self.db.add(config)

        validation_fields = {
            "config": "config_json_validated",
            "events": "config_events_validated",
            "iot": "config_iot_devices_validated",
            "payloads": "payloads_validated",
            "hierarchy": "hierarchy_validated",
            "scene-config": "scene_config_validated",
            "user-config": "user_config_validated",
        }
        field_name = validation_fields.get(config_type)
        if field_name:
            setattr(config, field_name, True)
            self.db.commit()

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        try:
            return redact_secret_like_text(str(response.json().get("detail", response.text)))
        except Exception:
            return redact_secret_like_text(response.text)
