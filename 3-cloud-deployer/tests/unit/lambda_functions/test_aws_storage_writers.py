"""Contract tests for specification-owned AWS storage writer classes."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


FUNCTIONS_ROOT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "providers"
    / "aws"
    / "lambda_functions"
)


def _load_function(directory: str):
    module_name = f"test_{directory.replace('-', '_')}"
    path = FUNCTIONS_ROOT / directory / "lambda_function.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("directory", "class_env", "class_value", "bucket_env", "payload"),
    [
        (
            "cold-writer",
            "COLD_STORAGE_CLASS",
            "STANDARD_IA",
            "COLD_S3_BUCKET_NAME",
            {
                "iot_device_id": "device-1",
                "chunk_index": 0,
                "start_timestamp": "2026-01-01T00:00:00Z",
                "end_timestamp": "2026-01-01T01:00:00Z",
                "items": [{"value": 1}],
            },
        ),
        (
            "archive-writer",
            "ARCHIVE_STORAGE_CLASS",
            "DEEP_ARCHIVE",
            "ARCHIVE_S3_BUCKET_NAME",
            {
                "object_key": "device-1/chunk.json",
                "data": [{"value": 1}],
            },
        ),
    ],
)
def test_writer_uses_injected_storage_class(
    directory,
    class_env,
    class_value,
    bucket_env,
    payload,
):
    s3 = MagicMock()
    environment = {
        bucket_env: "target-bucket",
        class_env: class_value,
        "INTER_CLOUD_TOKEN": "token",
    }
    event = {
        "headers": {"x-inter-cloud-token": "token"},
        "body": json.dumps(payload),
    }

    with patch.dict(os.environ, environment, clear=True), patch(
        "boto3.client",
        return_value=s3,
    ):
        module = _load_function(directory)
        response = module.lambda_handler(event, None)

    assert response["statusCode"] == 200
    assert s3.put_object.call_args.kwargs["StorageClass"] == class_value


@pytest.mark.parametrize(
    ("directory", "class_env", "bucket_env"),
    [
        ("cold-writer", "COLD_STORAGE_CLASS", "COLD_S3_BUCKET_NAME"),
        ("archive-writer", "ARCHIVE_STORAGE_CLASS", "ARCHIVE_S3_BUCKET_NAME"),
    ],
)
def test_writer_rejects_missing_storage_class(
    directory,
    class_env,
    bucket_env,
):
    environment = {
        bucket_env: "target-bucket",
        "INTER_CLOUD_TOKEN": "token",
    }

    with patch.dict(os.environ, environment, clear=True), patch("boto3.client"):
        with pytest.raises(EnvironmentError, match=class_env):
            _load_function(directory)
