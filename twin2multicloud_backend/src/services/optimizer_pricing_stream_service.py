"""Optimizer pricing refresh SSE stream use case."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx
from sqlalchemy.orm import Session

from src.config import settings
from src.repositories.twin_repository import TwinRepository
from src.services.credential_resolution_service import CredentialResolutionService
from src.services.errors import CredentialResolutionFailed
from src.services.service_errors import EntityNotFoundError, ValidationError


OPTIMIZER_URL = getattr(settings, "OPTIMIZER_URL", "http://master-thesis-2twin2clouds-1:8000")
SUPPORTED_PRICING_STREAM_PROVIDERS = {"aws", "azure", "gcp"}


class OptimizerPricingStreamService:
    """Owns pricing refresh SSE event generation and Optimizer stream relay."""

    def __init__(self, db: Session, twin_repository: TwinRepository, sleep_seconds: float = 0.1):
        self.db = db
        self.twin_repository = twin_repository
        self.sleep_seconds = sleep_seconds

    def build_refresh_stream(self, provider: str, twin_id: str, user_id: str) -> AsyncIterator[str]:
        """Return an SSE generator for the requested provider pricing refresh."""
        if provider not in SUPPORTED_PRICING_STREAM_PROVIDERS:
            raise ValidationError(f"Invalid provider: {provider}")
        return self._event_generator(provider, twin_id, user_id)

    async def _event_generator(self, provider: str, twin_id: str, user_id: str) -> AsyncIterator[str]:
        yield self._emit(f"Starting {provider.upper()} pricing refresh...")
        await asyncio.sleep(self.sleep_seconds)

        try:
            credentials: dict[str, str] = {}
            if provider == "azure":
                yield self._emit("Azure uses public API - no credentials needed")
            else:
                yield self._emit("Loading Cloud Connection credentials...")
                await asyncio.sleep(self.sleep_seconds)
                credentials = self._build_credentials(provider, twin_id, user_id)
                yield self._emit(f"{provider.upper()} Cloud Connection credentials loaded")

            await asyncio.sleep(self.sleep_seconds)
            yield self._emit(f"Connecting to Optimizer service for {provider.upper()} pricing...")

            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{OPTIMIZER_URL}/stream/fetch_pricing/{provider}",
                    json=credentials,
                    headers={"Accept": "text/event-stream"},
                ) as response:
                    if response.status_code != 200:
                        yield self._emit(f"❌ Optimizer error: {response.status_code}", "error")
                        return

                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            if event_str.strip():
                                yield event_str + "\n\n"

        except httpx.ConnectError:
            yield self._emit("❌ Error: Cannot connect to Optimizer service", "error")
        except httpx.TimeoutException:
            yield self._emit("❌ Error: Optimizer service timed out", "error")
        except Exception as exc:
            yield self._emit(f"❌ Error: {str(exc)}", "error")

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

    @staticmethod
    def _emit(message: str, event_type: str = "log") -> str:
        return f"event: {event_type}\ndata: {json.dumps({'message': message, 'type': event_type})}\n\n"
