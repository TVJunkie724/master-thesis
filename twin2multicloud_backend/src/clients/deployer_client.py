"""Typed Deployer API client."""

import io
import json
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
MAX_REQUIREMENTS_RESPONSE_BYTES = 2 * 1024 * 1024
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
            f"/permissions/preflight/{provider}",
            json=credentials,
            timeout=30.0,
        )

    async def validate_config_file(
        self,
        endpoint: str,
        files: dict[str, tuple[str, bytes, str]],
        *,
        provider: str | None = None,
        context_params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        params = dict(context_params or {})
        if provider:
            params["provider"] = provider
        return await self._request_json(
            "POST",
            f"/validate/{endpoint}",
            params=params or None,
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

    async def rotate_gcp_grafana_viewer_credential(
        self,
        project_name: str,
        operation_token: str,
    ) -> dict[str, Any]:
        """Perform one explicit, non-retried GCP Viewer rotation."""
        return await self._request_json(
            "POST",
            "/infrastructure/deployment-access/l5/credentials:rotate",
            params={"project_name": project_name},
            headers={"X-Operation-Package": operation_token},
            timeout=240.0,
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

    async def inspect_deployment_requirements(
        self,
        project_name: str,
        content: bytes,
    ) -> dict[str, Any]:
        """Resolve the package graph without staging or provider mutation."""

        response = await self._request_bounded_response(
            "POST",
            "/validate/deployment-requirements",
            max_bytes=MAX_REQUIREMENTS_RESPONSE_BYTES,
            size_error_detail="Deployer requirement inspection response is too large.",
            params={"project_name": project_name},
            files={"file": (f"{project_name}.zip", content, "application/zip")},
            timeout=httpx.Timeout(connect=30.0, read=60.0, write=60.0, pool=30.0),
        )
        return _validate_requirements_inspection_response(
            self._json_object(response),
            expected_project_name=project_name,
        )

    async def prepare_deployment_account(
        self,
        project_name: str,
        content: bytes,
        *,
        expected_plan_digest: str,
    ) -> dict[str, Any]:
        """Apply one explicitly confirmed, digest-bound account preparation plan."""

        response = await self._request_bounded_response(
            "POST",
            "/infrastructure/account-preparation",
            max_bytes=MAX_REQUIREMENTS_RESPONSE_BYTES,
            size_error_detail="Deployer account preparation response is too large.",
            params={"project_name": project_name},
            data={
                "expected_plan_digest": expected_plan_digest,
                "confirmed": "true",
            },
            files={"file": (f"{project_name}.zip", content, "application/zip")},
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=30.0),
        )
        return _validate_account_preparation_response(
            self._json_object(response),
            expected_project_name=project_name,
            expected_plan_digest=expected_plan_digest,
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
    graph_evidence = payload.get("graph_evidence")
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
    if not isinstance(graph_evidence, dict) or not _graph_evidence_is_valid(
        graph_evidence
    ):
        raise ExternalServiceError(
            "Deployer API omitted validated deployment graph evidence",
            public_detail="Deployer returned an invalid operation package contract.",
        )
    return payload


def _graph_evidence_is_valid(graph_evidence: object) -> bool:
    required_graph_fields = {
        "graph_schema_version",
        "graph_id",
        "calculation_run_id",
        "graph_digest",
        "architecture_digest",
        "profile_id",
        "profile_version",
        "catalog_id",
        "catalog_version",
        "catalog_digest",
        "specification_digest",
        "package_selection_digest",
        "requirements_digest",
        "node_count",
        "edge_count",
        "binding_count",
        "requirement_count",
        "requirement_types",
        "required_providers",
        "stage_ids",
    }
    digest_pattern = re.compile(r"^sha256:[0-9a-f]{64}$")
    return not (
        not isinstance(graph_evidence, dict)
        or set(graph_evidence) != required_graph_fields
        or graph_evidence.get("graph_schema_version") != "resolved-deployment-graph.v1"
        or not all(
            isinstance(graph_evidence.get(field), str)
            and digest_pattern.fullmatch(graph_evidence[field]) is not None
            for field in (
                "graph_digest",
                "architecture_digest",
                "catalog_digest",
                "specification_digest",
                "package_selection_digest",
                "requirements_digest",
            )
        )
        or not isinstance(graph_evidence.get("calculation_run_id"), str)
        or not graph_evidence["calculation_run_id"]
        or not all(
            isinstance(graph_evidence.get(field), str)
            and bool(graph_evidence[field])
            for field in (
                "graph_id",
                "profile_id",
                "profile_version",
                "catalog_id",
                "catalog_version",
            )
        )
        or not _bounded_graph_count(graph_evidence.get("node_count"), 1, 256)
        or not _bounded_graph_count(graph_evidence.get("edge_count"), 0, 512)
        or not _bounded_graph_count(graph_evidence.get("binding_count"), 1, 2048)
        or not _bounded_graph_count(graph_evidence.get("requirement_count"), 1, 4096)
        or not _bounded_string_list(
            graph_evidence.get("requirement_types"),
            allowed={
                "account_capability",
                "access_prerequisite",
                "api",
                "control_plane",
                "permission",
                "provider_scope",
                "quota",
                "region",
                "resource_provider",
                "runtime_identity",
                "verification_probe",
                "workload_identity",
            },
        )
        or not _bounded_string_list(
            graph_evidence.get("required_providers"),
            allowed={"aws", "azure", "gcp"},
        )
        or graph_evidence.get("stage_ids")
        != ["package", "preplan", "terraform", "postapply"]
    )


def _validate_requirements_inspection_response(
    payload: dict[str, Any],
    *,
    expected_project_name: str,
) -> dict[str, Any]:
    """Fail closed on non-canonical or unbound graph requirement evidence."""

    if set(payload) != {
        "project_name",
        "warnings",
        "graph_evidence",
        "requirements",
        "preparation_plan",
    }:
        raise _invalid_requirements_response()
    if payload.get("project_name") != expected_project_name:
        raise _invalid_requirements_response()
    warnings = payload.get("warnings")
    if (
        not isinstance(warnings, list)
        or len(warnings) > 100
        or not all(isinstance(item, str) and len(item) <= 2_000 for item in warnings)
    ):
        raise _invalid_requirements_response()
    graph_evidence = payload.get("graph_evidence")
    if not isinstance(graph_evidence, dict) or not _graph_evidence_is_valid(
        graph_evidence
    ):
        raise _invalid_requirements_response()
    requirements = payload.get("requirements")
    if (
        not isinstance(requirements, list)
        or len(requirements) != graph_evidence["requirement_count"]
        or not requirements
        or not all(_graph_requirement_is_valid(item) for item in requirements)
        or [item["requirement_id"] for item in requirements]
        != sorted(item["requirement_id"] for item in requirements)
        or sorted({item["provider"] for item in requirements})
        != graph_evidence["required_providers"]
        or sorted({item["requirement_type"] for item in requirements})
        != graph_evidence["requirement_types"]
    ):
        raise _invalid_requirements_response()
    if not _account_preparation_plan_is_valid(
        payload.get("preparation_plan"),
        graph_evidence,
    ):
        raise _invalid_requirements_response()
    return payload


def _account_preparation_plan_is_valid(
    value: object,
    graph_evidence: dict[str, Any],
) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "graph_digest",
        "requirements_digest",
        "plan_digest",
        "actions",
        "manual_requirements",
    }:
        return False
    digest_pattern = re.compile(r"^sha256:[0-9a-f]{64}$")
    if (
        value.get("schema_version") != "graph-account-preparation.v1"
        or value.get("graph_digest") != graph_evidence["graph_digest"]
        or value.get("requirements_digest") != graph_evidence["requirements_digest"]
        or not isinstance(value.get("plan_digest"), str)
        or digest_pattern.fullmatch(value["plan_digest"]) is None
    ):
        return False
    actions = value.get("actions")
    manual = value.get("manual_requirements")
    return (
        isinstance(actions, list)
        and len(actions) <= 4096
        and all(_preparation_action_is_valid(item) for item in actions)
        and [item["action_id"] for item in actions]
        == sorted(item["action_id"] for item in actions)
        and isinstance(manual, list)
        and len(manual) <= 4096
        and all(_manual_requirement_is_valid(item) for item in manual)
        and [item["requirement_id"] for item in manual]
        == sorted(item["requirement_id"] for item in manual)
    )


def _preparation_action_is_valid(value: object) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value)
        == {
            "action_id",
            "provider",
            "action_type",
            "capability_id",
            "scope",
            "requirement_ids",
            "reason",
            "persistent_after_destroy",
            "destructive",
        }
        and value.get("provider") in {"azure", "gcp"}
        and value.get("action_type")
        in {"register_resource_provider", "enable_project_api"}
        and all(
            isinstance(value.get(field), str) and 0 < len(value[field]) <= 2_000
            for field in ("action_id", "capability_id", "scope", "reason")
        )
        and isinstance(value.get("requirement_ids"), list)
        and value["requirement_ids"]
        and all(isinstance(item, str) for item in value["requirement_ids"])
        and value.get("persistent_after_destroy") is True
        and value.get("destructive") is False
    )


