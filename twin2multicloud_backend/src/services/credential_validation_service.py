"""Credential validation use cases for twin configuration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session

from src.clients.deployer_client import DeployerClient
from src.clients.optimizer_client import OptimizerClient
from src.repositories.twin_repository import TwinRepository
from src.schemas.twin_config import CredentialValidationResult, InlineValidationRequest
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.errors import CredentialResolutionFailed, ExternalServiceError, ExternalServiceUnavailable
from src.services.secret_redaction import redact_validation_message, redact_validation_payload
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.utils.crypto import decrypt


VALID_PROVIDERS = {"aws", "azure", "gcp"}
ValidatorCall = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class CredentialValidationService:
    """Owns stored and inline cloud credential validation workflows."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        *,
        optimizer_validator: ValidatorCall | None = None,
        deployer_validator: ValidatorCall | None = None,
        optimizer_client: OptimizerClient | None = None,
        deployer_client: DeployerClient | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.optimizer_client = optimizer_client or OptimizerClient()
        self.deployer_client = deployer_client or DeployerClient()
        self.optimizer_validator = optimizer_validator or self._call_optimizer
        self.deployer_validator = deployer_validator or self._call_deployer

    async def validate_stored_with_deployer(
        self,
        twin_id: str,
        user_id: str,
        provider: str,
    ) -> CredentialValidationResult:
        """Validate stored credentials against the Deployer and persist provider validity."""
        provider = self._normalize_provider(provider)
        twin = self._require_twin(twin_id, user_id)
        try:
            resolved = CredentialResolutionService().resolve_provider_credentials(twin, user_id, provider)
        except CredentialResolutionFailed as exc:
            raise self._resolution_error(exc) from exc
        credentials = resolved.deployer_validation_payload

        result = await self.deployer_validator(provider, credentials)
        sanitized = self._sanitize_result(result, credentials)
        valid = sanitized["valid"]
        self._set_provider_validated(twin.configuration, provider, valid)
        self.db.commit()

        return CredentialValidationResult(
            provider=provider,
            valid=valid,
            message=sanitized["message"],
            permissions=sanitized.get("permissions"),
        )

    async def validate_inline_with_deployer(self, request: InlineValidationRequest) -> CredentialValidationResult:
        """Validate plaintext request credentials against the Deployer without storing them."""
        provider = self._normalize_provider(request.provider)
        try:
            resolved = CredentialResolutionService().resolve_plaintext_credentials(
                provider,
                getattr(request, provider, None),
            )
        except CredentialResolutionFailed as exc:
            raise self._resolution_error(exc) from exc
        credentials = resolved.deployer_validation_payload

        result = await self.deployer_validator(provider, credentials)
        sanitized = self._sanitize_result(result, credentials)
        return CredentialValidationResult(
            provider=provider,
            valid=sanitized["valid"],
            message=sanitized["message"],
            permissions=sanitized.get("permissions"),
        )

    async def validate_inline_dual(self, request: InlineValidationRequest) -> dict[str, Any]:
        """Validate plaintext request credentials against Optimizer and Deployer."""
        provider = self._normalize_provider(request.provider)
        try:
            resolved = CredentialResolutionService().resolve_plaintext_credentials(
                provider,
                getattr(request, provider, None),
            )
        except CredentialResolutionFailed as exc:
            raise self._resolution_error(exc) from exc
        optimizer_creds = resolved.optimizer_payload
        deployer_creds = resolved.deployer_validation_payload
        return await self._perform_dual_validation(provider, optimizer_creds, deployer_creds)

    async def validate_stored_dual(self, twin_id: str, user_id: str, provider: str) -> dict[str, Any]:
        """Validate stored credentials against Optimizer and Deployer and persist combined validity."""
        provider = self._normalize_provider(provider)
        twin = self._require_twin(twin_id, user_id)
        try:
            resolved = CredentialResolutionService().resolve_provider_credentials(twin, user_id, provider)
        except CredentialResolutionFailed as exc:
            raise self._resolution_error(exc) from exc
        optimizer_creds = resolved.optimizer_payload
        deployer_creds = resolved.deployer_validation_payload
        result = await self._perform_dual_validation(provider, optimizer_creds, deployer_creds)
        self._set_provider_validated(twin.configuration, provider, result.get("valid", False))
        self.db.commit()
        return result

    def _normalize_provider(self, provider: str) -> str:
        provider = provider.lower()
        if provider not in VALID_PROVIDERS:
            raise ValidationError("Invalid provider. Use: aws, azure, gcp")
        return provider

    @staticmethod
    def _resolution_error(exc: CredentialResolutionFailed) -> ValidationError:
        return ValidationError(
            exc.message,
            detail={
                "code": "CREDENTIAL_RESOLUTION_FAILED",
                "message": exc.message,
                "errors": exc.errors,
            },
        )

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self.twin_repository.get_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    def _stored_deployer_credentials(self, config, provider: str, user_id: str, twin_id: str) -> dict[str, Any] | None:
        if provider == "aws":
            if not config.aws_access_key_id:
                return None
            return {
                "aws_access_key_id": decrypt(config.aws_access_key_id, user_id, twin_id),
                "aws_secret_access_key": decrypt(config.aws_secret_access_key, user_id, twin_id),
                "aws_region": config.aws_region,
                **(
                    {"aws_session_token": decrypt(config.aws_session_token, user_id, twin_id)}
                    if config.aws_session_token
                    else {}
                ),
            }
        if provider == "azure":
            if not config.azure_subscription_id:
                return None
            azure_region = config.azure_region
            return {
                "azure_subscription_id": decrypt(config.azure_subscription_id, user_id, twin_id),
                "azure_client_id": decrypt(config.azure_client_id, user_id, twin_id),
                "azure_client_secret": decrypt(config.azure_client_secret, user_id, twin_id),
                "azure_tenant_id": decrypt(config.azure_tenant_id, user_id, twin_id),
                "azure_region": azure_region,
                "azure_region_iothub": config.azure_region_iothub or azure_region,
                "azure_region_digital_twin": config.azure_region_digital_twin or azure_region,
            }
        if not config.gcp_project_id and not config.gcp_billing_account:
            return None
        return {
            "gcp_project_id": config.gcp_project_id,
            "gcp_billing_account": decrypt(config.gcp_billing_account, user_id, twin_id)
            if config.gcp_billing_account
            else None,
            "gcp_region": config.gcp_region,
            "gcp_credentials_file": decrypt(config.gcp_service_account_json, user_id, twin_id)
            if config.gcp_service_account_json
            else None,
        }

    def _stored_dual_credentials(
        self,
        config,
        provider: str,
        user_id: str,
        twin_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        deployer_creds = self._stored_deployer_credentials(config, provider, user_id, twin_id)
        if deployer_creds is None:
            return None
        if provider == "gcp":
            optimizer_creds = {
                "gcp_project_id": deployer_creds.get("gcp_project_id") or "placeholder-project",
                "gcp_credentials_file": deployer_creds.get("gcp_credentials_file"),
                "gcp_region": deployer_creds.get("gcp_region"),
            }
            return optimizer_creds, deployer_creds
        return deployer_creds.copy(), deployer_creds.copy()

    @staticmethod
    def _inline_deployer_credentials(request: InlineValidationRequest, provider: str) -> dict[str, Any] | None:
        if provider == "aws" and request.aws:
            credentials = {
                "aws_access_key_id": request.aws.access_key_id,
                "aws_secret_access_key": request.aws.secret_access_key,
                "aws_region": request.aws.region,
            }
            if request.aws.session_token:
                credentials["aws_session_token"] = request.aws.session_token
            return credentials
        if provider == "azure" and request.azure:
            return {
                "azure_subscription_id": request.azure.subscription_id,
                "azure_client_id": request.azure.client_id,
                "azure_client_secret": request.azure.client_secret,
                "azure_tenant_id": request.azure.tenant_id,
                "azure_region": request.azure.region,
                "azure_region_iothub": request.azure.region_iothub or request.azure.region,
                "azure_region_digital_twin": request.azure.region_digital_twin or request.azure.region,
            }
        if provider == "gcp" and request.gcp:
            return {
                "gcp_project_id": request.gcp.project_id,
                "gcp_billing_account": request.gcp.billing_account,
                "gcp_region": request.gcp.region,
                "gcp_credentials_file": request.gcp.service_account_json,
            }
        return None

    def _inline_dual_credentials(
        self,
        request: InlineValidationRequest,
        provider: str,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        deployer_creds = self._inline_deployer_credentials(request, provider)
        if deployer_creds is None:
            return None
        if provider == "gcp":
            optimizer_creds = {
                "gcp_project_id": deployer_creds.get("gcp_project_id") or "placeholder-project",
                "gcp_credentials_file": deployer_creds.get("gcp_credentials_file"),
                "gcp_region": deployer_creds.get("gcp_region"),
            }
            return optimizer_creds, deployer_creds
        return deployer_creds.copy(), deployer_creds.copy()

    async def _perform_dual_validation(
        self,
        provider: str,
        optimizer_creds: dict[str, Any],
        deployer_creds: dict[str, Any],
    ) -> dict[str, Any]:
        optimizer_result, deployer_result = await asyncio.gather(
            self.optimizer_validator(provider, optimizer_creds),
            self.deployer_validator(provider, deployer_creds),
        )
        optimizer = self._sanitize_result(optimizer_result, optimizer_creds)
        deployer = self._sanitize_result(deployer_result, deployer_creds)
        return {
            "provider": provider,
            "valid": optimizer.get("valid", False) and deployer.get("valid", False),
            "optimizer": {
                "valid": optimizer.get("valid", False),
                "message": optimizer.get("message", "Validation complete"),
            },
            "deployer": {
                "valid": deployer.get("valid", False),
                "message": deployer.get("message", "Validation complete"),
                "permissions": deployer.get("permissions"),
            },
        }

    @staticmethod
    def _set_provider_validated(config, provider: str, valid: bool) -> None:
        if provider == "aws":
            config.aws_validated = valid
        elif provider == "azure":
            config.azure_validated = valid
        elif provider == "gcp":
            config.gcp_validated = valid

    @staticmethod
    def _not_configured_result(provider: str) -> CredentialValidationResult:
        messages = {
            "aws": "AWS credentials not configured",
            "azure": "Azure credentials not configured",
            "gcp": "GCP credentials not configured (need project_id or billing_account)",
        }
        return CredentialValidationResult(provider=provider, valid=False, message=messages[provider])

    @staticmethod
    def _missing_dual_result(provider: str) -> dict[str, Any]:
        message = f"No {provider} credentials provided"
        return {
            "provider": provider,
            "valid": False,
            "optimizer": {"valid": False, "message": message},
            "deployer": {"valid": False, "message": message},
        }

    async def _call_optimizer(self, provider: str, credentials: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self.optimizer_client.verify_permissions(provider, credentials)
        except ExternalServiceUnavailable:
            return {"valid": False, "message": "Cannot connect to Optimizer API (port 5003)"}
        except ExternalServiceError as exc:
            return {"valid": False, "message": f"Optimizer API error: {exc.upstream_status_code or 502}"}

        return {
            "valid": result.get("valid", False) or result.get("status") == "valid",
            "message": result.get("message", "Validation complete"),
        }

    async def _call_deployer(self, provider: str, credentials: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self.deployer_client.verify_permissions(provider, credentials)
        except ExternalServiceUnavailable:
            return {"valid": False, "message": "Cannot connect to Deployer API (port 5004)"}
        except ExternalServiceError as exc:
            return {"valid": False, "message": f"Deployer API error: {exc.upstream_status_code or 502}"}

        return {
            "valid": result.get("valid", False) or result.get("status") == "valid",
            "message": result.get("message", "Validation complete"),
            "permissions": result.get("missing_permissions"),
        }

    def _sanitize_result(self, result: dict[str, Any], credentials: dict[str, Any]) -> dict[str, Any]:
        return {
            "valid": bool(result.get("valid", False)),
            "message": redact_validation_message(str(result.get("message", "Validation complete")), credentials),
            "permissions": redact_validation_payload(
                result.get("permissions", result.get("missing_permissions")),
                credentials,
            ),
        }
