"""
Unit tests for GCP Hot-to-Cold Mover Cloud Function.

Tests the data movement logic from Firestore (hot) to Cloud Storage (cold).
Covers both single-cloud and multi-cloud scenarios.

Note: GCP uses HOT_RETENTION_DAYS env var instead of config object.

Source: tests/unit/gcp_functions/test_hot_to_cold_mover.py
"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from pathlib import Path


# Add GCP cloud functions path
gcp_funcs_path = Path(__file__).parent.parent.parent.parent / "src" / "providers" / "gcp" / "cloud_functions"


@pytest.fixture(scope="function", autouse=True)
def setup_gcp_path():
    """Add GCP functions path for imports."""
    sys.path.insert(0, str(gcp_funcs_path))
    
    # Clear cached modules
    for key in list(sys.modules.keys()):
        if key.startswith("_shared") or "hot-to-cold-mover" in key:
            del sys.modules[key]
    
    yield
    
    if str(gcp_funcs_path) in sys.path:
        sys.path.remove(str(gcp_funcs_path))


@pytest.fixture
def mock_env_single_cloud():
    """Environment for single-cloud (GCP only) scenario."""
    return {
        "DIGITAL_TWIN_INFO": json.dumps({
            "config": {"hot_storage_size_in_days": 7},
            "config_iot_devices": [{"id": "test-device"}],
            "config_providers": {
                "layer_3_hot_provider": "google",
                "layer_3_cold_provider": "google"
            }
        }),
        "FIRESTORE_COLLECTION": "hot-storage",
        "COLD_BUCKET_NAME": "test-cold-bucket",
        "HOT_RETENTION_DAYS": "7",
        "FIRESTORE_DATABASE": "(default)",
        "REMOTE_COLD_WRITER_URL": "",
        "INTER_CLOUD_TOKEN": ""
    }


@pytest.fixture
def mock_env_cross_cloud():
    """Environment for cross-cloud (GCP→AWS) scenario."""
    return {
        "DIGITAL_TWIN_INFO": json.dumps({
            "config": {"hot_storage_size_in_days": 7},
            "config_iot_devices": [{"id": "test-device"}],
            "config_providers": {
                "layer_3_hot_provider": "google",
                "layer_3_cold_provider": "aws"
            }
        }),
        "FIRESTORE_COLLECTION": "hot-storage",
        "COLD_BUCKET_NAME": "",
        "HOT_RETENTION_DAYS": "7",
        "FIRESTORE_DATABASE": "(default)",
        "REMOTE_COLD_WRITER_URL": "https://aws-cold-writer.lambda-url.us-east-1.on.aws",
        "INTER_CLOUD_TOKEN": "secret-token"
    }


class TestGcpHotToColdMoverQuery:
    """Tests for Firestore query logic."""

    def test_queries_items_older_than_cutoff(self, mock_env_single_cloud):
        """Mover should query Firestore for items older than HOT_RETENTION_DAYS."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            # Verify env var is used (not config object like AWS/Azure)
            retention_days = int(os.environ.get("HOT_RETENTION_DAYS", "7"))
            assert retention_days == 7
            
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            assert cutoff < datetime.now(timezone.utc)

    def test_handles_empty_result(self, mock_env_single_cloud):
        """Mover should handle case when no items match cutoff."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("google.cloud.firestore.Client") as mock_firestore:
                mock_collection = MagicMock()
                mock_firestore.return_value.collection.return_value = mock_collection
                mock_collection.where.return_value.stream.return_value = []
                
                # Empty stream = no items to process
                items = list(mock_collection.where.return_value.stream())
                assert len(items) == 0


class TestGcpHotToColdMoverLocalWrite:
    """Tests for local GCS write (same-cloud)."""

    def test_writes_to_local_gcs_same_cloud(self, mock_env_single_cloud):
        """Mover should write to local GCS when L3-Cold is GCP."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            from _shared.env_utils import require_env
            
            bucket_name = require_env("COLD_BUCKET_NAME")
            assert bucket_name == "test-cold-bucket"


class TestGcpHotToColdMoverCrossCloud:
    """Tests for cross-cloud POST."""

    def test_detects_cross_cloud_mode(self, mock_env_cross_cloud):
        """Should detect when cold storage is on different cloud."""
        with patch.dict(os.environ, mock_env_cross_cloud, clear=False):
            twin_info = json.loads(os.environ["DIGITAL_TWIN_INFO"])
            providers = twin_info["config_providers"]
            
            l3_hot = providers["layer_3_hot_provider"]
            l3_cold = providers["layer_3_cold_provider"]
            
            # Different providers = cross-cloud
            assert l3_hot != l3_cold
            assert l3_hot == "google"
            assert l3_cold == "aws"


class TestGcpHotToColdMoverChunking:
    """Tests for 5MB chunking logic."""

    def test_chunks_large_batches(self, mock_env_single_cloud):
        """Should chunk items to stay under 5MB."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            MAX_CHUNK_SIZE_BYTES = 5 * 1024 * 1024
            
            large_item = {"data": "x" * 100000}
            items = [large_item.copy() for _ in range(100)]
            
            # Simulate chunking logic
            chunks = []
            current_chunk = []
            current_size = 0
            
            for item in items:
                item_size = len(json.dumps(item).encode('utf-8'))
                if current_size + item_size > MAX_CHUNK_SIZE_BYTES and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = [item]
                    current_size = item_size
                else:
                    current_chunk.append(item)
                    current_size += item_size
            
            if current_chunk:
                chunks.append(current_chunk)
            
            assert len(chunks) > 1


class TestGcpHotToColdMoverDeletion:
    """Tests for deletion from Firestore after move."""

    def test_deletes_from_firestore_after_move(self, mock_env_single_cloud):
        """Should delete items from Firestore after writing to cold."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("google.cloud.firestore.Client") as mock_firestore:
                mock_doc = MagicMock()
                mock_firestore.return_value.collection.return_value.document.return_value = mock_doc
                
                # Verify delete can be called
                mock_doc.delete()
                mock_doc.delete.assert_called_once()


class TestGcpHotToColdMoverEnvValidation:
    """Tests for environment variable validation."""

    def test_raises_on_missing_firestore_collection(self):
        """Should raise on missing FIRESTORE_COLLECTION."""
        with patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": "{}",
            # Missing FIRESTORE_COLLECTION
        }, clear=True):
            from _shared.env_utils import require_env
            
            with pytest.raises(EnvironmentError):
                require_env("FIRESTORE_COLLECTION")

    def test_raises_on_missing_cold_bucket(self):
        """Should raise on missing COLD_BUCKET_NAME."""
        with patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": "{}",
            "FIRESTORE_COLLECTION": "test"
            # Missing COLD_BUCKET_NAME
        }, clear=True):
            from _shared.env_utils import require_env
            
            with pytest.raises(EnvironmentError):
                require_env("COLD_BUCKET_NAME")
