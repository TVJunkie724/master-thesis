"""Automatic content-addressed GCP image publication for Five-layer v2.

The publisher runs only after Terraform has created the deployment Artifact
Registry, build identity, and short-lived source bucket. It never requires a
local Docker socket and never places registry credentials in project files.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping

import google.auth
from google.cloud import storage
from googleapiclient.discovery import build as build_google_api

from src.core.secure_files import atomic_write_private_bytes


DOCKER_BUILDER = (
    "gcr.io/cloud-builders/docker@"
    "sha256:f8b08c609fdc392ee6827ff3e1725e4980f7d96bde9f76f4695086405c96c147"
)
_DIGEST_REF = re.compile(r"^[a-z0-9.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$")
_ZERO_DIGEST = "sha256:" + "0" * 64
_EVIDENCE_VERSION = "gcp-v2-published-images.v1"


@dataclass(frozen=True, slots=True)
class GcpV2ImageRequest:
    name: str
    context: Path
    dockerfile: str = "Dockerfile"
    build_args: tuple[str, ...] = ()


def gcp_v2_container_deployment(tfvars: Mapping[str, Any]) -> bool:
    profile = (
        tfvars.get("architecture_profile_id"),
        str(tfvars.get("architecture_profile_version")),
    )
    if profile not in {
        ("five-layer-baseline", "2"),
        ("six-layer-eventing", "1"),
    }:
        return False
    return any(
        tfvars.get(key) == "google"
        for key in (
            "layer_1_provider",
            "layer_2_provider",
            "layer_3_hot_provider",
            "layer_3_cold_provider",
            "layer_4_provider",
            "layer_5_provider",
            "event_layer_provider",
        )
    )


def _gcp_v2_platform_deployment(tfvars: Mapping[str, Any]) -> bool:
    phase8_profile = (
        tfvars.get("architecture_profile_id"),
        str(tfvars.get("architecture_profile_version")),
    ) in {
        ("five-layer-baseline", "2"),
        ("six-layer-eventing", "1"),
    }
    routes = tfvars.get("resolved_cross_cloud_routes")
    bridge_or_landing = phase8_profile and isinstance(routes, list) and any(
        isinstance(route, Mapping)
        and route.get("execution_kind") == "source_event_forwarder"
        and "gcp"
        in {
            route.get("source_provider"),
            route.get("destination_provider"),
        }
        for route in routes
    )
    return bridge_or_landing or any(
        tfvars.get(key) == "google"
        for key in (
            "layer_1_provider",
            "layer_2_provider",
            "layer_3_hot_provider",
            "layer_3_cold_provider",
            "layer_4_provider",
            "layer_5_provider",
        )
    )


def _gcp_eventing_deployment(tfvars: Mapping[str, Any]) -> bool:
    return (
        tfvars.get("architecture_profile_id") == "six-layer-eventing"
        and str(tfvars.get("architecture_profile_version")) == "1"
        and tfvars.get("event_layer_provider") == "google"
    )


def _normalized_name(value: str) -> str:
    return value.lower().replace("_", "-")[:24]


def placeholder_image_tfvars(tfvars: Mapping[str, Any]) -> dict[str, Any]:
    """Return syntactically valid refs used only by the foundation target apply."""

    if not gcp_v2_container_deployment(tfvars):
        return {}
    prefix = (
        f"{tfvars['gcp_region']}-docker.pkg.dev/{tfvars['gcp_project_id']}/"
        f"{_normalized_name(str(tfvars['digital_twin_name']))}-v2/"
    )
    return {
        "gcp_v2_platform_image": f"{prefix}platform@{_ZERO_DIGEST}",
        "gcp_v2_processor_extension_image": f"{prefix}processor-extension@{_ZERO_DIGEST}",
        "gcp_v2_storage_mover_image": f"{prefix}storage-mover@{_ZERO_DIGEST}",
        "gcp_v2_grafana_image": f"{prefix}grafana@{_ZERO_DIGEST}",
        "gcp_event_runtime_image": f"{prefix}event-runtime@{_ZERO_DIGEST}",
        "gcp_v2_kubernetes_stage_enabled": False,
    }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_requests(project_path: Path, tfvars: Mapping[str, Any]) -> tuple[GcpV2ImageRequest, ...]:
    platform = Path(project_path) / ".build" / "gcp" / "five-layer-v2.tar.gz"
    requests: list[GcpV2ImageRequest] = []
    if _gcp_v2_platform_deployment(tfvars):
        requests.append(GcpV2ImageRequest("platform", platform))
    if _gcp_eventing_deployment(tfvars):
        requests.append(
            GcpV2ImageRequest(
                "event-runtime",
                Path(project_path) / ".build" / "gcp" / "six-layer-eventing.tar.gz",
            )
        )
    if tfvars.get("layer_2_provider") == "google":
        requests.append(
            GcpV2ImageRequest(
                "processor-extension",
                Path(project_path) / ".build" / "gcp" / "processor-extension.tar.gz",
            )
        )
    if (
        tfvars.get("layer_3_hot_provider") == "google"
        or (
            tfvars.get("layer_3_cold_provider") == "google"
            and tfvars.get("layer_3_archive_provider") != "google"
        )
    ):
        requests.append(
            GcpV2ImageRequest(
                "storage-mover",
                platform,
                dockerfile="storage-mover/Dockerfile",
            )
        )
    if tfvars.get("layer_5_provider") == "google":
        requests.append(
            GcpV2ImageRequest(
                "grafana",
                platform,
                dockerfile="grafana/Dockerfile",
                build_args=("TARGETARCH=amd64",),
            )
        )
    for request in requests:
        if not request.context.is_file() or request.context.is_symlink():
            raise ValueError(f"GCP image context is unavailable: {request.name}")
    return tuple(requests)


class GcpV2ImagePublisher:
    """Upload deterministic contexts and resolve Cloud Build image digests."""

    def __init__(
        self,
        *,
        project_path: Path,
        project_id: str,
        region: str,
        source_bucket: str,
        registry_prefix: str,
        build_service_account: str,
        credentials: Any,
        storage_client: Any | None = None,
        build_service: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.project_path = Path(project_path)
        self.project_id = project_id
        self.region = region
        self.source_bucket = source_bucket
        self.registry_prefix = registry_prefix
        self.build_service_account = build_service_account
        self.credentials = credentials
        self.storage_client = storage_client or storage.Client(
            project=project_id,
            credentials=credentials,
        )
        self.build_service = build_service or build_google_api(
            "cloudbuild",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )
        self.sleep = sleep
        self.evidence_path = (
            self.project_path / ".build" / "gcp" / "published-images.json"
        )

    @classmethod
    def from_tfvars_and_outputs(
        cls,
        *,
        project_path: Path,
        tfvars: Mapping[str, Any],
        outputs: Mapping[str, Any],
    ) -> "GcpV2ImagePublisher":
        raw_credentials = tfvars.get("gcp_credentials_json")
        if not isinstance(raw_credentials, str) or not raw_credentials:
            raise ValueError("GCP image publication requires deployment credentials")
        try:
            credential_info = json.loads(raw_credentials)
        except json.JSONDecodeError as exc:
            raise ValueError("GCP deployment credentials are invalid") from exc
        credentials, _ = google.auth.load_credentials_from_dict(
            credential_info,
            scopes=("https://www.googleapis.com/auth/cloud-platform",),
        )
        required = {
            "source_bucket": outputs.get("gcp_v2_build_source_bucket"),
            "registry_prefix": outputs.get("gcp_v2_registry_prefix"),
            "build_service_account": outputs.get("gcp_v2_build_service_account"),
        }
        if not all(isinstance(value, str) and value for value in required.values()):
            raise ValueError("GCP image foundation outputs are incomplete")
        return cls(
            project_path=project_path,
            project_id=str(tfvars["gcp_project_id"]),
            region=str(tfvars["gcp_region"]),
            credentials=credentials,
            **required,
        )

    def _cached(self, requests: tuple[GcpV2ImageRequest, ...]) -> dict[str, str] | None:
        if not self.evidence_path.is_file() or self.evidence_path.is_symlink():
            return None
        try:
            value = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        expected_contexts = {item.name: _digest(item.context) for item in requests}
        images = value.get("images") if isinstance(value, dict) else None
        if (
            value.get("schema_version") != _EVIDENCE_VERSION
            or value.get("contexts") != expected_contexts
            or not isinstance(images, dict)
            or set(images) != set(expected_contexts)
            or not all(
                isinstance(ref, str)
                and _DIGEST_REF.fullmatch(ref)
                and ref.startswith(self.registry_prefix)
                for ref in images.values()
            )
        ):
            return None
        return dict(images)

    def publish(self, requests: tuple[GcpV2ImageRequest, ...]) -> dict[str, str]:
        cached = self._cached(requests)
        if cached is not None:
            return cached
        images = {item.name: self._publish_one(item) for item in requests}
        payload = {
            "schema_version": _EVIDENCE_VERSION,
            "project_id": self.project_id,
            "region": self.region,
            "contexts": {item.name: _digest(item.context) for item in requests},
            "images": images,
        }
        atomic_write_private_bytes(
            self.evidence_path,
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(),
        )
        return images

    def _publish_one(self, request: GcpV2ImageRequest) -> str:
        context_digest = _digest(request.context)
        tag = f"{self.registry_prefix}{request.name}:{context_digest[:20]}"
        object_name = f"contexts/{request.name}-{context_digest}.tar.gz"
        blob = self.storage_client.bucket(self.source_bucket).blob(object_name)
        if not blob.exists():
            blob.metadata = {"sha256": context_digest, "schema": _EVIDENCE_VERSION}
            blob.upload_from_filename(
                str(request.context),
                content_type="application/gzip",
                if_generation_match=0,
            )
        blob.reload()
        generation = str(blob.generation)
        args = ["build", "--platform=linux/amd64", "-f", request.dockerfile]
        for value in request.build_args:
            args.extend(("--build-arg", value))
        args.extend(("-t", tag, "."))
        body = {
            "source": {
                "storageSource": {
                    "bucket": self.source_bucket,
                    "object": object_name,
                    "generation": generation,
                }
            },
            "steps": [
                {"name": DOCKER_BUILDER, "args": args},
                {"name": DOCKER_BUILDER, "args": ["push", tag]},
            ],
            "images": [tag],
            "serviceAccount": (
                f"projects/{self.project_id}/serviceAccounts/"
                f"{self.build_service_account}"
            ),
            "options": {
                "logging": "CLOUD_LOGGING_ONLY",
                "machineType": "E2_HIGHCPU_8",
            },
            "timeout": "1200s",
            "tags": ["twin2multicloud", "five-layer-v2", request.name],
        }
        operation = (
            self.build_service.projects()
            .locations()
            .builds()
            .create(
                parent=f"projects/{self.project_id}/locations/{self.region}",
                body=body,
            )
            .execute()
        )
        operation_name = operation.get("name")
        if not isinstance(operation_name, str) or not operation_name:
            raise RuntimeError("Cloud Build did not return an operation")
        while not operation.get("done"):
            self.sleep(2)
            operation = (
                self.build_service.projects()
                .locations()
                .operations()
                .get(name=operation_name)
                .execute()
            )
        if operation.get("error"):
            raise RuntimeError(f"Cloud Build failed for {request.name}")
        built = operation.get("response", {}).get("results", {}).get("images", [])
        match = next((item for item in built if item.get("name") == tag), None)
        digest = match.get("digest") if isinstance(match, dict) else None
        result = f"{tag.rsplit(':', 1)[0]}@{digest}"
        if not isinstance(digest, str) or not _DIGEST_REF.fullmatch(result):
            raise RuntimeError(f"Cloud Build returned no image digest for {request.name}")
        return result


def image_tfvars(images: Mapping[str, str], tfvars: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "gcp_v2_kubernetes_stage_enabled": False,
    }
    if _gcp_v2_platform_deployment(tfvars):
        result["gcp_v2_platform_image"] = images.get("platform", "")
    if _gcp_eventing_deployment(tfvars):
        result["gcp_event_runtime_image"] = images.get("event-runtime", "")
    if tfvars.get("layer_2_provider") == "google":
        result["gcp_v2_processor_extension_image"] = images.get(
            "processor-extension", ""
        )
    if (
        tfvars.get("layer_3_hot_provider") == "google"
        or (
            tfvars.get("layer_3_cold_provider") == "google"
            and tfvars.get("layer_3_archive_provider") != "google"
        )
    ):
        result["gcp_v2_storage_mover_image"] = images.get("storage-mover", "")
    if tfvars.get("layer_5_provider") == "google":
        result["gcp_v2_grafana_image"] = images.get("grafana", "")
    if any(not value for key, value in result.items() if key.endswith("_image")):
        raise RuntimeError("GCP Five-layer v2 image publication is incomplete")
    return result


__all__ = [
    "GcpV2ImagePublisher",
    "GcpV2ImageRequest",
    "gcp_v2_container_deployment",
    "image_requests",
    "image_tfvars",
    "placeholder_image_tfvars",
]
