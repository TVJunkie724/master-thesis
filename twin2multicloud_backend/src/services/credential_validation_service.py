"""Deployer-owned credential validation use cases."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session

from src.clients.deployer_client import DeployerClient
from src.repositories.twin_repository import TwinRepository
from src.schemas.twin_config import CredentialValidationResult, InlineValidationRequest
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.errors import (
    CredentialResolutionFailed,
    ExternalServiceError,
    ExternalServiceUnavailable,
)
from src.services.provider_contract import normalize_provider_id
from src.services.secret_redaction import (
    redact_validation_message,
    redact_validation_payload,
)
from src.services.service_errors import EntityNotFoundError, ValidationError

ValidatorCall = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class CredentialValidationService:
    """Validate stored or inline admin credentials only at the Deployer boundary."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        *,
        deployer_validator: ValidatorCall | None = None,
        deployer_client: DeployerClient | None = None,
    ) -> None:
        self.db = db
        self.twin_repository = twin_repository
        self.deployer_client = deployer_client or DeployerClient()
        self.deployer_validator = deployer_validator or self._call_deployer

    async def validate_stored_with_deployer(
        self,
        twin_id: str,
        user_id: str,
        provider: str,
    ) -> CredentialValidationResult:
        provider = self._normalize_provider(provider)
        twin = self._require_twin(twin_id, user_id)
        try:
            resolved = CredentialResolutionService().resolve_provider_credentials(
                twin,
                user_id,
                provider,
            )
        except CredentialResolutionFailed as exc:
            raise self._resolution_error(exc) from exc
        result = await self._validated_result(
            provider,
            resolved.deployer_validation_payload,
        )
        self._set_provider_validated(twin.configuration, provider, result["valid"])
        self.db.commit()
        return CredentialValidationResult(provider=provider, **result)

    async def validate_inline_with_deployer(
        self,
        request: InlineValidationRequest,
    ) -> CredentialValidationResult:
        provider = self._normalize_provider(request.provider)
        try:
            resolved = CredentialResolutionService().resolve_plaintext_credentials(
                provider,
                getattr(request, provider, None),
            )
        except CredentialResolutionFailed as exc:
            raise self._resolution_error(exc) from exc
        result = await self._validated_result(
            provider,
            resolved.deployer_validation_payload,
        )
        return CredentialValidationResult(provider=provider, **result)

    async def _validated_result(
        self,
        provider: str,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        raw = await self.deployer_validator(provider, credentials)
        return {
            "valid": bool(raw.get("valid", False)),
            "message": redact_validation_message(
                str(raw.get("message", "Validation complete")),
                credentials,
            ),
            "permissions": redact_validation_payload(
                raw.get("permissions", raw.get("missing_permissions")),
                credentials,
            ),
        }

    async def _call_deployer(
        self,
        provider: str,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            result = await self.deployer_client.verify_permissions(provider, credentials)
        except ExternalServiceUnavailable:
            return {
                "valid": False,
                "message": "Cannot connect to Deployer API (port 5004)",
            }
        except ExternalServiceError as exc:
            return {
                "valid": False,
                "message": f"Deployer API error: {exc.upstream_status_code or 502}",
            }
        return {
            "valid": (
                bool(result.get("valid"))
                or bool(result.get("ready"))
                or result.get("status") in {"valid", "passed"}
            ),
            "message": result.get("summary")
            or result.get("message", "Validation complete"),
            "permissions": result.get("missing_permissions"),
        }

    def _require_twin(self, twin_id: str, user_id: str):
        twin = self.twin_repository.get_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        try:
            return normalize_provider_id(provider)
        except ValueError as exc:
            raise ValidationError("Invalid provider. Use: aws, azure, gcp") from exc

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

    @staticmethod
    def _set_provider_validated(config, provider: str, valid: bool) -> None:
        if provider == "aws":
            config.aws_validated = valid
        elif provider == "azure":
            config.azure_validated = valid
        else:
            config.gcp_validated = valid
