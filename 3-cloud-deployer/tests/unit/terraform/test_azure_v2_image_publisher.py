"""Offline tests for automatic Azure Five-layer v2 image publication."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.providers.terraform.azure_v2_image_publisher import (
    AzureV2ImagePublisher,
    AzureV2ImageRequest,
    azure_v2_container_deployment,
    image_tfvars,
)


def _tfvars() -> dict:
    return {
        "architecture_profile_id": "five-layer-baseline",
        "architecture_profile_version": "2",
        "layer_3_hot_provider": "azure",
        "layer_3_cold_provider": "azure",
        "layer_3_archive_provider": "azure",
    }


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Transport:
    def __init__(self, *, unavailable=False, existing_status=""):
        self.calls = []
        self.created = bool(existing_status)
        self.image_name = (
            "twinregistry.azurecr.io/storage-mover:stale" if existing_status else ""
        )
        self.status = existing_status
        self.unavailable = unavailable
        self.deleted = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if "taskRuns/" in url and method == "GET":
            if not self.created:
                return _Response(404)
            registry, tagged = self.image_name.split("/", 1)
            repository, tag = tagged.rsplit(":", 1)
            return _Response(
                200,
                {
                    "properties": {
                        "runResult": {
                            "properties": {
                                "status": self.status,
                                "outputImages": [
                                    {
                                        "registry": registry,
                                        "repository": repository,
                                        "tag": tag,
                                        "digest": "sha256:" + "a" * 64,
                                    }
                                ],
                            }
                        }
                    }
                },
            )
        if "taskRuns/" in url and method == "DELETE":
            self.created = False
            self.deleted = True
            return _Response(200)
        if "listBuildSourceUploadUrl" in url:
            if self.unavailable:
                return _Response(
                    403,
                    {"error": {"code": "TasksOperationsNotAllowed"}},
                )
            return _Response(
                200,
                {
                    "relativePath": "source/context.tar.gz",
                    "uploadUrl": "https://upload.invalid/context?sig=secret",
                },
            )
        if url.startswith("https://upload.invalid/"):
            assert kwargs["headers"] == {
                "x-ms-blob-type": "BlockBlob",
                "content-type": "application/gzip",
            }
            return _Response(201)
        if "taskRuns/" in url and method == "PUT":
            self.image_name = kwargs["json"]["properties"]["runRequest"][
                "imageNames"
            ][0]
            self.created = True
            self.status = "Succeeded"
            return _Response(201)
        raise AssertionError((method, url))


def _publisher(tmp_path, transport):
    return AzureV2ImagePublisher(
        project_path=tmp_path,
        subscription_id="00000000-0000-0000-0000-000000000001",
        resource_group="twin-rg",
        location="westeurope",
        registry_name="twinregistry",
        login_server="twinregistry.azurecr.io",
        credential=SimpleNamespace(
            get_token=lambda _scope: SimpleNamespace(token="arm-token")
        ),
        transport=transport,
        sleep=lambda _seconds: None,
    )


def test_publisher_uploads_context_and_returns_task_run_digest(tmp_path):
    context = tmp_path / "context.tar.gz"
    context.write_bytes(b"deterministic context")
    transport = _Transport()
    publisher = _publisher(tmp_path, transport)

    images = publisher.publish((AzureV2ImageRequest("storage-mover", context),))

    assert images["storage-mover"] == (
        "twinregistry.azurecr.io/storage-mover@sha256:" + "a" * 64
    )
    assert publisher.evidence_path.stat().st_mode & 0o077 == 0
    assert publisher.publish((AzureV2ImageRequest("storage-mover", context),)) == images
    assert len([call for call in transport.calls if call[1].startswith("https://upload")]) == 1


def test_free_credit_task_pause_fails_closed_without_local_fallback(tmp_path):
    context = tmp_path / "context.tar.gz"
    context.write_bytes(b"deterministic context")
    publisher = _publisher(tmp_path, _Transport(unavailable=True))

    with pytest.raises(
        RuntimeError,
        match="AZURE_ACR_TASKS_NOT_AVAILABLE_FOR_SUBSCRIPTION",
    ):
        publisher.publish((AzureV2ImageRequest("storage-mover", context),))


def test_failed_task_run_is_deleted_before_a_bounded_retry(tmp_path):
    context = tmp_path / "context.tar.gz"
    context.write_bytes(b"deterministic context")
    transport = _Transport(existing_status="Failed")
    publisher = _publisher(tmp_path, transport)

    images = publisher.publish((AzureV2ImageRequest("storage-mover", context),))

    assert transport.deleted is True
    assert images["storage-mover"].endswith("@sha256:" + "a" * 64)


def test_selection_and_tfvars_are_bounded_to_the_azure_mover():
    assert azure_v2_container_deployment(_tfvars()) is True
    assert (
        azure_v2_container_deployment(
            {**_tfvars(), "architecture_profile_version": "1"}
        )
        is False
    )
    image = "twinregistry.azurecr.io/storage-mover@sha256:" + "b" * 64
    assert image_tfvars({"storage-mover": image}, _tfvars()) == {
        "azure_v2_storage_mover_image": image
    }
