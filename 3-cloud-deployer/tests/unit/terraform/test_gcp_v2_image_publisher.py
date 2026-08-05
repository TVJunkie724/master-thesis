"""Offline tests for automatic GCP Five-layer v2 image publication."""

from __future__ import annotations

from src.providers.terraform.gcp_v2_image_publisher import (
    DOCKER_BUILDER,
    GcpV2ImagePublisher,
    GcpV2ImageRequest,
    image_tfvars,
    placeholder_image_tfvars,
)


def _tfvars() -> dict:
    return {
        "architecture_profile_id": "five-layer-baseline",
        "architecture_profile_version": "2",
        "digital_twin_name": "Factory_Twin",
        "gcp_project_id": "phase8-project",
        "gcp_region": "europe-west1",
        "layer_1_provider": "google",
        "layer_2_provider": "google",
        "layer_3_hot_provider": "google",
        "layer_3_cold_provider": "google",
        "layer_3_archive_provider": "google",
        "layer_4_provider": "google",
        "layer_5_provider": "google",
    }


def test_placeholder_refs_are_registry_scoped_and_stage_one_is_closed():
    values = placeholder_image_tfvars(_tfvars())

    assert values["gcp_v2_kubernetes_stage_enabled"] is False
    assert set(values) == {
        "gcp_v2_platform_image",
        "gcp_v2_processor_extension_image",
        "gcp_v2_storage_mover_image",
        "gcp_v2_grafana_image",
        "gcp_v2_kubernetes_stage_enabled",
    }
    assert all(
        value.startswith(
            "europe-west1-docker.pkg.dev/phase8-project/factory-twin-v2/"
        )
        and value.endswith("@sha256:" + "0" * 64)
        for key, value in values.items()
        if key.endswith("_image")
    )


class _Blob:
    def __init__(self):
        self.generation = 7
        self.metadata = None
        self.uploads = []

    @staticmethod
    def exists():
        return False

    def upload_from_filename(self, path, **kwargs):
        self.uploads.append((path, kwargs))

    @staticmethod
    def reload():
        return None


class _Bucket:
    def __init__(self, blob):
        self._blob = blob

    def blob(self, name):
        self._blob.name = name
        return self._blob


class _Storage:
    def __init__(self, blob):
        self._blob = blob

    def bucket(self, name):
        assert name == "build-bucket"
        return _Bucket(self._blob)


class _Request:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class _BuildService:
    def __init__(self):
        self.created = []
        self.operation_name = "projects/phase8-project/locations/europe-west1/operations/1"
        self.image_name = None

    def projects(self):
        return self

    def locations(self):
        return self

    def builds(self):
        return self

    def operations(self):
        return self

    def create(self, *, parent, body):
        self.created.append((parent, body))
        self.image_name = body["images"][0]
        return _Request({"name": self.operation_name, "done": False})

    def get(self, *, name):
        assert name == self.operation_name
        return _Request(
            {
                "name": name,
                "done": True,
                "response": {
                    "results": {
                        "images": [
                            {"name": self.image_name, "digest": "sha256:" + "a" * 64}
                        ]
                    }
                },
            }
        )


def test_publisher_uploads_generation_bound_context_and_returns_digest(tmp_path):
    context = tmp_path / "context.tar.gz"
    context.write_bytes(b"deterministic context")
    blob = _Blob()
    builds = _BuildService()
    publisher = GcpV2ImagePublisher(
        project_path=tmp_path,
        project_id="phase8-project",
        region="europe-west1",
        source_bucket="build-bucket",
        registry_prefix=(
            "europe-west1-docker.pkg.dev/phase8-project/factory-twin-v2/"
        ),
        build_service_account="build@phase8-project.iam.gserviceaccount.com",
        credentials=object(),
        storage_client=_Storage(blob),
        build_service=builds,
        sleep=lambda _seconds: None,
    )

    images = publisher.publish(
        (
            GcpV2ImageRequest(
                "grafana",
                context,
                dockerfile="grafana/Dockerfile",
                build_args=("TARGETARCH=amd64",),
            ),
        )
    )

    assert images["grafana"].endswith("@sha256:" + "a" * 64)
    assert blob.uploads[0][1]["if_generation_match"] == 0
    parent, body = builds.created[0]
    assert parent == "projects/phase8-project/locations/europe-west1"
    assert body["source"]["storageSource"]["generation"] == "7"
    assert body["steps"][0]["name"] == DOCKER_BUILDER
    assert body["steps"][0]["args"][:5] == [
        "build",
        "--platform=linux/amd64",
        "-f",
        "grafana/Dockerfile",
        "--build-arg",
    ]
    assert body["serviceAccount"].endswith(
        "/serviceAccounts/build@phase8-project.iam.gserviceaccount.com"
    )
    assert publisher.evidence_path.stat().st_mode & 0o077 == 0


def test_image_tfvars_uses_dedicated_finite_storage_job_image():
    prefix = "europe-west1-docker.pkg.dev/phase8-project/factory-twin-v2/"
    images = {
        "platform": prefix + "platform@sha256:" + "a" * 64,
        "processor-extension": prefix + "processor-extension@sha256:" + "b" * 64,
        "grafana": prefix + "grafana@sha256:" + "c" * 64,
        "storage-mover": prefix + "storage-mover@sha256:" + "d" * 64,
    }

    values = image_tfvars(images, _tfvars())

    assert values["gcp_v2_storage_mover_image"] == images["storage-mover"]
    assert values["gcp_v2_processor_extension_image"] == images["processor-extension"]
    assert values["gcp_v2_grafana_image"] == images["grafana"]
    assert values["gcp_v2_kubernetes_stage_enabled"] is False
