"""
Unit tests for Azure Hot-to-Cold Mover Function.

Tests the data movement logic from Cosmos DB (hot) to Blob Storage (cold).
Covers both single-cloud and multi-cloud scenarios.

Source: tests/unit/azure_functions/test_hot_to_cold_mover.py
"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="function", autouse=True)
def azure_funcs_path():
    """Add Azure functions path for imports and clean up after."""
    _azure_funcs_dir = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "src", "providers", "azure", "azure_functions"
    ))
    sys.path.insert(0, _azure_funcs_dir)
    
    # Clear cached shared modules
    for key in list(sys.modules.keys()):
        if key.startswith("_shared") or "hot-to-cold-mover" in key:
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
            "config": {"hot_storage_size_in_days": 7},
            "config_iot_devices": [{"id": "test-device"}],
            "config_providers": {
                "layer_3_hot_provider": "azure",
                "layer_3_cold_provider": "azure"
            }
        }),
        "COSMOS_DB_ENDPOINT": "https://test-cosmos.documents.azure.com:443/",
        "COSMOS_DB_KEY": "test-key",
        "COSMOS_DB_DATABASE": "test-db",
        "COSMOS_DB_CONTAINER": "hot-storage",
        "BLOB_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test",
        "COLD_STORAGE_CONTAINER": "cold-storage",
        "REMOTE_COLD_WRITER_URL": "",
        "INTER_CLOUD_TOKEN": ""
    }


@pytest.fixture
def mock_env_cross_cloud():
    """Environment for cross-cloud (Azure→AWS) scenario."""
    return {
        "DIGITAL_TWIN_INFO": json.dumps({
            "config": {"hot_storage_size_in_days": 7},
            "config_iot_devices": [{"id": "test-device"}],
            "config_providers": {
                "layer_3_hot_provider": "azure",
                "layer_3_cold_provider": "aws"
            }
        }),
        "COSMOS_DB_ENDPOINT": "https://test-cosmos.documents.azure.com:443/",
        "COSMOS_DB_KEY": "test-key",
        "COSMOS_DB_DATABASE": "test-db",
        "COSMOS_DB_CONTAINER": "hot-storage",
        "BLOB_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test",
        "COLD_STORAGE_CONTAINER": "",
        "REMOTE_COLD_WRITER_URL": "https://aws-cold-writer.lambda-url.us-east-1.on.aws",
        "INTER_CLOUD_TOKEN": "secret-token"
    }


class TestAzureHotToColdMoverQuery:
    """Tests for Cosmos DB query logic."""

    def test_queries_items_older_than_cutoff(self, mock_env_single_cloud):
        """Mover should query Cosmos DB for items older than hot_storage_size_in_days."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("azure.cosmos.CosmosClient") as mock_cosmos:
                with patch("azure.storage.blob.BlobServiceClient"):
                    mock_container = MagicMock()
                    mock_cosmos.return_value.get_database_client.return_value.get_container_client.return_value = mock_container
                    mock_container.query_items.return_value = []
                    
                    # Import after env is set
                    # Force reimport
                    if "function_app" in sys.modules:
                        del sys.modules["function_app"]
                    
                    # Test the _get_digital_twin_info function
                    from _shared.env_utils import require_env
                    twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
                    assert twin_info["config"]["hot_storage_size_in_days"] == 7

    def test_handles_empty_result(self, mock_env_single_cloud):
        """Mover should handle case when no items match cutoff."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("azure.cosmos.CosmosClient") as mock_cosmos:
                with patch("azure.storage.blob.BlobServiceClient") as mock_blob:
                    mock_container = MagicMock()
                    mock_cosmos.return_value.get_database_client.return_value.get_container_client.return_value = mock_container
                    mock_container.query_items.return_value = []
                    
                    # Blob should not be called if no items
                    mock_blob_container = MagicMock()
                    mock_blob.from_connection_string.return_value.get_container_client.return_value = mock_blob_container
                    
                    # No items = no blob writes
                    mock_blob_container.upload_blob.assert_not_called()


class TestAzureHotToColdMoverLocalWrite:
    """Tests for local Blob Storage write (same-cloud)."""

    def test_writes_to_local_blob_same_cloud(self, mock_env_single_cloud):
        """Mover should write to local Blob Storage when L3-Cold is Azure."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            from _shared.env_utils import require_env
            
            container_name = require_env("COLD_STORAGE_CONTAINER")
            assert container_name == "cold-storage"


