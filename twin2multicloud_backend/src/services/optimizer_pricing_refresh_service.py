"""Optimizer pricing refresh use case."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.clients.optimizer_client import OptimizerClient
from src.repositories.twin_repository import TwinRepository
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.external_service_mapping import map_optimizer_client_error
from src.services.secret_redaction import redact_validation_message
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.errors import CredentialResolutionFailed
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError


SUPPORTED_PRICING_REFRESH_PROVIDERS = {"aws", "azure", "gcp"}


class OptimizerPricingRefreshService:
    """Owns pricing refresh credential materialization and Optimizer proxying."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        optimizer_client: OptimizerClient | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.optimizer_client = optimizer_client or OptimizerClient()

    async def refresh_pricing(self, provider: str, twin_id: str, user_id: str) -> dict[str, Any]:
        """Refresh provider pricing using the twin's stored credentials when required."""
        if provider not in SUPPORTED_PRICING_REFRESH_PROVIDERS:
            raise ValidationError(f"Invalid provider: {provider}. Must be aws, azure, or gcp")

        credentials: dict[str, str] = {}
        try:
            if provider == "azure":
                return await self.optimizer_client.refresh_azure_pricing()

            credentials = self._build_credentials(provider, twin_id, user_id)
            return await self.optimizer_client.refresh_pricing_with_credentials(
                provider,
                credentials,
            )
        except ExternalServiceUnavailable as exc:
            raise map_optimizer_client_error(exc) from exc
        except ExternalServiceError as exc:
            downstream = map_optimizer_client_error(exc)
            raise DownstreamServiceError(
                downstream.status_code,
                redact_validation_message(downstream.public_detail, credentials),
            ) from exc

    def _build_credentials(self, provider: str, twin_id: str, user_id: str) -> dict[str, str]:
        twin = self.twin_repository.get_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")

        try:
            resolved = CredentialResolutionService().resolve_provider_credentials(twin, user_id, provider)
        except CredentialResolutionFailed as exc:
            raise ValidationError(
                self._resolution_message(provider, exc),
                detail={"errors": exc.errors},
            ) from exc

        return self._optimizer_pricing_payload(provider, resolved.optimizer_payload)

    @staticmethod
    def _optimizer_pricing_payload(provider: str, optimizer_payload: dict) -> dict[str, str]:
        if provider != "gcp":
            return optimizer_payload
        payload = {
            "gcp_service_account_json": optimizer_payload.get("gcp_credentials_file"),
            "gcp_project_id": optimizer_payload.get("gcp_project_id"),
            "gcp_billing_account": optimizer_payload.get("gcp_billing_account"),
            "gcp_region": optimizer_payload.get("gcp_region"),
        }
        return {key: value for key, value in payload.items() if value}

    @staticmethod
    def _resolution_message(provider: str, exc: CredentialResolutionFailed) -> str:
        codes = {error.get("code") for error in exc.errors}
        if "MISSING_CONFIGURATION" in codes:
            return "Twin has no configuration. Complete Step 1 first."
        if "MISSING_CLOUD_CONNECTION" in codes:
            return f"{provider.upper()} credentials not configured"
        if "MISSING_CREDENTIAL_FIELD" in codes:
            return f"{provider.upper()} credentials not configured"
        return exc.message
