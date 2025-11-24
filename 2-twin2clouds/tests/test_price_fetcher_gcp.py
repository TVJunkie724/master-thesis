import pytest
from backend.cloud_price_fetcher_google import fetch_gcp_price, STATIC_DEFAULTS_GCP

def test_fetch_gcp_price_iot():
    """Test fetching GCP IoT (Pub/Sub) pricing - returns static defaults"""
    
    result = fetch_gcp_price("iot", "us-central1", debug=False)
    
    assert result is not None
    assert "pricePerMessage" in result
    assert isinstance(result["pricePerMessage"], (int, float))

def test_fetch_gcp_price_functions():
    """Test fetching GCP Functions pricing - returns static defaults"""
    
    result = fetch_gcp_price("functions", "us-central1", debug=False)
    
    assert result is not None
    assert "requestPrice" in result
    assert "durationPrice" in result
    assert "freeRequests" in result
    assert "freeComputeTime" in result

def test_fetch_gcp_price_storage_hot():
    """Test fetching GCP Firestore (hot storage) pricing"""
    
    result = fetch_gcp_price("storage_hot", "us-central1", debug=False)
    
    assert result is not None
    assert "storagePrice" in result
    assert "writePrice" in result
    assert "readPrice" in result

def test_fetch_gcp_price_storage_cool():
    """Test fetching GCP Storage Nearline (cool) pricing"""
    
    result = fetch_gcp_price("storage_cool", "us-central1", debug=False)
    
    assert result is not None
    assert "storagePrice" in result
    assert "dataRetrievalPrice" in result

def test_fetch_gcp_price_storage_archive():
    """Test fetching GCP Storage Archive pricing"""
    
    result = fetch_gcp_price("storage_archive", "us-central1", debug=False)
    
    assert result is not None
    assert "storagePrice" in result
    assert "dataRetrievalPrice" in result

def test_fetch_gcp_price_transfer():
    """Test fetching GCP data transfer pricing"""
    
    result = fetch_gcp_price("transfer", "us-central1", debug=False)
    
    assert result is not None
    assert "egressPrice" in result
    assert isinstance(result["egressPrice"], (int, float))

def test_fetch_gcp_price_twinmaker():
    """Test fetching GCP twin management pricing (placeholder)"""
    
    result = fetch_gcp_price("twinmaker", "us-central1", debug=False)
    
    assert result is not None
    # These are placeholders for self-hosted equivalents
    assert "entityPrice" in result
    assert "queryPrice" in result

def test_fetch_gcp_price_grafana():
    """Test fetching GCP Grafana pricing (placeholder)"""
    
    result = fetch_gcp_price("grafana", "us-central1", debug=False)
    
    assert result is not None
    assert "editorPrice" in result
    assert "viewerPrice" in result

def test_fetch_gcp_price_unknown_service():
    """Test fetching pricing for an unknown service"""
    
    result = fetch_gcp_price("unknown_service", "us-central1", debug=False)
    
    # Should return None for unknown services
    assert result is None

def test_static_defaults_structure():
    """Test that static defaults have the expected structure"""
    
    # Verify all expected services are in static defaults
    expected_services = [
        "transfer", "iot", "functions", "storage_hot", 
        "storage_cool", "storage_archive", "twinmaker", "grafana"
    ]
    
    for service in expected_services:
        assert service in STATIC_DEFAULTS_GCP
        assert isinstance(STATIC_DEFAULTS_GCP[service], dict)
        assert len(STATIC_DEFAULTS_GCP[service]) > 0
