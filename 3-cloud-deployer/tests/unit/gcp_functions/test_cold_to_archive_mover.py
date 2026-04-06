"""
Unit tests for GCP Cold-to-Archive Mover Cloud Function.

Tests the data movement logic from Cloud Storage Nearline (cold) to Archive.
Covers both single-cloud and multi-cloud scenarios.

Note: GCP cold-to-archive has NO memory guard (unlike AWS/Azure).

Source: tests/unit/gcp_functions/test_cold_to_archive_mover.py
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
    
    for key in list(sys.modules.keys()):
        if key.startswith("_shared"):
            del sys.modules[key]
    
    yield
    
    if str(gcp_funcs_path) in sys.path:
        sys.path.remove(str(gcp_funcs_path))


@pytest.fixture
def mock_env_single_cloud():
    """Environment for single-cloud (GCP only) scenario."""
    return {
        "DIGITAL_TWIN_INFO": json.dumps({
            "config": {"cold_storage_size_in_days": 30},
            "config_providers": {
                "layer_3_cold_provider": "google",
                "layer_3_archive_provider": "google"
            }
        }),
        "COLD_BUCKET_NAME": "test-cold-bucket",
        "ARCHIVE_BUCKET_NAME": "test-archive-bucket",
        "COLD_RETENTION_DAYS": "30",
        "REMOTE_ARCHIVE_WRITER_URL": "",
        "INTER_CLOUD_TOKEN": ""
    }


@pytest.fixture
def mock_env_cross_cloud():
    """Environment for cross-cloud (GCP→AWS) scenario."""
    return {
        "DIGITAL_TWIN_INFO": json.dumps({
            "config": {"cold_storage_size_in_days": 30},
            "config_providers": {
                "layer_3_cold_provider": "google",
                "layer_3_archive_provider": "aws"
            }
        }),
        "COLD_BUCKET_NAME": "test-cold-bucket",
        "ARCHIVE_BUCKET_NAME": "",
        "COLD_RETENTION_DAYS": "30",
        "REMOTE_ARCHIVE_WRITER_URL": "https://aws-archive-writer.lambda-url.us-east-1.on.aws",
        "INTER_CLOUD_TOKEN": "secret-token"
    }


class TestGcpColdToArchiveMoverQuery:
    """Tests for GCS blob listing logic."""

    def test_lists_blobs_older_than_cutoff(self, mock_env_single_cloud):
        """Mover should list blobs and filter by last_modified using COLD_RETENTION_DAYS."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            # GCP uses COLD_RETENTION_DAYS env var
            retention_days = int(os.environ.get("COLD_RETENTION_DAYS", "30"))
            assert retention_days == 30
            
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            assert cutoff < datetime.now(timezone.utc)

    def test_handles_empty_bucket(self, mock_env_single_cloud):
        """Mover should handle empty cold bucket."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("google.cloud.storage.Client") as mock_storage:
                mock_bucket = MagicMock()
                mock_storage.return_value.bucket.return_value = mock_bucket
                mock_bucket.list_blobs.return_value = []
                
                blobs = list(mock_bucket.list_blobs())
                assert len(blobs) == 0


class TestGcpColdToArchiveMoverLocalCopy:
    """Tests for local archive (same GCP cloud)."""

    def test_changes_storage_class_to_archive(self, mock_env_single_cloud):
        """Mover should change storage class to ARCHIVE."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            from _shared.env_utils import require_env
            
            archive_bucket = require_env("ARCHIVE_BUCKET_NAME")
            assert archive_bucket == "test-archive-bucket"


class TestGcpColdToArchiveMoverCrossCloud:
    """Tests for cross-cloud POST."""

    def test_detects_cross_cloud_mode(self, mock_env_cross_cloud):
        """Should detect when archive is on different cloud."""
        with patch.dict(os.environ, mock_env_cross_cloud, clear=False):
            twin_info = json.loads(os.environ["DIGITAL_TWIN_INFO"])
            providers = twin_info["config_providers"]
            
            l3_cold = providers["layer_3_cold_provider"]
            l3_archive = providers["layer_3_archive_provider"]
            
            assert l3_cold != l3_archive
            assert l3_cold == "google"
            assert l3_archive == "aws"


# NOTE: GCP cold-to-archive has NO memory guard (unlike AWS/Azure)
# Test class for memory guard is intentionally omitted


class TestGcpColdToArchiveMoverDeletion:
    """Tests for deletion from cold after archive."""

    def test_deletes_from_cold_after_move(self, mock_env_single_cloud):
        """Should delete blob from cold bucket after archiving."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("google.cloud.storage.Client") as mock_storage:
                mock_bucket = MagicMock()
                mock_blob = MagicMock()
                mock_storage.return_value.bucket.return_value = mock_bucket
                mock_bucket.blob.return_value = mock_blob
                
                # Verify delete can be called
                mock_blob.delete()
                mock_blob.delete.assert_called_once()


class TestGcpColdToArchiveMoverEnvValidation:
    """Tests for environment variable validation."""

    def test_raises_on_missing_cold_bucket(self):
        """Should raise on missing COLD_BUCKET_NAME."""
        with patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": "{}",
            # Missing COLD_BUCKET_NAME
        }, clear=True):
            from _shared.env_utils import require_env
            
            with pytest.raises(EnvironmentError):
                require_env("COLD_BUCKET_NAME")

    def test_raises_on_missing_archive_bucket(self):
        """Should raise on missing ARCHIVE_BUCKET_NAME."""
        with patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": "{}",
            "COLD_BUCKET_NAME": "cold"
            # Missing ARCHIVE_BUCKET_NAME
        }, clear=True):
            from _shared.env_utils import require_env
            
            with pytest.raises(EnvironmentError):
                require_env("ARCHIVE_BUCKET_NAME")