def _manual_requirement_is_valid(value: object) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == {"requirement_id", "provider", "capability_id", "reason"}
        and value.get("provider") in {"aws", "azure", "gcp"}
        and all(
            isinstance(value.get(field), str) and 0 < len(value[field]) <= 2_000
            for field in ("requirement_id", "capability_id", "reason")
        )
    )


def _validate_account_preparation_response(
    payload: dict[str, Any],
    *,
    expected_project_name: str,
    expected_plan_digest: str,
) -> dict[str, Any]:
    if set(payload) != {
        "project_name",
        "plan_digest",
        "requirements_digest",
        "status",
        "completed_actions",
        "failed_actions",
        "remaining_actions",
        "retry_safe",
    }:
        raise _invalid_preparation_response()
    digest_pattern = re.compile(r"^sha256:[0-9a-f]{64}$")
    if (
        payload.get("project_name") != expected_project_name
        or payload.get("plan_digest") != expected_plan_digest
        or not isinstance(payload.get("requirements_digest"), str)
        or digest_pattern.fullmatch(payload["requirements_digest"]) is None
        or payload.get("status") not in {"ready", "partial", "failed"}
        or payload.get("retry_safe") is not True
    ):
        raise _invalid_preparation_response()
    for field in ("completed_actions", "failed_actions", "remaining_actions"):
        values = payload.get(field)
        if not isinstance(values, list) or len(values) > 4096:
            raise _invalid_preparation_response()
    if payload["status"] == "ready" and (
        payload["failed_actions"] or payload["remaining_actions"]
    ):
        raise _invalid_preparation_response()
    return payload