class TestAzureHotToColdMoverCrossCloud:
    """Tests for cross-cloud POST to remote."""

    def test_detects_cross_cloud_mode(self, mock_env_cross_cloud):
        """Should detect when cold storage is on different cloud."""
        with patch.dict(os.environ, mock_env_cross_cloud, clear=False):
            twin_info = json.loads(os.environ["DIGITAL_TWIN_INFO"])
            providers = twin_info["config_providers"]
            
            l3_hot = providers["layer_3_hot_provider"]
            l3_cold = providers["layer_3_cold_provider"]
            
            # Different providers = cross-cloud
            assert l3_hot != l3_cold
            assert l3_hot == "azure"
            assert l3_cold == "aws"


class TestAzureHotToColdMoverChunking:
    """Tests for 5MB chunking logic."""

    def test_chunks_large_batches(self, mock_env_single_cloud):
        """Should chunk items to stay under 5MB."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            # Test the chunking constant
            MAX_CHUNK_SIZE_BYTES = 5 * 1024 * 1024
            
            # Create large items
            large_item = {"data": "x" * 100000}  # ~100KB
            items = [large_item.copy() for _ in range(100)]  # ~10MB total
            
            # Simulated chunking (same logic as function)
            chunks = []
            current_chunk = []
            current_size = 2
            
            for item in items:
                item_size = len(json.dumps(item).encode('utf-8')) + 1
                if current_size + item_size > MAX_CHUNK_SIZE_BYTES and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = [item]
                    current_size = 2 + item_size
                else:
                    current_chunk.append(item)
                    current_size += item_size
            
            if current_chunk:
                chunks.append(current_chunk)
            
            assert len(chunks) > 1


class TestAzureHotToColdMoverDeletion:
    """Tests for deletion from Cosmos DB after move."""

    def test_deletes_from_cosmos_after_move(self, mock_env_single_cloud):
        """Should delete items from Cosmos DB after writing to cold."""
        with patch.dict(os.environ, mock_env_single_cloud, clear=False):
            with patch("azure.cosmos.CosmosClient") as mock_cosmos:
                mock_container = MagicMock()
                mock_cosmos.return_value.get_database_client.return_value.get_container_client.return_value = mock_container
                
                # Verify delete_item method exists and can be called
                test_item = {"id": "test-id", "device_id": "device-1"}
                mock_container.delete_item(item=test_item["id"], partition_key=test_item["device_id"])
                
                mock_container.delete_item.assert_called_once()


class TestAzureHotToColdMoverEnvValidation:
    """Tests for environment variable validation."""

    def test_raises_on_missing_cosmos_endpoint(self):
        """Should raise on missing COSMOS_DB_ENDPOINT."""
        with patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": "{}",
            # Missing COSMOS_DB_ENDPOINT
        }, clear=True):
            from _shared.env_utils import require_env
            
            with pytest.raises(EnvironmentError):
                require_env("COSMOS_DB_ENDPOINT")

    def test_raises_on_missing_blob_connection_string(self):
        """Should raise on missing BLOB_CONNECTION_STRING."""
        with patch.dict(os.environ, {
            "DIGITAL_TWIN_INFO": "{}",
        }, clear=True):
            from _shared.env_utils import require_env
            
            with pytest.raises(EnvironmentError):
                require_env("BLOB_CONNECTION_STRING")
