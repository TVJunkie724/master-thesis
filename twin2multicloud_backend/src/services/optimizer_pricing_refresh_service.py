"""Optimizer pricing refresh use case."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.config import settings
from src.repositories.twin_repository import TwinRepository
from src.services.secret_redaction import redact_validation_message
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.errors import CredentialResolutionFailed
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError


OPTIMIZER_URL = getattr(settings, "OPTIMIZER_URL", "http://master-thesis-2twin2clouds-1:8000")
SUPPORTED_PRICING_REFRESH_PROVIDERS = {"aws", "azure", "gcp"}


class OptimizerPricingRefreshService:
    """Owns pricing refresh credential materialization and Optimizer proxying."""

    def __init__(self, db: Session, twin_repository: TwinRepository):
        self.db = db
        self.twin_repository = twin_repository

    async def refresh_pricing(self, provider: str, twin_id: str, user_id: str) -> dict[str, Any]:
        """Refresh provider pricing using the twin's stored credentials when required."""
        if provider not in SUPPORTED_PRICING_REFRESH_PROVIDERS:
            raise ValidationError(f"Invalid provider: {provider}. Must be aws, azure, or gcp")

        credentials: dict[str, str] = {}
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                if provider == "azure":
                    response = await client.post(
                        f"{OPTIMIZER_URL}/fetch_pricing/azure",
                        params={"force_fetch": True},
                    )
                else:
                    credentials = self._build_credentials(provider, twin_id, user_id)
                    response = await client.post(
                        f"{OPTIMIZER_URL}/fetch_pricing_with_credentials/{provider}",
                        json=credentials,
                    )
        except httpx.ConnectError as exc:
            raise DownstreamServiceError(503, "Cannot connect to Optimizer service") from exc
        except httpx.TimeoutException as exc:
            raise DownstreamServiceError(504, "Optimizer service timed out") from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(502, f"Request failed: {type(exc).__name__}") from exc

        if response.status_code != 200:
            raise DownstreamServiceError(
                response.status_code,
                redact_validation_message(response.text, credentials),
            )
        return response.json()

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
