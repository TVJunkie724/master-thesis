"""Optimizer pricing refresh SSE stream use case."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx
from sqlalchemy.orm import Session

from src.config import settings
from src.repositories.twin_repository import TwinRepository
from src.services.service_errors import EntityNotFoundError, ValidationError
from src.utils.crypto import decrypt


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
                yield self._emit("Loading twin credentials...")
                await asyncio.sleep(self.sleep_seconds)
                credentials = self._build_credentials(provider, twin_id, user_id)
                yield self._emit(f"{provider.upper()} credentials loaded and decrypted")

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

    @staticmethod
    def _emit(message: str, event_type: str = "log") -> str:
        return f"event: {event_type}\ndata: {json.dumps({'message': message, 'type': event_type})}\n\n"
