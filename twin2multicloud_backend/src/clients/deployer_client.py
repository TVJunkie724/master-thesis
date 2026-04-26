"""Typed Deployer API client."""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import httpx

from src.clients.base import ExternalServiceClient
from src.config import settings


class DeployerClient(ExternalServiceClient):
    service_name = "Deployer API"

    def __init__(self, base_url: str | None = None, **kwargs):
        super().__init__(
            base_url=base_url or getattr(settings, "DEPLOYER_URL", "http://3cloud-deployer:8000"),
            **kwargs,
        )

    async def validate_deployer_complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/validate/deployer-complete",
            json=payload,
            timeout=30.0,
        )

    async def check_cooldown(
        self,
        destroyed_at: datetime,
        uses_gcp_firestore: bool,
    ) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            "/infrastructure/cooldown-check",
            params={
                "destroyed_at": f"{destroyed_at.isoformat()}Z",
                "uses_gcp_firestore": str(uses_gcp_firestore).lower(),
            },
            timeout=10.0,
        )

    def deploy_stream(self, provider: str, project_name: str) -> AsyncIterator[str]:
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        return self._stream_lines(
            "POST",
            "/infrastructure/deploy/stream",
            params={"provider": provider, "project_name": project_name},
            timeout=timeout,
        )

    def destroy_stream(self, provider: str, project_name: str) -> AsyncIterator[str]:
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        return self._stream_lines(
            "POST",
            "/infrastructure/destroy/stream",
            params={"provider": provider, "project_name": project_name},
            timeout=timeout,
        )

    async def start_log_trace(self, project_name: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/logs/trace/start",
            params={"project_name": project_name},
            timeout=30.0,
        )

    def stream_log_trace(self, project_name: str, trace_id: str) -> AsyncIterator[str]:
        return self._stream_lines(
            "GET",
            f"/logs/trace/stream/{trace_id}",
            params={"project_name": project_name},
            timeout=120.0,
        )

    async def verify_infrastructure(
        self,
        project_name: str,
        provider: str,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/infrastructure/verify",
            params={"project_name": project_name, "provider": provider},
            timeout=60.0,
        )

    def verify_dataflow(self, project_name: str, payload: dict[str, Any]) -> AsyncIterator[str]:
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        return self._stream_lines(
            "POST",
            "/dataflow/verify",
            params={"project_name": project_name},
            json={"payload": payload},
            timeout=timeout,
        )

    async def download_simulator(self, project_name: str, provider: str) -> bytes:
        return await self._request_bytes(
            "GET",
            f"/projects/{project_name}/simulator/{provider}/download",
            timeout=60.0,
        )
