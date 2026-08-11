"""Automatic content-addressed AWS image publication for Five-layer v2."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping

import boto3
from botocore.exceptions import ClientError

from src.core.secure_files import atomic_write_private_bytes


_DIGEST_REF = re.compile(
    r"^[0-9]+\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$"
)
_EVIDENCE_VERSION = "aws-v2-published-images.v1"


@dataclass(frozen=True, slots=True)
class AwsV2ImageRequest:
    name: str
    context: Path


def _five_layer_v2(tfvars: Mapping[str, Any]) -> bool:
    """Return whether the reviewed v2 foundation is selected directly or inherited."""

    return (
        tfvars.get("architecture_profile_id"),
        str(tfvars.get("architecture_profile_version")),
    ) in {
        ("five-layer-baseline", "2"),
        ("six-layer-eventing", "1"),
    }


def aws_v2_storage_mover_deployment(tfvars: Mapping[str, Any]) -> bool:
    if not _five_layer_v2(tfvars):
        return False
    return tfvars.get("layer_3_hot_provider") == "aws" or (
        tfvars.get("layer_3_cold_provider") == "aws"
        and tfvars.get("layer_3_archive_provider") != "aws"
    )


def aws_v2_bridge_deployment(tfvars: Mapping[str, Any]) -> bool:
    if not _five_layer_v2(tfvars):
        return False
    routes = tfvars.get("resolved_cross_cloud_routes")
    return isinstance(routes, list) and any(
        isinstance(route, Mapping)
        and route.get("source_provider") == "aws"
        and route.get("execution_kind") == "source_event_forwarder"
        for route in routes
    )


def aws_v2_container_deployment(tfvars: Mapping[str, Any]) -> bool:
    return aws_v2_storage_mover_deployment(tfvars) or aws_v2_bridge_deployment(tfvars)


def image_requests(
    project_path: Path, tfvars: Mapping[str, Any]
) -> tuple[AwsV2ImageRequest, ...]:
    requests: list[AwsV2ImageRequest] = []
    build_root = Path(project_path) / ".build" / "aws"
    selections = (
        (
            aws_v2_storage_mover_deployment(tfvars),
            "storage-mover",
            build_root / "five-layer-v2-storage-mover.zip",
        ),
        (
            aws_v2_bridge_deployment(tfvars),
            "bridge",
            build_root / "five-layer-v2-bridge.zip",
        ),
    )
    for selected, name, context in selections:
        if not selected:
            continue
        if not context.is_file() or context.is_symlink():
            raise ValueError(f"AWS {name} image context is unavailable")
        requests.append(AwsV2ImageRequest(name, context))
    return tuple(requests)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AwsV2ImagePublisher:
    """Upload deterministic contexts and resolve CodeBuild ECR digests."""

    def __init__(
        self,
        *,
        project_path: Path,
        region: str,
        source_bucket: str,
        repository_url: str,
        repository_name: str,
        codebuild_project: str,
        s3_client: Any,
        codebuild_client: Any,
        ecr_client: Any,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.project_path = Path(project_path)
        self.region = region
        self.source_bucket = source_bucket
        self.repository_url = repository_url
        self.repository_name = repository_name
        self.codebuild_project = codebuild_project
        self.s3 = s3_client
        self.codebuild = codebuild_client
        self.ecr = ecr_client
        self.sleep = sleep
        self.evidence_path = (
            self.project_path / ".build" / "aws" / "published-images.json"
        )

    @classmethod
    def from_tfvars_and_outputs(
        cls,
        *,
        project_path: Path,
        tfvars: Mapping[str, Any],
        outputs: Mapping[str, Any],
    ) -> "AwsV2ImagePublisher":
        access_key = tfvars.get("aws_access_key_id")
        secret_key = tfvars.get("aws_secret_access_key")
        region = tfvars.get("aws_region")
        if not all(
            isinstance(value, str) and value
            for value in (access_key, secret_key, region)
        ):
            raise ValueError("AWS image publication requires deployment credentials")
        required = {
            "source_bucket": outputs.get("aws_v2_build_source_bucket"),
            "repository_url": outputs.get("aws_v2_ecr_repository_url"),
            "repository_name": outputs.get("aws_v2_ecr_repository_name"),
            "codebuild_project": outputs.get("aws_v2_codebuild_project"),
        }
        if not all(isinstance(value, str) and value for value in required.values()):
            raise ValueError("AWS image foundation outputs are incomplete")
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        return cls(
            project_path=project_path,
            region=region,
            s3_client=session.client("s3"),
            codebuild_client=session.client("codebuild"),
            ecr_client=session.client("ecr"),
            **required,
        )

    def _cached(self, requests: tuple[AwsV2ImageRequest, ...]) -> dict[str, str] | None:
        if not self.evidence_path.is_file() or self.evidence_path.is_symlink():
            return None
        try:
            value = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        contexts = {item.name: _digest(item.context) for item in requests}
        images = value.get("images") if isinstance(value, dict) else None
        if (
            value.get("schema_version") != _EVIDENCE_VERSION
            or value.get("contexts") != contexts
            or not isinstance(images, dict)
            or set(images) != set(contexts)
            or not all(
                isinstance(ref, str)
                and _DIGEST_REF.fullmatch(ref)
                and ref.startswith(f"{self.repository_url}@")
                for ref in images.values()
            )
        ):
            return None
        cached = dict(images)
        return cached if all(self._digest_exists(ref) for ref in cached.values()) else None

    def _digest_exists(self, reference: str) -> bool:
        digest = reference.rsplit("@", 1)[-1]
        try:
            details = self.ecr.describe_images(
                repositoryName=self.repository_name,
                imageIds=[{"imageDigest": digest}],
            ).get("imageDetails", [])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ImageNotFoundException":
                return False
            raise
        return len(details) == 1 and details[0].get("imageDigest") == digest

    def _tag_digest(self, tag: str) -> str | None:
        try:
            details = self.ecr.describe_images(
                repositoryName=self.repository_name,
                imageIds=[{"imageTag": tag}],
            ).get("imageDetails", [])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ImageNotFoundException":
                return None
            raise
        digest = details[0].get("imageDigest") if len(details) == 1 else None
        result = f"{self.repository_url}@{digest}"
        if not isinstance(digest, str) or not _DIGEST_REF.fullmatch(result):
            raise RuntimeError("ECR returned an invalid image digest")
        return result

    def publish(self, requests: tuple[AwsV2ImageRequest, ...]) -> dict[str, str]:
        cached = self._cached(requests)
        if cached is not None:
            return cached
        images = {item.name: self._publish_one(item) for item in requests}
        payload = {
            "schema_version": _EVIDENCE_VERSION,
            "region": self.region,
            "contexts": {item.name: _digest(item.context) for item in requests},
            "images": images,
        }
        atomic_write_private_bytes(
            self.evidence_path,
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(),
        )
        return images

    def _publish_one(self, request: AwsV2ImageRequest) -> str:
        context_digest = _digest(request.context)
        object_key = f"contexts/{request.name}-{context_digest}.zip"
        upload_required = False
        try:
            existing = self.s3.head_object(Bucket=self.source_bucket, Key=object_key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise
            upload_required = True
        else:
            if existing.get("Metadata", {}).get("sha256") != context_digest:
                raise RuntimeError("AWS image context checksum conflict")
        if upload_required:
            try:
                self.s3.put_object(
                    Bucket=self.source_bucket,
                    Key=object_key,
                    Body=request.context.read_bytes(),
                    IfNoneMatch="*",
                    Metadata={"sha256": context_digest, "schema": _EVIDENCE_VERSION},
                    ServerSideEncryption="AES256",
                    ContentType="application/zip",
                )
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") not in {
                    "PreconditionFailed",
                    "ConditionalRequestConflict",
                    "412",
                    "409",
                }:
                    raise
                existing = self.s3.head_object(
                    Bucket=self.source_bucket, Key=object_key
                )
                if existing.get("Metadata", {}).get("sha256") != context_digest:
                    raise RuntimeError("AWS image context checksum conflict") from exc
        tag = context_digest[:20]
        published = self._tag_digest(tag)
        if published is not None:
            return published
        build = self.codebuild.start_build(
            projectName=self.codebuild_project,
            sourceLocationOverride=f"{self.source_bucket}/{object_key}",
            environmentVariablesOverride=[
                {
                    "name": "IMAGE_URI",
                    "value": self.repository_url,
                    "type": "PLAINTEXT",
                },
                {"name": "IMAGE_TAG", "value": tag, "type": "PLAINTEXT"},
            ],
        ).get("build", {})
        build_id = build.get("id")
        if not isinstance(build_id, str) or not build_id:
            raise RuntimeError("CodeBuild did not return a build identifier")
        while True:
            values = self.codebuild.batch_get_builds(ids=[build_id]).get("builds", [])
            if len(values) != 1:
                raise RuntimeError("CodeBuild result is unavailable")
            status = values[0].get("buildStatus")
            if status == "SUCCEEDED":
                break
            if status in {"FAILED", "FAULT", "STOPPED", "TIMED_OUT"}:
                raise RuntimeError("CodeBuild image publication failed")
            self.sleep(2)
        result = self._tag_digest(tag)
        if result is None:
            raise RuntimeError("ECR returned no image digest")
        return result


def image_tfvars(
    images: Mapping[str, str], tfvars: Mapping[str, Any]
) -> dict[str, str]:
    expected = {
        name: variable
        for selected, name, variable in (
            (
                aws_v2_storage_mover_deployment(tfvars),
                "storage-mover",
                "aws_v2_storage_mover_image",
            ),
            (
                aws_v2_bridge_deployment(tfvars),
                "bridge",
                "aws_v2_bridge_image",
            ),
        )
        if selected
    }
    if not expected:
        return {}
    if set(images) != set(expected) or any(not images.get(name) for name in expected):
        raise RuntimeError("AWS Five-layer v2 image publication is incomplete")
    return {variable: images[name] for name, variable in expected.items()}


__all__ = [
    "AwsV2ImagePublisher",
    "AwsV2ImageRequest",
    "aws_v2_bridge_deployment",
    "aws_v2_container_deployment",
    "aws_v2_storage_mover_deployment",
    "image_requests",
    "image_tfvars",
]
