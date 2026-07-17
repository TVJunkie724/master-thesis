"""Typed Optimizer API client."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from src.clients.base import ExternalServiceClient
from src.config import settings


MAX_PRICING_CATALOG_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class OptimizerProviderStatus:
    """Provider-scoped cache status from the Optimizer freshness endpoints."""

    provider: str
    status_code: int
    payload: dict[str, Any]

    @property
    def is_success(self) -> bool:
        return self.status_code == 200


class OptimizerClient(ExternalServiceClient):
    service_name = "Optimizer API"

    def __init__(self, base_url: str | None = None, **kwargs):
        super().__init__(
            base_url=base_url or getattr(settings, "OPTIMIZER_URL", "http://twin2clouds:8000"),
            **kwargs,
        )

    async def validate_optimizer_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/validate/optimizer-config",
            json=payload,
            timeout=30.0,
        )

    async def verify_permissions(self, provider: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/permissions/verify/{provider}",
            json=credentials,
            timeout=30.0,
        )

    async def calculate(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "PUT",
            "/calculate",
            json=params,
            timeout=60.0,
        )

    async def get_provider_capabilities(self) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            "/capabilities/providers",
            timeout=10.0,
        )

    async def get_cache_status(
        self,
        *,
        endpoint_prefix: str,
        provider: str,
        pricing_region: str | None = None,
    ) -> OptimizerProviderStatus:
        """Return one provider cache status while preserving non-200 detail."""
        params = (
            {"pricing_region": pricing_region}
            if pricing_region is not None
            else None
        )
        response = await self._request(
            "GET",
            f"/{endpoint_prefix}/{provider}",
            params=params,
            timeout=30.0,
        )
        payload = self._json_object(response) if response.status_code == 200 else {}
        return OptimizerProviderStatus(
            provider=provider,
            status_code=response.status_code,
            payload=payload,
        )

    async def get_pricing_catalog_baseline(
        self,
        provider: str,
    ) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            f"/pricing/catalogs/baseline/{quote(provider, safe='')}",
            timeout=30.0,
        )

    async def get_exact_pricing_catalog_reference(
        self,
        provider: str,
        pricing_region: str,
        snapshot_id: str,
    ) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            (
                f"/pricing/catalogs/{quote(provider, safe='')}/"
                f"{quote(pricing_region, safe='')}/snapshots/"
                f"{quote(snapshot_id, safe='')}/reference"
            ),
            timeout=30.0,
        )

    async def get_exact_pricing_catalog_snapshot(
        self,
        provider: str,
        pricing_region: str,
        snapshot_id: str,
    ) -> dict[str, Any]:
        response = await self._request_bounded_response(
            "GET",
            (
                f"/pricing/catalogs/{quote(provider, safe='')}/"
                f"{quote(pricing_region, safe='')}/snapshots/"
                f"{quote(snapshot_id, safe='')}"
            ),
            max_bytes=MAX_PRICING_CATALOG_BYTES,
            size_error_detail="Pricing catalog snapshot exceeds the diagnostic size limit.",
            timeout=30.0,
        )
        return self._json_object(response)

    async def refresh_pricing(
        self,
        provider: str,
        *,
        credentials: dict[str, Any] | None = None,
        force_fetch: bool = True,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/fetch_pricing_with_credentials/{quote(provider, safe='')}",
            params={"force_fetch": force_fetch},
            json=credentials or {},
            timeout=300.0,
        )

    async def refresh_azure_pricing(self) -> dict[str, Any]:
        return await self.refresh_pricing(
            "azure",
            credentials={},
            force_fetch=True,
        )

    async def refresh_pricing_with_credentials(
        self,
        provider: str,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.refresh_pricing(
            provider,
            credentials=credentials,
            force_fetch=True,
        )

    def stream_pricing_refresh(
        self,
        provider: str,
        credentials: dict[str, Any],
    ) -> AsyncIterator[str]:
        return self._stream_text_chunks(
            "POST",
            f"/stream/fetch_pricing/{provider}",
            json=credentials,
            headers={"Accept": "text/event-stream"},
            timeout=300.0,
        )
