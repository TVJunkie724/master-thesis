"""Client for Management API calls to the Cloud Deployer service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from src.config import settings
from src.services.service_errors import DownstreamServiceError


class DeployerClient:
    """Typed client for read-oriented Deployer API operations."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float = 10.0):
        self.base_url = base_url or getattr(settings, "DEPLOYER_URL", "http://3cloud-deployer:8000")
        self.timeout_seconds = timeout_seconds

    async def check_cooldown(self, destroyed_at: datetime, uses_gcp_firestore: bool) -> dict[str, Any]:
        """Return the Deployer cooldown calculation for GCP Firestore redeploys."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/infrastructure/cooldown-check",
                    params={
                        "destroyed_at": destroyed_at.isoformat() + "Z",
                        "uses_gcp_firestore": str(uses_gcp_firestore).lower(),
                    },
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise DownstreamServiceError(
                status_code=exc.response.status_code,
                public_detail="Deployer API error",
            ) from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(
                status_code=503,
                public_detail="Deployer API unavailable",
            ) from exc

