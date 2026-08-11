"""Offline tests for automatic AWS Five-layer v2 image publication."""

from __future__ import annotations

from botocore.exceptions import ClientError

from src.providers.terraform.aws_v2_image_publisher import (
    AwsV2ImagePublisher,
    AwsV2ImageRequest,
    aws_v2_bridge_deployment,
    aws_v2_container_deployment,
    image_requests,
    image_tfvars,
)


def _tfvars() -> dict:
    return {
        "architecture_profile_id": "five-layer-baseline",
        "architecture_profile_version": "2",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "aws",
        "layer_3_archive_provider": "aws",
    }


def _bridge_route(source: str = "aws") -> dict:
    return {
        "source_provider": source,
        "destination_provider": "gcp",
        "execution_kind": "source_event_forwarder",
    }


class _S3:
    def __init__(self):
        self.objects = {}

    def head_object(self, *, Bucket, Key):
        value = self.objects.get((Bucket, Key))
        if value is None:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {"Metadata": value["Metadata"]}

    def put_object(self, **kwargs):
        key = (kwargs["Bucket"], kwargs["Key"])
        if key in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.objects[key] = kwargs


class _CodeBuild:
    def __init__(self):
        self.starts = []

    def start_build(self, **kwargs):
        self.starts.append(kwargs)
        return {"build": {"id": "build-1"}}

    @staticmethod
    def batch_get_builds(*, ids):
        assert ids == ["build-1"]
        return {"builds": [{"buildStatus": "SUCCEEDED"}]}


class _Ecr:
    def __init__(self, *, tag_exists=False, digest_exists=True):
        self.requests = []
        self.tag_exists = tag_exists
        self.digest_exists = digest_exists
        self.tag_requests = 0

    def describe_images(self, **kwargs):
        self.requests.append(kwargs)
        image_id = kwargs["imageIds"][0]
        if "imageDigest" in image_id:
            if self.digest_exists:
                return {"imageDetails": [{"imageDigest": image_id["imageDigest"]}]}
        else:
            self.tag_requests += 1
            if self.tag_exists or self.tag_requests > 1:
                return {"imageDetails": [{"imageDigest": "sha256:" + "a" * 64}]}
        raise ClientError(
            {"Error": {"Code": "ImageNotFoundException"}},
            "DescribeImages",
        )


def test_publisher_uploads_conditional_context_and_returns_digest(tmp_path):
    context = tmp_path / "context.zip"
    context.write_bytes(b"deterministic context")
    s3 = _S3()
    builds = _CodeBuild()
    ecr = _Ecr()
    repository = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/factory-v2"
    publisher = AwsV2ImagePublisher(
        project_path=tmp_path,
        region="eu-central-1",
        source_bucket="build-bucket",
        repository_url=repository,
        repository_name="factory-v2",
        codebuild_project="factory-v2-images",
        s3_client=s3,
        codebuild_client=builds,
        ecr_client=ecr,
        sleep=lambda _seconds: None,
    )

    images = publisher.publish((AwsV2ImageRequest("storage-mover", context),))

    assert images["storage-mover"] == repository + "@sha256:" + "a" * 64
    uploaded = next(iter(s3.objects.values()))
    assert uploaded["IfNoneMatch"] == "*"
    assert uploaded["Metadata"]["sha256"]
    assert builds.starts[0]["sourceLocationOverride"].startswith(
        "build-bucket/contexts/storage-mover-"
    )
    assert ecr.requests[-1]["repositoryName"] == "factory-v2"
    assert publisher.evidence_path.stat().st_mode & 0o077 == 0

    assert publisher.publish((AwsV2ImageRequest("storage-mover", context),)) == images
    assert len(builds.starts) == 1


def test_publisher_reuses_existing_content_tag_without_starting_build(tmp_path):
    context = tmp_path / "context.zip"
    context.write_bytes(b"deterministic context")
    builds = _CodeBuild()
    repository = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/factory-v2"
    publisher = AwsV2ImagePublisher(
        project_path=tmp_path,
        region="eu-central-1",
        source_bucket="build-bucket",
        repository_url=repository,
        repository_name="factory-v2",
        codebuild_project="factory-v2-images",
        s3_client=_S3(),
        codebuild_client=builds,
        ecr_client=_Ecr(tag_exists=True),
        sleep=lambda _seconds: None,
    )

    images = publisher.publish((AwsV2ImageRequest("storage-mover", context),))

    assert images["storage-mover"] == repository + "@sha256:" + "a" * 64
    assert builds.starts == []


def test_selection_and_tfvars_are_bounded_to_graph_selected_images(tmp_path):
    assert aws_v2_container_deployment(_tfvars()) is True
    assert (
        aws_v2_container_deployment({**_tfvars(), "architecture_profile_version": "1"})
        is False
    )
    image = (
        "123456789012.dkr.ecr.eu-central-1.amazonaws.com/factory-v2@sha256:" + "b" * 64
    )
    assert image_tfvars({"storage-mover": image}, _tfvars()) == {
        "aws_v2_storage_mover_image": image
    }

    bridge_only = {
        **_tfvars(),
        "layer_3_hot_provider": "gcp",
        "layer_3_cold_provider": "gcp",
        "layer_3_archive_provider": "gcp",
        "resolved_cross_cloud_routes": [_bridge_route()],
    }
    bridge_context = tmp_path / ".build" / "aws" / "five-layer-v2-bridge.zip"
    bridge_context.parent.mkdir(parents=True)
    bridge_context.write_bytes(b"bridge")

    assert aws_v2_bridge_deployment(bridge_only) is True
    assert image_requests(tmp_path, bridge_only) == (
        AwsV2ImageRequest("bridge", bridge_context),
    )
    assert image_tfvars({"bridge": image}, bridge_only) == {
        "aws_v2_bridge_image": image
    }

    inbound_only = {
        **bridge_only,
        "resolved_cross_cloud_routes": [_bridge_route("azure")],
    }
    assert aws_v2_bridge_deployment(inbound_only) is False
    assert aws_v2_container_deployment(inbound_only) is False
    assert image_requests(tmp_path, inbound_only) == ()

    inherited_six_layer = {
        **bridge_only,
        "architecture_profile_id": "six-layer-eventing",
        "architecture_profile_version": "1",
    }
    assert aws_v2_bridge_deployment(inherited_six_layer) is True
    assert image_requests(tmp_path, inherited_six_layer) == (
        AwsV2ImageRequest("bridge", bridge_context),
    )


def test_storage_and_bridge_images_are_both_required_when_selected(tmp_path):
    values = {**_tfvars(), "resolved_cross_cloud_routes": [_bridge_route()]}
    build_root = tmp_path / ".build" / "aws"
    build_root.mkdir(parents=True)
    storage_context = build_root / "five-layer-v2-storage-mover.zip"
    bridge_context = build_root / "five-layer-v2-bridge.zip"
    storage_context.write_bytes(b"storage")
    bridge_context.write_bytes(b"bridge")

    assert image_requests(tmp_path, values) == (
        AwsV2ImageRequest("storage-mover", storage_context),
        AwsV2ImageRequest("bridge", bridge_context),
    )
    image = (
        "123456789012.dkr.ecr.eu-central-1.amazonaws.com/factory-v2@sha256:"
        + "c" * 64
    )
    assert image_tfvars(
        {"storage-mover": image, "bridge": image}, values
    ) == {
        "aws_v2_storage_mover_image": image,
        "aws_v2_bridge_image": image,
    }