def _invalid_preparation_response() -> ExternalServiceError:
    return ExternalServiceError(
        "Deployer API returned invalid account preparation evidence",
        public_detail="Deployer returned an invalid account preparation contract.",
    )


def _graph_requirement_is_valid(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "requirement_id",
        "requirement_type",
        "provider",
        "capability_id",
        "scope",
        "preparation_mode",
        "mandatory",
        "source_node_ids",
        "source_edge_ids",
        "region",
        "attributes",
    }:
        return False
    bounded_strings = ("requirement_id", "requirement_type", "capability_id", "scope")
    if not all(
        isinstance(value.get(field), str) and 0 < len(value[field]) <= 300
        for field in bounded_strings
    ):
        return False
    if value.get("provider") not in {"aws", "azure", "gcp"}:
        return False
    if value.get("preparation_mode") not in {
        "none",
        "confirmed_account",
        "manual_external",
        "terraform",
    }:
        return False
    if value.get("mandatory") is not True:
        return False
    if not isinstance(value.get("region"), str) or len(value["region"]) > 100:
        return False
    if not isinstance(value.get("attributes"), dict):
        return False
    return all(
        isinstance(value.get(field), list)
        and len(value[field]) <= 512
        and value[field] == sorted(set(value[field]))
        and all(isinstance(item, str) and 0 < len(item) <= 300 for item in value[field])
        for field in ("source_node_ids", "source_edge_ids")
    )


def _invalid_requirements_response() -> ExternalServiceError:
    return ExternalServiceError(
        "Deployer API returned invalid deployment requirements",
        public_detail="Deployer returned an invalid requirement inspection contract.",
    )


def _bounded_graph_count(value: object, minimum: int, maximum: int) -> bool:
    """Validate a topology-neutral, bounded graph evidence counter."""

    return (
        not isinstance(value, bool)
        and isinstance(value, int)
        and minimum <= value <= maximum
    )


def _bounded_string_list(value: object, *, allowed: set[str]) -> bool:
    """Validate a deterministic non-empty subset without accepting duplicates."""

    return (
        isinstance(value, list)
        and bool(value)
        and value == sorted(set(value))
        and all(isinstance(item, str) and item in allowed for item in value)
    )


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
