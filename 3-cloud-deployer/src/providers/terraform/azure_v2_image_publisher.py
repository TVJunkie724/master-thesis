"""Content-addressed Azure ACR Task publication for Five-layer v2."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping
from urllib.parse import quote

from azure.identity import ClientSecretCredential
import requests

from src.core.secure_files import atomic_write_private_bytes


TASK_API_VERSION = "2025-03-01-preview"
UPLOAD_API_VERSION = "2019-04-01"
_DIGEST_REF = re.compile(
    r"^[a-z0-9]+\.azurecr\.io/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$"
)
_EVIDENCE_VERSION = "azure-v2-published-images.v1"


@dataclass(frozen=True, slots=True)
class AzureV2ImageRequest:
    name: str
    context: Path


def azure_v2_container_deployment(tfvars: Mapping[str, Any]) -> bool:
    if (
        tfvars.get("architecture_profile_id") != "five-layer-baseline"
        or str(tfvars.get("architecture_profile_version")) != "2"
    ):
        return False
    return tfvars.get("layer_3_hot_provider") == "azure" or (
        tfvars.get("layer_3_cold_provider") == "azure"
        and tfvars.get("layer_3_archive_provider") != "azure"
    )


def image_requests(
    project_path: Path, tfvars: Mapping[str, Any]
) -> tuple[AzureV2ImageRequest, ...]:
    if not azure_v2_container_deployment(tfvars):
        return ()
    context = (
        Path(project_path)
        / ".build"
        / "azure"
        / "five-layer-v2-storage-mover.tar.gz"
    )
    if not context.is_file() or context.is_symlink():
        raise ValueError("Azure storage-mover image context is unavailable")
    return (AzureV2ImageRequest("storage-mover", context),)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AzureV2ImagePublisher:
    """Upload deterministic contexts and resolve ACR Task output digests."""

    def __init__(
        self,
        *,
        project_path: Path,
        subscription_id: str,
        resource_group: str,
        location: str,
        registry_name: str,
        login_server: str,
        credential: Any,
        transport: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.project_path = Path(project_path)
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.location = location
        self.registry_name = registry_name
        self.login_server = login_server
        self.credential = credential
        self.transport = transport or requests.Session()
        self.sleep = sleep
        self.registry_root = (
            "https://management.azure.com/subscriptions/"
            f"{quote(subscription_id, safe='')}/resourceGroups/"
            f"{quote(resource_group, safe='')}/providers/"
            "Microsoft.ContainerRegistry/registries/"
            f"{quote(registry_name, safe='')}"
        )
        self.evidence_path = (
            self.project_path / ".build" / "azure" / "published-images.json"
        )

    @classmethod
    def from_tfvars_and_outputs(
        cls,
        *,
        project_path: Path,
        tfvars: Mapping[str, Any],
        outputs: Mapping[str, Any],
    ) -> "AzureV2ImagePublisher":
        credential_values = {
            "subscription_id": tfvars.get("azure_subscription_id"),
            "tenant_id": tfvars.get("azure_tenant_id"),
            "client_id": tfvars.get("azure_client_id"),
            "client_secret": tfvars.get("azure_client_secret"),
        }
        if not all(
            isinstance(value, str) and value for value in credential_values.values()
        ):
            raise ValueError("Azure image publication requires deployment credentials")
        required = {
            "resource_group": outputs.get("azure_v2_resource_group_name"),
            "location": outputs.get("azure_v2_location"),
            "registry_name": outputs.get("azure_v2_acr_name"),
            "login_server": outputs.get("azure_v2_acr_login_server"),
        }
        if not all(isinstance(value, str) and value for value in required.values()):
            raise ValueError("Azure image foundation outputs are incomplete")
        credential = ClientSecretCredential(
            tenant_id=str(credential_values["tenant_id"]),
            client_id=str(credential_values["client_id"]),
            client_secret=str(credential_values["client_secret"]),
        )
        return cls(
            project_path=project_path,
            subscription_id=str(credential_values["subscription_id"]),
            credential=credential,
            **required,
        )

    def _headers(self) -> dict[str, str]:
        token = self.credential.get_token(
            "https://management.azure.com/.default"
        ).token
        return {"authorization": f"Bearer {token}", "content-type": "application/json"}

    @staticmethod
    def _payload(response: Any) -> dict[str, Any]:
        try:
            value = response.json()
        except (ValueError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _error_code(payload: Mapping[str, Any]) -> str:
        error = payload.get("error")
        return str(error.get("code", "")) if isinstance(error, Mapping) else ""

    def _arm(
        self,
        method: str,
        url: str,
        *,
        expected: set[int],
        body: Mapping[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        response = self.transport.request(
            method,
            url,
            headers=self._headers(),
            json=dict(body) if body is not None else None,
            timeout=60,
        )
        payload = self._payload(response)
        if response.status_code not in expected:
            if self._error_code(payload) == "TasksOperationsNotAllowed":
                raise RuntimeError("AZURE_ACR_TASKS_NOT_AVAILABLE_FOR_SUBSCRIPTION")
            raise RuntimeError("Azure ACR Task operation failed")
        return response.status_code, payload

    def _task_run_url(self, name: str) -> str:
        return (
            f"{self.registry_root}/taskRuns/{quote(name, safe='')}"
            f"?api-version={TASK_API_VERSION}"
        )

    @staticmethod
    def _run_name(request: AzureV2ImageRequest) -> str:
        return f"t2mc-{request.name}-{_digest(request.context)[:16]}"

    def _get_run(self, request: AzureV2ImageRequest) -> dict[str, Any] | None:
        status, payload = self._arm(
            "GET",
            self._task_run_url(self._run_name(request)),
            expected={200, 404},
        )
        return None if status == 404 else payload

    def _image_from_run(
        self, request: AzureV2ImageRequest, run: Mapping[str, Any]
    ) -> str | None:
        properties = run.get("properties")
        if not isinstance(properties, Mapping):
            return None
        result = properties.get("runResult")
        result_properties = (
            result.get("properties") if isinstance(result, Mapping) else None
        )
        if not isinstance(result_properties, Mapping):
            return None
        images = result_properties.get("outputImages")
        if not isinstance(images, list):
            return None
        expected_repository = request.name
        expected_tag = _digest(request.context)[:20]
        match = next(
            (
                item
                for item in images
                if isinstance(item, Mapping)
                and item.get("registry") == self.login_server
                and item.get("repository") == expected_repository
                and item.get("tag") == expected_tag
            ),
            None,
        )
        digest = match.get("digest") if isinstance(match, Mapping) else None
        reference = f"{self.login_server}/{expected_repository}@{digest}"
        return (
            reference
            if isinstance(digest, str) and _DIGEST_REF.fullmatch(reference)
            else None
        )

    @staticmethod
    def _run_status(run: Mapping[str, Any]) -> str:
        properties = run.get("properties")
        if not isinstance(properties, Mapping):
            return ""
        result = properties.get("runResult")
        result_properties = (
            result.get("properties") if isinstance(result, Mapping) else None
        )
        if isinstance(result_properties, Mapping) and result_properties.get("status"):
            return str(result_properties["status"])
        return str(properties.get("provisioningState", ""))

    def _wait_for_run(self, request: AzureV2ImageRequest) -> str:
        for _ in range(600):
            run = self._get_run(request)
            if run is None:
                raise RuntimeError("Azure ACR Task run disappeared")
            status = self._run_status(run)
            if status == "Succeeded":
                image = self._image_from_run(request, run)
                if image is None:
                    raise RuntimeError("Azure ACR Task returned no image digest")
                return image
            if status in {"Failed", "Canceled", "Error", "Timeout"}:
                raise RuntimeError("Azure ACR Task image publication failed")
            self.sleep(2)
        raise RuntimeError("Azure ACR Task image publication timed out")

    def _delete_run(self, request: AzureV2ImageRequest) -> None:
        self._arm(
            "DELETE",
            self._task_run_url(self._run_name(request)),
            expected={200, 202, 204},
        )
        for _ in range(60):
            if self._get_run(request) is None:
                return
            self.sleep(2)
        raise RuntimeError("Azure ACR Task run deletion timed out")

    def _cached(
        self, requests_: tuple[AzureV2ImageRequest, ...]
    ) -> dict[str, str] | None:
        if not self.evidence_path.is_file() or self.evidence_path.is_symlink():
            return None
        try:
            value = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict):
            return None
        contexts = {item.name: _digest(item.context) for item in requests_}
        images = value.get("images")
        if (
            value.get("schema_version") != _EVIDENCE_VERSION
            or value.get("contexts") != contexts
            or not isinstance(images, dict)
            or set(images) != set(contexts)
        ):
            return None
        verified: dict[str, str] = {}
        for request in requests_:
            run = self._get_run(request)
            image = self._image_from_run(request, run or {})
            if image is None or image != images.get(request.name):
                return None
            verified[request.name] = image
        return verified

    def publish(
        self, requests_: tuple[AzureV2ImageRequest, ...]
    ) -> dict[str, str]:
        cached = self._cached(requests_)
        if cached is not None:
            return cached
        images = {item.name: self._publish_one(item) for item in requests_}
        payload = {
            "schema_version": _EVIDENCE_VERSION,
            "subscription_id": self.subscription_id,
            "contexts": {item.name: _digest(item.context) for item in requests_},
            "images": images,
        }
        atomic_write_private_bytes(
            self.evidence_path,
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(),
        )
        return images

    def _publish_one(self, request: AzureV2ImageRequest) -> str:
        existing = self._get_run(request)
        if existing is not None:
            status = self._run_status(existing)
            if status == "Succeeded":
                image = self._image_from_run(request, existing)
                if image is not None:
                    return image
            elif status not in {"Failed", "Canceled", "Error", "Timeout"}:
                return self._wait_for_run(request)
            self._delete_run(request)

        _, upload = self._arm(
            "POST",
            f"{self.registry_root}/listBuildSourceUploadUrl"
            f"?api-version={UPLOAD_API_VERSION}",
            expected={200},
        )
        upload_url = upload.get("uploadUrl")
        relative_path = upload.get("relativePath")
        if not all(isinstance(value, str) and value for value in (upload_url, relative_path)):
            raise RuntimeError("Azure ACR Task source upload is unavailable")
        response = self.transport.request(
            "PUT",
            upload_url,
            headers={
                "x-ms-blob-type": "BlockBlob",
                "content-type": "application/gzip",
            },
            data=request.context.read_bytes(),
            timeout=120,
        )
        if response.status_code not in {200, 201}:
            raise RuntimeError("Azure ACR Task source upload failed")

        context_digest = _digest(request.context)
        tag = context_digest[:20]
        body = {
            "location": self.location,
            "properties": {
                "forceUpdateTag": context_digest,
                "runRequest": {
                    "type": "DockerBuildRequest",
                    "sourceLocation": relative_path,
                    "dockerFilePath": "Dockerfile",
                    "imageNames": [f"{self.login_server}/{request.name}:{tag}"],
                    "isPushEnabled": True,
                    "noCache": False,
                    "platform": {"os": "Linux", "architecture": "amd64"},
                    "agentConfiguration": {"cpu": 2},
                    "timeout": 1200,
                },
            },
        }
        self._arm(
            "PUT",
            self._task_run_url(self._run_name(request)),
            expected={200, 201, 202},
            body=body,
        )
        return self._wait_for_run(request)


def image_tfvars(
    images: Mapping[str, str], tfvars: Mapping[str, Any]
) -> dict[str, str]:
    if not azure_v2_container_deployment(tfvars):
        return {}
    image = images.get("storage-mover", "")
    if not image:
        raise RuntimeError("Azure Five-layer v2 image publication is incomplete")
    return {"azure_v2_storage_mover_image": image}


__all__ = [
    "AzureV2ImagePublisher",
    "AzureV2ImageRequest",
    "azure_v2_container_deployment",
    "image_requests",
    "image_tfvars",
]
