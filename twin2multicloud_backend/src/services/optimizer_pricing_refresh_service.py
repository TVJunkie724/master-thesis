"""Optimizer pricing refresh use case."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.config import settings
from src.repositories.twin_repository import TwinRepository
from src.services.secret_redaction import redact_validation_message
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError
from src.utils.crypto import decrypt


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

        config = twin.configuration
        if not config:
            raise ValidationError("Twin has no configuration. Complete Step 1 first.")

        if provider == "aws":
            if not (config.aws_access_key_id and config.aws_secret_access_key):
                raise ValidationError("AWS credentials not configured in Step 1")
            return {
                "aws_access_key_id": decrypt(config.aws_access_key_id, user_id, twin_id),
                "aws_secret_access_key": decrypt(config.aws_secret_access_key, user_id, twin_id),
                "aws_region": config.aws_region or "eu-central-1",
            }

        if not config.gcp_service_account_json:
            raise ValidationError("GCP credentials not configured in Step 1")
        return {
            "gcp_service_account_json": decrypt(config.gcp_service_account_json, user_id, twin_id),
            "gcp_region": config.gcp_region or "europe-west1",
        }
