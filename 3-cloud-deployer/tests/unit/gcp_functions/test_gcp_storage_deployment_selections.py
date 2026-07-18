"""Runtime contracts for optimizer-owned GCP storage selections."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


FUNCTION_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "gcp"
    / "cloud_functions"
)


def _load_module(directory: str):
    path = FUNCTION_ROOT / directory / "main.py"
    name = f"test_{directory.replace('-', '_')}_{id(object())}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _old_blob(name: str = "device/data.json"):
    blob = MagicMock()
    blob.name = name
    blob.time_created = datetime.now(timezone.utc) - timedelta(days=60)
    return blob


def test_hot_to_cool_local_write_uses_configured_storage_class():
    env = {
        "COLD_BUCKET_NAME": "cold",
        "COLD_STORAGE_CLASS": "NEARLINE",
    }
    client = MagicMock()

    with patch.dict(os.environ, env, clear=True):
        module = _load_module("hot-to-cold-mover")
        module._storage_client = client
        module._write_to_local_gcs("device-1", [{"value": 1}], "a", "b", 0)

    blob = client.bucket.return_value.blob.return_value
    assert blob.storage_class == "NEARLINE"
    blob.upload_from_string.assert_called_once()


def test_cross_cloud_cool_does_not_require_local_bucket_or_storage_class():
    env = {
        "DIGITAL_TWIN_INFO": (
            '{"config_providers":{"layer_3_hot_provider":"google",'
            '"layer_3_cold_provider":"azure"}}'
        ),
        "FIRESTORE_COLLECTION": "hot-data",
        "REMOTE_COLD_WRITER_URL": "https://cold.example.test",
        "INTER_CLOUD_TOKEN": "test-token",
    }
    document = MagicMock()
    document.to_dict.return_value = {
        "device_id": "device-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "value": 1,
    }
    firestore_client = MagicMock()
    query = (
        firestore_client.collection.return_value
        .where.return_value
        .order_by.return_value
        .limit.return_value
    )
    query.stream.return_value = [document]

    with patch.dict(os.environ, env, clear=True):
        module = _load_module("hot-to-cold-mover")
        module._firestore_client = firestore_client
        module.post_raw = MagicMock()
        response = module.main(MagicMock())

    assert response[1] == 200
    module.post_raw.assert_called_once()
    firestore_client.batch.return_value.delete.assert_called_once_with(
        document.reference
    )
    firestore_client.batch.return_value.commit.assert_called_once_with()


def test_cool_to_archive_local_copy_uses_dedicated_bucket_and_storage_class():
    env = {
        "DIGITAL_TWIN_INFO": (
            '{"config_providers":{"layer_3_cold_provider":"google",'
            '"layer_3_archive_provider":"google"}}'
        ),
        "COLD_BUCKET_NAME": "cold",
        "ARCHIVE_BUCKET_NAME": "archive",
        "ARCHIVE_STORAGE_CLASS": "ARCHIVE",
        "REMOTE_ARCHIVE_WRITER_URL": "",
    }
    old_blob = _old_blob()
    cold_bucket = MagicMock()
    cold_bucket.list_blobs.return_value = [old_blob]
    archive_bucket = MagicMock()
    client = MagicMock()
    client.bucket.side_effect = [cold_bucket, archive_bucket]

    with patch.dict(os.environ, env, clear=True):
        module = _load_module("cold-to-archive-mover")
        module._storage_client = client
        response = module.main(MagicMock())

    assert response[1] == 200
    client.bucket.assert_any_call("cold")
    client.bucket.assert_any_call("archive")
    archive_blob = archive_bucket.blob.return_value
    assert archive_blob.storage_class == "ARCHIVE"
    archive_blob.rewrite.assert_called_once_with(old_blob)
    old_blob.delete.assert_called_once_with()


def test_cross_cloud_archive_does_not_require_local_archive_selection():
    env = {
        "DIGITAL_TWIN_INFO": (
            '{"config_providers":{"layer_3_cold_provider":"google",'
            '"layer_3_archive_provider":"aws"}}'
        ),
        "COLD_BUCKET_NAME": "cold",
        "REMOTE_ARCHIVE_WRITER_URL": "https://archive.example.test",
        "INTER_CLOUD_TOKEN": "test-token",
    }
    old_blob = _old_blob()
    old_blob.download_as_text.return_value = '[{"value": 1}]'
    cold_bucket = MagicMock()
    cold_bucket.list_blobs.return_value = [old_blob]
    client = MagicMock()
    client.bucket.return_value = cold_bucket

    with patch.dict(os.environ, env, clear=True):
        module = _load_module("cold-to-archive-mover")
        module._storage_client = client
        module.post_raw = MagicMock()
        response = module.main(MagicMock())

    assert response[1] == 200
    client.bucket.assert_called_once_with("cold")
    module.post_raw.assert_called_once()
    old_blob.delete.assert_called_once_with()


@pytest.mark.parametrize(
    ("directory", "bucket_env", "class_env", "payload"),
    (
        (
            "cold-writer",
            ("COLD_BUCKET", "cold"),
            ("COLD_STORAGE_CLASS", "NEARLINE"),
            {
                "iot_device_id": "device-1",
                "items": [{"value": 1}],
                "startTimestamp": "a",
                "endTimestamp": "b",
                "chunkIndex": 0,
            },
        ),
        (
            "archive-writer",
            ("ARCHIVE_BUCKET", "archive"),
            ("ARCHIVE_STORAGE_CLASS", "ARCHIVE"),
            {
                "blobName": "device/data.json",
                "items": [{"value": 1}],
            },
        ),
    ),
)
def test_cross_cloud_writer_uses_configured_storage_class(
    directory,
    bucket_env,
    class_env,
    payload,
):
    env = {
        "INTER_CLOUD_TOKEN": "test-token",
        bucket_env[0]: bucket_env[1],
        class_env[0]: class_env[1],
    }
    request = MagicMock()
    request.get_json.return_value = payload
    client = MagicMock()

    with patch.dict(os.environ, env, clear=True):
        module = _load_module(directory)
        module.validate_token = MagicMock(return_value=True)
        module._storage_client = client
        response = module.main(request)

    assert response[1] == 200
    blob = client.bucket.return_value.blob.return_value
    assert blob.storage_class == class_env[1]
    blob.upload_from_string.assert_called_once()


@pytest.mark.parametrize(
    ("directory", "getter", "environment_name"),
    (
        ("hot-to-cold-mover", "_get_cold_storage_class", "COLD_STORAGE_CLASS"),
        (
            "cold-to-archive-mover",
            "_get_archive_storage_class",
            "ARCHIVE_STORAGE_CLASS",
        ),
        ("cold-writer", "_get_cold_storage_class", "COLD_STORAGE_CLASS"),
        (
            "archive-writer",
            "_get_archive_storage_class",
            "ARCHIVE_STORAGE_CLASS",
        ),
    ),
)
def test_storage_class_selection_fails_closed(
    directory,
    getter,
    environment_name,
):
    with patch.dict(os.environ, {}, clear=True):
        module = _load_module(directory)
        with pytest.raises(EnvironmentError, match=environment_name):
            getattr(module, getter)()
