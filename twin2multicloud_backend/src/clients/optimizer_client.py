"""Typed Optimizer API client."""

from typing import Any
from urllib.parse import quote

import httpx

from src.clients.base import ExternalServiceClient
from src.config import settings
from src.security.request_context import current_request_id
from src.services.errors import ExternalServiceError

ARCHITECTURE_RESOLUTION_ERROR_CODES = frozenset(
    {
        "ARCH_PROFILE_NOT_FOUND",
        "ARCH_PROFILE_DIGEST_MISMATCH",
        "ARCH_PROFILE_BUNDLE_INCOMPATIBLE",
        "ARCH_WORKLOAD_INCOMPATIBLE",
        "ARCH_EXTENSION_BINDING_INVALID",
        "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
        "ARCH_COMPONENT_CANDIDATE_MISSING",
        "ARCH_EDGE_IMPLEMENTATION_MISSING",
        "ARCH_FUNCTIONAL_INCOMPLETE",
        "ARCH_PRICING_EVIDENCE_MISSING",
        "ARCH_FORMULA_MISSING",
        "ARCH_DEPLOYMENT_MAPPING_MISSING",
        "ARCH_NO_ADMISSIBLE_CANDIDATE",
        "ARCH_RESOLUTION_BUILD_FAILED",
    }
)


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

    async def calculate(self, params: dict[str, Any]) -> dict[str, Any]:
        response = await self._request(
            "PUT",
            "/calculate",
            json=params,
            headers={"X-Request-ID": current_request_id()},
            timeout=60.0,
        )
        if response.status_code >= 400:
            error_code = _architecture_resolution_error_code(response)
            if error_code is not None:
                raise ExternalServiceError(
                    f"Optimizer API rejected architecture resolution: {error_code}",
                    upstream_status_code=response.status_code,
                    public_detail=(
                        "Optimizer rejected architecture profile resolution."
                    ),
                    error_code=error_code,
                )
            self._raise_for_status(response)
        return self._json_object(response)

    async def get_provider_capabilities(self) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            "/capabilities/providers",
            timeout=10.0,
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

def _architecture_resolution_error_code(
    response: httpx.Response,
) -> str | None:
    if response.status_code != 409 or len(response.content) > 64 * 1024:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    detail = payload.get("detail", payload)
    if not isinstance(detail, dict):
        return None
    error_code = detail.get("error_code")
    if error_code not in ARCHITECTURE_RESOLUTION_ERROR_CODES:
        return None
    return str(error_code)
