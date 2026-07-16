"""Typed Deployer API client."""

import json
import io
import re
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from src.clients.base import ExternalServiceClient
from src.config import settings
from src.services.errors import ExternalServiceError


MAX_SIMULATOR_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_PROJECT_EXTRACTION_RESPONSE_BYTES = 192 * 1024 * 1024
_SAFE_SIMULATOR_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}\.zip$")
_SAFE_OPERATION_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_SIMULATOR_CREDENTIAL_CLASSES = {
    "aws": "aws_iot_device_certificate",
    "azure": "azure_iot_hub_device_identity",
    "gcp": "gcp_pubsub_topic_publisher",
}


@dataclass(frozen=True)
class DeployerSimulatorArchive:
    """Validated simulator archive received from the Deployer API."""

    content: bytes
    filename: str
    provider: str
    credential_class: str
    media_type: str = "application/zip"


class DeployerClient(ExternalServiceClient):
    service_name = "Deployer API"

    def __init__(self, base_url: str | None = None, **kwargs):
        super().__init__(
            base_url=base_url
            or getattr(settings, "DEPLOYER_URL", "http://3cloud-deployer:8000"),
            **kwargs,
        )

    async def validate_deployer_complete(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/validate/deployer-complete",
            json=payload,
            timeout=30.0,
        )

    async def get_provider_capabilities(self) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            "/capabilities/providers",
            timeout=10.0,
        )

    async def verify_permissions(
        self, provider: str, credentials: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            f"/permissions/verify/{provider}",
            json=credentials,
            timeout=30.0,
        )

    async def validate_config_file(
        self,
        endpoint: str,
        files: dict[str, tuple[str, bytes, str]],
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        params = {"provider": provider} if provider else None
        return await self._request_json(
            "POST",
            f"/validate/{endpoint}",
            params=params,
            files=files,
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

    def deploy_stream(
        self,
        provider: str,
        project_name: str,
        operation_token: str,
    ) -> AsyncIterator[str]:
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        return self._stream_lines(
            "POST",
            "/infrastructure/deploy/stream",
            params={"provider": provider, "project_name": project_name},
            headers={"X-Operation-Package": operation_token},
            timeout=timeout,
        )

    def destroy_stream(
        self,
        provider: str,
        project_name: str,
        operation_token: str,
    ) -> AsyncIterator[str]:
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        return self._stream_lines(
            "POST",
            "/infrastructure/destroy/stream",
            params={"provider": provider, "project_name": project_name},
            headers={"X-Operation-Package": operation_token},
            timeout=timeout,
        )

    async def start_log_trace(
        self,
        project_name: str,
        operation_token: str,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/logs/trace/start",
            params={"project_name": project_name},
            headers={"X-Operation-Package": operation_token},
            timeout=30.0,
        )

    def stream_log_trace(
        self,
        project_name: str,
        trace_id: str,
        operation_token: str,
    ) -> AsyncIterator[str]:
        return self._stream_lines(
            "GET",
            f"/logs/trace/stream/{trace_id}",
            params={"project_name": project_name},
            headers={"X-Operation-Package": operation_token},
            timeout=120.0,
        )

    async def verify_infrastructure(
        self,
        project_name: str,
        provider: str,
        operation_token: str,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/infrastructure/verify",
            params={"project_name": project_name, "provider": provider},
            headers={"X-Operation-Package": operation_token},
            timeout=60.0,
        )

    def verify_dataflow(
        self,
        project_name: str,
        payload: dict[str, Any],
        operation_token: str,
    ) -> AsyncIterator[str]:
        timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
        return self._stream_lines(
            "POST",
            "/dataflow/verify",
            params={"project_name": project_name},
            json={"payload": payload},
            headers={"X-Operation-Package": operation_token},
            timeout=timeout,
        )

    async def download_simulator(
        self,
        project_name: str,
        provider: str,
        operation_token: str,
    ) -> DeployerSimulatorArchive:
        response = await self._request_bounded_response(
            "GET",
            f"/projects/{project_name}/simulator/{provider}/download",
            max_bytes=MAX_SIMULATOR_ARCHIVE_BYTES,
            size_error_detail="Deployer returned an invalid simulator archive size.",
            headers={"X-Operation-Package": operation_token},
            timeout=60.0,
        )
        return _parse_simulator_archive(response, requested_provider=provider)

    async def stage_operation_package(
        self,
        project_name: str,
        content: bytes,
    ) -> dict[str, Any]:
        """Stage a generated credential package for exactly one Deployer operation."""
        payload = await self._request_json(
            "POST",
            f"/projects/{project_name}/operation-package",
            files={"file": (f"{project_name}.zip", content, "application/zip")},
            timeout=httpx.Timeout(connect=30.0, read=60.0, write=60.0, pool=30.0),
        )
        return _validate_operation_package_response(
            payload,
            expected_project_name=project_name,
        )

    async def extract_project_zip(
        self,
        content: bytes,
        validation_context: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request_bounded_response(
            "POST",
            "/validate/zip/extract",
            max_bytes=MAX_PROJECT_EXTRACTION_RESPONSE_BYTES,
            size_error_detail="Deployer project extraction response is too large.",
            files={"file": ("project.zip", content, "application/zip")},
            params={
                "validation_context": _json_dumps_compact(validation_context),
                "include_credentials": False,
            },
            timeout=120.0,
        )
        return self._json_object(response)


def _json_dumps_compact(value: dict[str, Any]) -> str:
    """Encode query JSON without whitespace to keep request URLs deterministic."""
    return json.dumps(value, separators=(",", ":"))


def _validate_operation_package_response(
    payload: dict[str, Any],
    *,
    expected_project_name: str,
) -> dict[str, Any]:
    """Fail closed when the Deployer staging response violates its contract."""
    token = payload.get("operation_token")
    project_name = payload.get("project_name")
    raw_expiry = payload.get("expires_at")
    warnings = payload.get("warnings", [])
    if project_name != expected_project_name:
        raise ExternalServiceError(
            "Deployer API operation package project mismatch",
            public_detail="Deployer returned an invalid operation package contract.",
        )
    if not isinstance(token, str) or not _SAFE_OPERATION_TOKEN.fullmatch(token):
        raise ExternalServiceError(
            "Deployer API returned an invalid operation package token",
            public_detail="Deployer returned an invalid operation package contract.",
        )
    if not isinstance(raw_expiry, str):
        raise ExternalServiceError(
            "Deployer API omitted operation package expiry",
            public_detail="Deployer returned an invalid operation package contract.",
        )
    try:
        expires_at = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalServiceError(
            "Deployer API returned an invalid operation package expiry",
            public_detail="Deployer returned an invalid operation package contract.",
        ) from exc
    if expires_at.tzinfo is None or expires_at <= datetime.now(timezone.utc):
        raise ExternalServiceError(
            "Deployer API returned an expired operation package",
            public_detail="Deployer returned an invalid operation package contract.",
        )
    if not isinstance(warnings, list) or not all(
        isinstance(warning, str) for warning in warnings
    ):
        raise ExternalServiceError(
            "Deployer API returned invalid operation package warnings",
            public_detail="Deployer returned an invalid operation package contract.",
        )
    return payload


def _parse_simulator_archive(
    response: httpx.Response,
    *,
    requested_provider: str,
) -> DeployerSimulatorArchive:
    """Validate the complete binary response before it crosses the client boundary."""
    provider = requested_provider.strip().lower()
    if provider == "google":
        provider = "gcp"
    expected_credential_class = _SIMULATOR_CREDENTIAL_CLASSES.get(provider)
    if expected_credential_class is None:
        raise ExternalServiceError(
            "Deployer API simulator provider contract is unsupported",
            public_detail="Simulator provider contract is unsupported.",
        )

    media_type = (
        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    )
    if media_type != "application/zip":
        raise ExternalServiceError(
            "Deployer API returned an invalid simulator media type",
            public_detail="Deployer returned an invalid simulator archive.",
        )
    if response.headers.get("x-twin2multicloud-utility") != "simulator":
        raise ExternalServiceError(
            "Deployer API omitted simulator utility metadata",
            public_detail="Deployer returned incomplete simulator metadata.",
        )
    if response.headers.get("x-twin2multicloud-provider", "").lower() != provider:
        raise ExternalServiceError(
            "Deployer API simulator provider metadata mismatch",
            public_detail="Deployer returned mismatched simulator metadata.",
        )
    credential_class = response.headers.get("x-twin2multicloud-credential-class", "")
    if credential_class != expected_credential_class:
        raise ExternalServiceError(
            "Deployer API simulator credential class mismatch",
            public_detail="Deployer returned mismatched simulator credential metadata.",
        )

    filename = _content_disposition_filename(
        response.headers.get("content-disposition", "")
    )
    content = response.content
    if not content or len(content) > MAX_SIMULATOR_ARCHIVE_BYTES:
        raise ExternalServiceError(
            "Deployer API simulator archive size is invalid",
            public_detail="Deployer returned an invalid simulator archive size.",
        )
    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise ExternalServiceError(
            "Deployer API response is not a valid ZIP archive",
            public_detail="Deployer returned an invalid simulator archive.",
        )
    return DeployerSimulatorArchive(
        content=content,
        filename=filename,
        provider=provider,
        credential_class=credential_class,
    )


def _content_disposition_filename(value: str) -> str:
    match = re.fullmatch(
        r'attachment;\s*filename=(?:"([^"]+)"|([^";]+))',
        value.strip(),
        re.IGNORECASE,
    )
    filename = (match.group(1) or match.group(2)) if match else None
    if not filename or not _SAFE_SIMULATOR_FILENAME.fullmatch(filename):
        raise ExternalServiceError(
            "Deployer API returned an unsafe simulator filename",
            public_detail="Deployer returned an unsafe simulator filename.",
        )
    return filename
