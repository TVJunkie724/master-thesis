"""
Unit tests for AWS Cold-to-Archive Mover Lambda Function.

Tests the data movement logic from S3 Cold to S3 Archive (DEEP_ARCHIVE).
Covers both single-cloud and multi-cloud scenarios.

Source: tests/unit/lambda_functions/test_cold_to_archive_mover.py
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import importlib.util


# Path to the lambda function under test
MOVER_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "src", "providers", "aws", "lambda_functions",
    "cold-to-archive-mover", "lambda_function.py"
)


def load_lambda_module(path):
    """Dynamically load lambda module after environment is mocked."""
    if "lambda_function" in sys.modules:
        del sys.modules["lambda_function"]
    
    spec = importlib.util.spec_from_file_location("lambda_function", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lambda_function"] = module
    spec.loader.exec_module(module)
    return module


class TestColdToArchiveMoverQuery(unittest.TestCase):
    """Tests for S3 list/pagination logic."""

    def setUp(self):
        self.mock_s3 = MagicMock()
        self.mock_paginator = MagicMock()
        self.mock_s3.get_paginator.return_value = self.mock_paginator
        
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        self.boto3_client_patch.start()
        
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"cold_storage_size_in_days": 30},
                "config_providers": {
                    "layer_3_cold_provider": "aws",
                    "layer_3_archive_provider": "aws"
                }
            }),
            "COLD_S3_BUCKET_NAME": "test-cold-bucket",
            "ARCHIVE_S3_BUCKET_NAME": "test-archive-bucket",
            "ARCHIVE_STORAGE_CLASS": "DEEP_ARCHIVE",
            "REMOTE_ARCHIVE_WRITER_URL": "",
            "INTER_CLOUD_TOKEN": ""
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_client_patch.stop()

    def test_lists_objects_older_than_cutoff(self):
        """Mover should list objects from cold bucket and filter by LastModified."""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        
        self.mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "device-1/old-data.json", "LastModified": old_date, "Size": 1000}
                ]
            }
        ]
        
        self.module.lambda_handler({}, None)
        
        # Verify paginator was used
        self.mock_s3.get_paginator.assert_called_with("list_objects_v2")
        self.mock_paginator.paginate.assert_called_with(Bucket="test-cold-bucket")

    def test_handles_empty_bucket(self):
        """Mover should handle empty cold bucket gracefully."""
        # S3 returns no "Contents" key for empty buckets (not Contents=None)
        self.mock_paginator.paginate.return_value = [{}]
        
        # Should not raise
        self.module.lambda_handler({}, None)
        
        # No copy or delete operations
        self.mock_s3.copy_object.assert_not_called()
        self.mock_s3.delete_object.assert_not_called()



class TestColdToArchiveMoverLocalCopy(unittest.TestCase):
    """Tests for local S3 copy (same-cloud)."""

    def setUp(self):
        self.mock_s3 = MagicMock()
        self.mock_paginator = MagicMock()
        self.mock_s3.get_paginator.return_value = self.mock_paginator
        
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        self.boto3_client_patch.start()
        
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"cold_storage_size_in_days": 30},
                "config_providers": {
                    "layer_3_cold_provider": "aws",
                    "layer_3_archive_provider": "aws"
                }
            }),
            "COLD_S3_BUCKET_NAME": "test-cold-bucket",
            "ARCHIVE_S3_BUCKET_NAME": "test-archive-bucket",
            "ARCHIVE_STORAGE_CLASS": "DEEP_ARCHIVE",
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_client_patch.stop()

    def test_copies_to_archive_same_cloud(self):
        """Mover should copy to archive bucket with DEEP_ARCHIVE storage class."""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        
        self.mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "device-1/data.json", "LastModified": old_date, "Size": 1000}
                ]
            }
        ]
        
        self.module.lambda_handler({}, None)
        
        # Verify copy_object was called with DEEP_ARCHIVE
        self.mock_s3.copy_object.assert_called()
        call_kwargs = self.mock_s3.copy_object.call_args[1]
        self.assertEqual(call_kwargs["Bucket"], "test-archive-bucket")
        self.assertEqual(call_kwargs["StorageClass"], "DEEP_ARCHIVE")


class TestColdToArchiveMoverCrossCloud(unittest.TestCase):
    """Tests for cross-cloud POST to remote Archive Writer."""

    def setUp(self):
        self.mock_s3 = MagicMock()
        self.mock_paginator = MagicMock()
        self.mock_s3.get_paginator.return_value = self.mock_paginator
        
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        self.boto3_client_patch.start()
        
        # Cross-cloud config
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"cold_storage_size_in_days": 30},
                "config_providers": {
                    "layer_3_cold_provider": "aws",
                    "layer_3_archive_provider": "azure"  # Different!
                }
            }),
            "COLD_S3_BUCKET_NAME": "test-cold-bucket",
            "ARCHIVE_S3_BUCKET_NAME": "unused",
            "REMOTE_ARCHIVE_WRITER_URL": "https://azure.example.com/archive-writer",
            "INTER_CLOUD_TOKEN": "secret-token"
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_client_patch.stop()

    def test_posts_to_remote_cross_cloud(self):
        """Mover should POST to remote when archive is on different cloud."""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        
        self.mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "device-1/data.json", "LastModified": old_date, "Size": 1000}
                ]
            }
        ]
        
        # Mock get_object to return data
        self.mock_s3.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=b'{"test": "data"}'))
        }
        
        with patch.object(self.module, "post_raw"):
            self.module.lambda_handler({}, None)
            
            # copy_object should NOT be called (using remote)
            self.mock_s3.copy_object.assert_not_called()


class TestColdToArchiveMoverMemoryGuard(unittest.TestCase):
    """Tests for 200MB memory guard."""

    def setUp(self):
        self.mock_s3 = MagicMock()
        self.mock_paginator = MagicMock()
        self.mock_s3.get_paginator.return_value = self.mock_paginator
        
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        self.boto3_client_patch.start()
        
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"cold_storage_size_in_days": 30},
                "config_providers": {
                    "layer_3_cold_provider": "aws",
                    "layer_3_archive_provider": "aws"
                }
            }),
            "COLD_S3_BUCKET_NAME": "test-cold-bucket",
            "ARCHIVE_S3_BUCKET_NAME": "test-archive-bucket",
            "ARCHIVE_STORAGE_CLASS": "DEEP_ARCHIVE",
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_client_patch.stop()

    def test_skips_oversized_objects(self):
        """Mover should skip objects larger than 200MB."""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        
        self.mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    # 250MB - should be skipped
                    {"Key": "device-1/large.json", "LastModified": old_date, "Size": 250 * 1024 * 1024}
                ]
            }
        ]
        
        self.module.lambda_handler({}, None)
        
        # Should NOT process the large object
        self.mock_s3.copy_object.assert_not_called()
        self.mock_s3.delete_object.assert_not_called()


class TestColdToArchiveMoverDeletion(unittest.TestCase):
    """Tests for deletion from cold after archive."""

    def setUp(self):
        self.mock_s3 = MagicMock()
        self.mock_paginator = MagicMock()
        self.mock_s3.get_paginator.return_value = self.mock_paginator
        
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        self.boto3_client_patch.start()
        
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"cold_storage_size_in_days": 30},
                "config_providers": {
                    "layer_3_cold_provider": "aws",
                    "layer_3_archive_provider": "aws"
                }
            }),
            "COLD_S3_BUCKET_NAME": "test-cold-bucket",
            "ARCHIVE_S3_BUCKET_NAME": "test-archive-bucket",
            "ARCHIVE_STORAGE_CLASS": "DEEP_ARCHIVE",
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_client_patch.stop()

    def test_deletes_from_cold_after_move(self):
        """Mover should delete from cold bucket after copying to archive."""
        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        
        self.mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "device-1/data.json", "LastModified": old_date, "Size": 1000}
                ]
            }
        ]
        
        self.module.lambda_handler({}, None)
        
        # Verify delete was called
        self.mock_s3.delete_object.assert_called_with(
            Bucket="test-cold-bucket",
            Key="device-1/data.json"
        )


class TestColdToArchiveMoverEnvValidation(unittest.TestCase):
    """Tests for environment variable validation."""

    def test_raises_on_missing_cold_bucket(self):
        """Should raise on missing COLD_S3_BUCKET_NAME."""
        with patch("boto3.client"):
            with patch.dict(os.environ, {
                "DIGITAL_TWIN_INFO": "{}",
                # Missing COLD_S3_BUCKET_NAME
                "ARCHIVE_S3_BUCKET_NAME": "archive"
            }, clear=True):
                with self.assertRaises(Exception):
                    load_lambda_module(MOVER_PATH)

    def test_raises_on_missing_archive_bucket(self):
        """Should raise on missing ARCHIVE_S3_BUCKET_NAME."""
        with patch("boto3.client"):
            with patch.dict(os.environ, {
                "DIGITAL_TWIN_INFO": "{}",
                "COLD_S3_BUCKET_NAME": "cold"
                # Missing ARCHIVE_S3_BUCKET_NAME
            }, clear=True):
                with self.assertRaises(Exception):
                    load_lambda_module(MOVER_PATH)

    def test_local_copy_rejects_missing_storage_class(self):
        """A local AWS destination must not fall back to a literal class."""
        with patch("boto3.client"):
            with patch.dict(os.environ, {
                "DIGITAL_TWIN_INFO": json.dumps({
                    "config": {"cold_storage_size_in_days": 30},
                    "config_providers": {
                        "layer_3_cold_provider": "aws",
                        "layer_3_archive_provider": "aws",
                    },
                }),
                "COLD_S3_BUCKET_NAME": "cold",
                "ARCHIVE_S3_BUCKET_NAME": "archive",
            }, clear=True):
                module = load_lambda_module(MOVER_PATH)
                with self.assertRaisesRegex(
                    module.ConfigurationError,
                    "ARCHIVE_STORAGE_CLASS",
                ):
                    module.lambda_handler({}, None)


if __name__ == "__main__":
    unittest.main()
