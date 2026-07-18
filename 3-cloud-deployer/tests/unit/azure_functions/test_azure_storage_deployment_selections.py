"""Runtime contracts for optimizer-owned Azure Blob tiers and schedules."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


FUNCTION_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "azure"
    / "azure_functions"
)


def _load_module(directory: str):
    path = FUNCTION_ROOT / directory / "function_app.py"
    name = f"test_{directory.replace('-', '_')}_{id(path)}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hot_to_cold_local_write_uses_configured_blob_tier():
    with patch.dict(os.environ, {"COLD_BLOB_TIER": "Cool"}, clear=True):
        module = _load_module("hot-to-cold-mover")
        container = MagicMock()
        module._blob_container_client = container

        module._write_to_local_blob("device-1", [{"value": 1}], "a", "b", 0)

    container.get_blob_client.return_value.upload_blob.assert_called_once_with(
        '[{"value": 1}]',
        overwrite=True,
        standard_blob_tier="Cool",
    )


def test_cross_cloud_cold_writer_uses_configured_blob_tier():
    env = {
        "INTER_CLOUD_TOKEN": "test-token",
        "COLD_BLOB_TIER": "Cool",
    }
    request = MagicMock()
    request.headers = {"X-Inter-Cloud-Token": "test-token"}
    request.get_json.return_value = {
        "iot_device_id": "device-1",
        "chunk_index": 0,
        "start_timestamp": "a",
        "end_timestamp": "b",
        "items": [{"value": 1}],
    }
    container = MagicMock()

    with patch.dict(os.environ, env, clear=True):
        module = _load_module("cold-writer")
        module._blob_container_client = container
        module.validate_token = MagicMock(return_value=True)
        response = module.cold_writer(request)

    assert response.status_code == 200
    container.get_blob_client.return_value.upload_blob.assert_called_once_with(
        '[{"value": 1}]',
        overwrite=True,
        standard_blob_tier="Cool",
    )


def test_cold_to_archive_local_copy_uses_configured_blob_tier():
    env = {
        "DIGITAL_TWIN_INFO": (
            '{"config":{"cold_storage_size_in_days":30},'
            '"config_providers":{"layer_3_cold_provider":"azure",'
            '"layer_3_archive_provider":"azure"}}'
        ),
        "BLOB_CONNECTION_STRING": "UseDevelopmentStorage=true",
        "COLD_STORAGE_CONTAINER": "cold",
        "ARCHIVE_STORAGE_CONTAINER": "archive",
        "ARCHIVE_BLOB_TIER": "Archive",
        "REMOTE_ARCHIVE_WRITER_URL": "",
    }
    old_blob = MagicMock()
    old_blob.name = "device/data.json"
    old_blob.size = 10
    from datetime import datetime, timedelta, timezone

    old_blob.last_modified = datetime.now(timezone.utc) - timedelta(days=60)
    service = MagicMock()
    cold = MagicMock()
    archive = MagicMock()
    cold.list_blobs.return_value = [old_blob]
    service.get_container_client.side_effect = [cold, archive]

    with patch.dict(os.environ, env, clear=True):
        module = _load_module("cold-to-archive-mover")
        module._blob_service_client = service
        module.cold_to_archive_mover(MagicMock(past_due=False))

    archive.get_blob_client.return_value.start_copy_from_url.assert_called_once_with(
        cold.get_blob_client.return_value.url,
        standard_blob_tier="Archive",
    )
    cold.delete_blob.assert_called_once_with("device/data.json")


def test_cross_cloud_archive_writer_uses_configured_blob_tier():
    env = {
        "INTER_CLOUD_TOKEN": "test-token",
        "ARCHIVE_BLOB_TIER": "Archive",
    }
    request = MagicMock()
    request.headers = {"X-Inter-Cloud-Token": "test-token"}
    request.get_json.return_value = {
        "object_key": "device/data.json",
        "data": "{}",
    }
    container = MagicMock()

    with patch.dict(os.environ, env, clear=True):
        module = _load_module("archive-writer")
        module._blob_container_client = container
        module.validate_token = MagicMock(return_value=True)
        response = module.archive_writer(request)

    assert response.status_code == 200
    container.get_blob_client.return_value.upload_blob.assert_called_once_with(
        "{}",
        overwrite=True,
        standard_blob_tier="Archive",
    )


def test_cross_cloud_archive_does_not_require_local_archive_settings():
    env = {
        "DIGITAL_TWIN_INFO": (
            '{"config":{"cold_storage_size_in_days":30},'
            '"config_providers":{"layer_3_cold_provider":"azure",'
            '"layer_3_archive_provider":"aws"}}'
        ),
        "BLOB_CONNECTION_STRING": "UseDevelopmentStorage=true",
        "COLD_STORAGE_CONTAINER": "cold",
        "REMOTE_ARCHIVE_WRITER_URL": "https://archive.example.test",
        "INTER_CLOUD_TOKEN": "test-token",
    }
    service = MagicMock()
    service.get_container_client.return_value.list_blobs.return_value = []

    with patch.dict(os.environ, env, clear=True):
        module = _load_module("cold-to-archive-mover")
        module._blob_service_client = service
        module.cold_to_archive_mover(MagicMock(past_due=False))

    service.get_container_client.assert_called_once_with("cold")


@pytest.mark.parametrize(
    ("directory", "schedule"),
    (
        ("hot-to-cold-mover", "%HOT_TO_COOL_TIMER_SCHEDULE%"),
        ("cold-to-archive-mover", "%COOL_TO_ARCHIVE_TIMER_SCHEDULE%"),
    ),
)
def test_transition_timer_decorators_use_app_settings(directory, schedule):
    source = (FUNCTION_ROOT / directory / "function_app.py").read_text(
        encoding="utf-8"
    )
    assert f'schedule="{schedule}"' in source


@pytest.mark.parametrize(
    ("directory", "getter", "environment_name"),
    (
        ("cold-writer", "_get_cold_blob_tier", "COLD_BLOB_TIER"),
        ("archive-writer", "_get_archive_blob_tier", "ARCHIVE_BLOB_TIER"),
    ),
)
def test_cross_cloud_writers_fail_closed_without_destination_tier(
    directory,
    getter,
    environment_name,
):
    with patch.dict(os.environ, {}, clear=True):
        module = _load_module(directory)
        with pytest.raises(EnvironmentError, match=environment_name):
            getattr(module, getter)()
