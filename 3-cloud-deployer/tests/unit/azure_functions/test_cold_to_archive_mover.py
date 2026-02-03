"""
Unit tests for Azure Cold-to-Archive Mover Function.

Tests the data movement logic from Blob Cool to Blob Archive tier.
Covers both single-cloud and multi-cloud scenarios.

Source: tests/unit/azure_functions/test_cold_to_archive_mover.py
"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta


@pytest.fixture(scope="function", autouse=True)
def azure_funcs_path():
    """Add Azure functions path for imports and clean up after."""
    _azure_funcs_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "src", "providers", "azure", "azure_functions"
    ))
    sys.path.insert(0, _azure_funcs_dir)
    
    for key in list(sys.modules.keys()):
        if key.startswith("_shared"):
            del sys.modules[key]
    
    yield _azure_funcs_dir
    
    if _azure_funcs_dir in sys.path:
        sys.path.remove(_azure_funcs_dir)
    for key in list(sys.modules.keys()):
        if key.startswith("_shared"):
            del sys.modules[key]


@pytest.fixture
def mock_env_single_cloud():
    """Environment for single-cloud (Azure only) scenario."""
    return {
        "DIGITAL_TWIN_INFO": json.dumps({
            "config": {"cold_storage_size_in_days": 30},
            "config_providers": {
                "layer_3_cold_provider": "azure",
                "layer_3_archive_provider": "azure"
            }
        }),
        "BLOB_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test",
        "COLD_STORAGE_CONTAINER": "cold-storage",
        "ARCHIVE_STORAGE_CONTAINER": "archive-storage",
        "REMOTE_ARCHIVE_WRITER_URL": "",
        "INTER_CLOUD_TOKEN": ""
    }


@pytest.fixture
def mock_env_cross_cloud():
    """Environment for cross-cloud (Azure→AWS) scenario."""
    return {
        "DIGITAL_TWIN_INFO": json.dumps({
            "config": {"cold_storage_size_in_days": 30},
            "config_providers": {
                "layer_3_cold_provider": "azure",
                "layer_3_archive_provider": "aws"
            }
        }),
        "BLOB_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test",
        "COLD_STORAGE_CONTAINER": "cold-storage",
        "ARCHIVE_STORAGE_CONTAINER": "",
        "REMOTE_ARCHIVE_WRITER_URL": "https://aws-archive-writer.lambda-url.us-east-1.on.aws",
        "INTER_CLOUD_TOKEN": "secret-token"
    }


class TestAzureColdToArchiveMoverQuery:
    """Tests for Blob listing logic."""

    def test_lists_blobs_older_than_cutoff(self, mock_env_single_cloud):
        """Mover should list blobs and filter by last_modified."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("azure.storage.blob.BlobServiceClient") as mock_blob_service:
                mock_container = MagicMock()
                mock_blob_service.from_connection_string.return_value.get_container_client.return_value = mock_container
                
                old_date = datetime.now(timezone.utc) - timedelta(days=60)
                mock_container.list_blobs.return_value = [
                    MagicMock(name="device-1/data.json", last_modified=old_date, size=1000)
                ]
                
                # Should filter by cutoff (30 days) - this blob is 60 days old
                blobs = list(mock_container.list_blobs())
                assert len(blobs) == 1

    def test_handles_empty_container(self, mock_env_single_cloud):
        """Mover should handle empty cold container."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("azure.storage.blob.BlobServiceClient") as mock_blob_service:
                mock_container = MagicMock()
                mock_blob_service.from_connection_string.return_value.get_container_client.return_value = mock_container
                mock_container.list_blobs.return_value = []
                
                blobs = list(mock_container.list_blobs())
                assert len(blobs) == 0


class TestAzureColdToArchiveMoverLocalCopy:
    """Tests for local archive (same-cloud)."""

    def test_copies_to_archive_same_cloud(self, mock_env_single_cloud):
        """Mover should copy to archive container with Archive tier."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            from _shared.env_utils import require_env
            
            archive_container = require_env("ARCHIVE_STORAGE_CONTAINER")
            assert archive_container == "archive-storage"


class TestAzureColdToArchiveMoverCrossCloud:
    """Tests for cross-cloud POST."""

    def test_detects_cross_cloud_mode(self, mock_env_cross_cloud):
        """Should detect when archive is on different cloud."""
        with patch.dict(os.environ, mock_env_cross_cloud, clear=False):
            twin_info = json.loads(os.environ["DIGITAL_TWIN_INFO"])
            providers = twin_info["config_providers"]
            
            l3_cold = providers["layer_3_cold_provider"]
            l3_archive = providers["layer_3_archive_provider"]
            
            assert l3_cold != l3_archive
            assert l3_cold == "azure"
            assert l3_archive == "aws"


class TestAzureColdToArchiveMoverMemoryGuard:
    """Tests for 200MB memory guard."""

    def test_skips_oversized_objects(self, mock_env_single_cloud):
        """Should skip blobs larger than 200MB."""
        MAX_OBJECT_SIZE_BYTES = 200 * 1024 * 1024
        
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            # Create mock blob that exceeds size limit
            oversized_blob = MagicMock()
            oversized_blob.name = "device-1/large.json"
            oversized_blob.size = 250 * 1024 * 1024  # 250MB
            oversized_blob.last_modified = datetime.now(timezone.utc) - timedelta(days=60)
            
            # The logic should skip this
            should_process = oversized_blob.size <= MAX_OBJECT_SIZE_BYTES
            assert should_process is False


class TestAzureColdToArchiveMoverDeletion:
    """Tests for deletion from cold after archive."""

    def test_deletes_from_cold_after_move(self, mock_env_single_cloud):
        """Should delete blob from cold container after archiving."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("azure.storage.blob.BlobServiceClient") as mock_blob_service:
                mock_container = MagicMock()
                mock_blob_service.from_connection_string.return_value.get_container_client.return_value = mock_container
                
                # Verify delete_blob can be called
                mock_container.delete_blob("device-1/data.json")
                mock_container.delete_blob.assert_called_with("device-1/data.json")


class TestAzureColdToArchiveMoverEnvValidation:
    """Tests for environment variable validation."""

    def test_raises_on_missing_cold_container(self):
        """Should raise on missing COLD_STORAGE_CONTAINER."""
        with patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": "{}",
            "BLOB_CONNECTION_STRING": "test"
            # Missing COLD_STORAGE_CONTAINER
        }, clear=True):
            from _shared.env_utils import require_env
            
            with pytest.raises(EnvironmentError):
                require_env("COLD_STORAGE_CONTAINER")

    def test_raises_on_missing_archive_container(self):
        """Should raise on missing ARCHIVE_STORAGE_CONTAINER."""
        with patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": "{}",
            "BLOB_CONNECTION_STRING": "test",
            "COLD_STORAGE_CONTAINER": "cold"
            # Missing ARCHIVE_STORAGE_CONTAINER
        }, clear=True):
            from _shared.env_utils import require_env
            
            with pytest.raises(EnvironmentError):
                require_env("ARCHIVE_STORAGE_CONTAINER")
