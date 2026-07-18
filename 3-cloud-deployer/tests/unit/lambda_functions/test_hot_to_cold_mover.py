"""
Unit tests for AWS Hot-to-Cold Mover Lambda Function.

Tests the data movement logic from DynamoDB (hot) to S3 (cold).
Covers both single-cloud and multi-cloud scenarios.

Source: tests/unit/lambda_functions/test_hot_to_cold_mover.py
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
import importlib.util


# Path to the lambda function under test
MOVER_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "src", "providers", "aws", "lambda_functions",
    "hot-to-cold-mover", "lambda_function.py"
)


def load_lambda_module(path):
    """Dynamically load lambda module after environment is mocked."""
    # Clear any cached module
    if "lambda_function" in sys.modules:
        del sys.modules["lambda_function"]
    
    spec = importlib.util.spec_from_file_location("lambda_function", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lambda_function"] = module
    spec.loader.exec_module(module)
    return module


class TestHotToColdMoverQuery(unittest.TestCase):
    """Tests for DynamoDB query logic."""

    def setUp(self):
        """Set up mocks before loading module."""
        self.mock_dynamodb = MagicMock()
        self.mock_table = MagicMock()
        self.mock_dynamodb.Table.return_value = self.mock_table
        
        self.mock_s3 = MagicMock()
        
        self.boto3_resource_patch = patch("boto3.resource", return_value=self.mock_dynamodb)
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        
        self.boto3_resource_patch.start()
        self.boto3_client_patch.start()
        
        # Environment with single-cloud config
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"hot_storage_size_in_days": 7},
                "config_iot_devices": [{"id": "test-device-1"}],
                "config_providers": {
                    "layer_3_hot_provider": "aws",
                    "layer_3_cold_provider": "aws"
                }
            }),
            "DYNAMODB_TABLE_NAME": "test-hot-table",
            "COLD_S3_BUCKET_NAME": "test-cold-bucket",
            "COLD_STORAGE_CLASS": "STANDARD_IA",
            "REMOTE_COLD_WRITER_URL": "",
            "INTER_CLOUD_TOKEN": ""
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_resource_patch.stop()
        self.boto3_client_patch.stop()

    def test_queries_items_older_than_cutoff(self):
        """Mover should query DynamoDB for items older than hot_storage_size_in_days."""
        # Setup: return items older than cutoff
        old_items = [
            {"device_id": "test-device-1", "timestamp": "2025-01-01T00:00:00Z", "value": 42},
        ]
        self.mock_table.query.return_value = {"Items": old_items}
        self.mock_table.batch_writer.return_value.__enter__ = MagicMock()
        self.mock_table.batch_writer.return_value.__exit__ = MagicMock()
        
        # Execute
        self.module.lambda_handler({}, None)
        
        # Assert: query was called
        self.assertTrue(self.mock_table.query.called)
        
        # Verify query uses timestamp filter
        call_kwargs = self.mock_table.query.call_args_list[0][1]
        self.assertIn("KeyConditionExpression", call_kwargs)

    def test_handles_empty_result(self):
        """Mover should handle case when no items match cutoff."""
        # Setup: no items to move
        self.mock_table.query.return_value = {"Items": []}
        self.mock_table.batch_writer.return_value.__enter__ = MagicMock()
        self.mock_table.batch_writer.return_value.__exit__ = MagicMock()
        
        # Execute - should not raise
        self.module.lambda_handler({}, None)
        
        # Assert: S3 was NOT called (no items to write)
        self.mock_s3.put_object.assert_not_called()


class TestHotToColdMoverLocalWrite(unittest.TestCase):
    """Tests for local S3 write (same-cloud)."""

    def setUp(self):
        self.mock_dynamodb = MagicMock()
        self.mock_table = MagicMock()
        self.mock_dynamodb.Table.return_value = self.mock_table
        self.mock_s3 = MagicMock()
        
        self.boto3_resource_patch = patch("boto3.resource", return_value=self.mock_dynamodb)
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        
        self.boto3_resource_patch.start()
        self.boto3_client_patch.start()
        
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"hot_storage_size_in_days": 7},
                "config_iot_devices": [{"id": "device-1"}],
                "config_providers": {
                    "layer_3_hot_provider": "aws",
                    "layer_3_cold_provider": "aws"
                }
            }),
            "DYNAMODB_TABLE_NAME": "test-table",
            "COLD_S3_BUCKET_NAME": "test-cold-bucket",
            "COLD_STORAGE_CLASS": "STANDARD_IA",
            "REMOTE_COLD_WRITER_URL": "",
            "INTER_CLOUD_TOKEN": ""
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_resource_patch.stop()
        self.boto3_client_patch.stop()

    def test_writes_to_local_s3_same_cloud(self):
        """Mover should write to local S3 when L3-Cold is on same cloud."""
        items = [
            {"device_id": "device-1", "timestamp": "2025-01-01T00:00:00Z", "temp": 25.5},
        ]
        self.mock_table.query.return_value = {"Items": items}
        self.mock_table.batch_writer.return_value.__enter__ = MagicMock()
        self.mock_table.batch_writer.return_value.__exit__ = MagicMock()
        
        self.module.lambda_handler({}, None)
        
        # Verify S3 put_object was called
        self.mock_s3.put_object.assert_called()
        call_kwargs = self.mock_s3.put_object.call_args[1]
        self.assertEqual(call_kwargs["Bucket"], "test-cold-bucket")
        self.assertIn("device-1/", call_kwargs["Key"])
        self.assertEqual(call_kwargs["StorageClass"], "STANDARD_IA")


class TestHotToColdMoverCrossCloud(unittest.TestCase):
    """Tests for cross-cloud POST to remote Cold Writer."""

    def setUp(self):
        self.mock_dynamodb = MagicMock()
        self.mock_table = MagicMock()
        self.mock_dynamodb.Table.return_value = self.mock_table
        self.mock_s3 = MagicMock()
        
        self.boto3_resource_patch = patch("boto3.resource", return_value=self.mock_dynamodb)
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        
        self.boto3_resource_patch.start()
        self.boto3_client_patch.start()
        
        # Cross-cloud config: AWS hot, Azure cold
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"hot_storage_size_in_days": 7},
                "config_iot_devices": [{"id": "device-1"}],
                "config_providers": {
                    "layer_3_hot_provider": "aws",
                    "layer_3_cold_provider": "azure"  # Different!
                }
            }),
            "DYNAMODB_TABLE_NAME": "test-table",
            "COLD_S3_BUCKET_NAME": "unused-bucket",
            "REMOTE_COLD_WRITER_URL": "https://azure-cold-writer.azurewebsites.net/api/cold-writer",
            "INTER_CLOUD_TOKEN": "secret-token-123"
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_resource_patch.stop()
        self.boto3_client_patch.stop()

    @patch.object(sys.modules.get("lambda_function", MagicMock()), "post_raw")
    def test_posts_to_remote_cross_cloud(self, mock_post_raw):
        """Mover should POST to remote Cold Writer when L3-Cold is on different cloud."""
        # Reload with patched post_raw
        with patch("_shared.inter_cloud.post_raw"):
            # Need to reload module to pick up the patch
            module = load_lambda_module(MOVER_PATH)
            
            items = [{"device_id": "device-1", "timestamp": "2025-01-01T00:00:00Z", "temp": 25}]
            self.mock_table.query.return_value = {"Items": items}
            self.mock_table.batch_writer.return_value.__enter__ = MagicMock()
            self.mock_table.batch_writer.return_value.__exit__ = MagicMock()
            
            module.lambda_handler({}, None)
            
            # S3 should NOT be used
            self.mock_s3.put_object.assert_not_called()


class TestHotToColdMoverChunking(unittest.TestCase):
    """Tests for 5MB chunking logic."""

    def setUp(self):
        self.mock_dynamodb = MagicMock()
        self.mock_s3 = MagicMock()
        
        self.boto3_resource_patch = patch("boto3.resource", return_value=self.mock_dynamodb)
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        
        self.boto3_resource_patch.start()
        self.boto3_client_patch.start()
        
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"hot_storage_size_in_days": 7},
                "config_iot_devices": [],
                "config_providers": {
                    "layer_3_hot_provider": "aws",
                    "layer_3_cold_provider": "aws"
                }
            }),
            "DYNAMODB_TABLE_NAME": "test-table",
            "COLD_S3_BUCKET_NAME": "test-bucket",
            "COLD_STORAGE_CLASS": "STANDARD_IA",
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_resource_patch.stop()
        self.boto3_client_patch.stop()

    def test_chunks_large_batches(self):
        """_chunk_items should split items to stay under 5MB."""
        # Create items that total ~10MB (should produce 2+ chunks)
        large_item = {"data": "x" * 100000}  # ~100KB per item
        items = [large_item.copy() for _ in range(100)]  # ~10MB total
        
        chunks = self.module._chunk_items(items, max_bytes=5 * 1024 * 1024)
        
        # Should have multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # Each chunk should be under 5MB
        for chunk_items, idx in chunks:
            chunk_size = len(json.dumps(chunk_items).encode('utf-8'))
            self.assertLess(chunk_size, 5 * 1024 * 1024)


class TestHotToColdMoverDeletion(unittest.TestCase):
    """Tests for deletion from DynamoDB after move."""

    def setUp(self):
        self.mock_dynamodb = MagicMock()
        self.mock_table = MagicMock()
        self.mock_batch_writer = MagicMock()
        self.mock_dynamodb.Table.return_value = self.mock_table
        self.mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=self.mock_batch_writer)
        self.mock_table.batch_writer.return_value.__exit__ = MagicMock()
        
        self.mock_s3 = MagicMock()
        
        self.boto3_resource_patch = patch("boto3.resource", return_value=self.mock_dynamodb)
        self.boto3_client_patch = patch("boto3.client", return_value=self.mock_s3)
        
        self.boto3_resource_patch.start()
        self.boto3_client_patch.start()
        
        self.env_patch = patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": json.dumps({
                "config": {"hot_storage_size_in_days": 7},
                "config_iot_devices": [{"id": "device-1"}],
                "config_providers": {
                    "layer_3_hot_provider": "aws",
                    "layer_3_cold_provider": "aws"
                }
            }),
            "DYNAMODB_TABLE_NAME": "test-table",
            "COLD_S3_BUCKET_NAME": "test-bucket",
            "COLD_STORAGE_CLASS": "STANDARD_IA",
        }, clear=False)
        self.env_patch.start()
        
        self.module = load_lambda_module(MOVER_PATH)

    def tearDown(self):
        self.env_patch.stop()
        self.boto3_resource_patch.stop()
        self.boto3_client_patch.stop()

    def test_deletes_from_dynamodb_after_move(self):
        """Mover should delete items from DynamoDB after writing to cold."""
        items = [
            {"device_id": "device-1", "timestamp": "2025-01-01T00:00:00Z", "temp": 25},
            {"device_id": "device-1", "timestamp": "2025-01-01T01:00:00Z", "temp": 26},
        ]
        self.mock_table.query.return_value = {"Items": items}
        
        self.module.lambda_handler({}, None)
        
        # Verify batch_writer.delete_item was called for each item
        self.assertEqual(self.mock_batch_writer.delete_item.call_count, 2)


class TestHotToColdMoverEnvValidation(unittest.TestCase):
    """Tests for environment variable validation (fail-fast)."""

    def test_raises_on_missing_dynamodb_table(self):
        """Should raise on missing DYNAMODB_TABLE_NAME."""
        with patch("boto3.resource"), patch("boto3.client"):
            with patch.dict(os.environ, {
                "DIGITAL_TWIN_INFO": "{}",
                # Missing DYNAMODB_TABLE_NAME
                "COLD_S3_BUCKET_NAME": "bucket"
            }, clear=True):
                with self.assertRaises(Exception):
                    load_lambda_module(MOVER_PATH)

    def test_raises_on_missing_cold_bucket(self):
        """Should raise on missing COLD_S3_BUCKET_NAME."""
        with patch("boto3.resource"), patch("boto3.client"):
            with patch.dict(os.environ, {
                "DIGITAL_TWIN_INFO": "{}",
                "DYNAMODB_TABLE_NAME": "table"
                # Missing COLD_S3_BUCKET_NAME
            }, clear=True):
                with self.assertRaises(Exception):
                    load_lambda_module(MOVER_PATH)

    def test_local_write_rejects_missing_storage_class(self):
        """A local AWS destination must not fall back to a literal class."""
        with patch("boto3.resource"), patch("boto3.client"):
            with patch.dict(os.environ, {
                "DIGITAL_TWIN_INFO": json.dumps({
                    "config_providers": {
                        "layer_3_hot_provider": "aws",
                        "layer_3_cold_provider": "aws",
                    }
                }),
                "DYNAMODB_TABLE_NAME": "table",
                "COLD_S3_BUCKET_NAME": "bucket",
            }, clear=True):
                module = load_lambda_module(MOVER_PATH)
                with self.assertRaisesRegex(
                    module.ConfigurationError,
                    "COLD_STORAGE_CLASS",
                ):
                    module._write_to_local_s3(
                        "device",
                        [{"value": 1}],
                        "start",
                        "end",
                        0,
                    )


if __name__ == "__main__":
    unittest.main()
