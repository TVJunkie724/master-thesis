from fastapi.testclient import TestClient
from unittest.mock import patch
from rest_api import app
import backend.constants as CONSTANTS

client = TestClient(app)

# ----------------------------------------------------------------
# AWS Region Tests
# ----------------------------------------------------------------

def test_fetch_regions_aws_default():
    """
    Test POST /api/fetch_regions/aws without params.
    Should default to force_fetch=False.
    If file is fresh, should use cache.
    """
    with patch("rest_api.is_file_fresh") as mock_is_fresh, \
         patch("rest_api.load_json_file") as mock_load, \
         patch("backend.fetch_data.initial_fetch_aws.fetch_region_map") as mock_fetch:
        
        # Case: File is fresh
        mock_is_fresh.return_value = True
        mock_load.return_value = {"cached": "aws"}
        
        response = client.post("/api/fetch_regions/aws")
        
        assert response.status_code == 200
        assert response.json() == {"cached": "aws"}
        mock_fetch.assert_not_called()

def test_fetch_regions_aws_force():
    """
    Test POST /api/fetch_regions/aws with force_fetch=True.
    Should ignore cache and call fetch_region_map.
    """
    with patch("rest_api.is_file_fresh") as mock_is_fresh, \
         patch("backend.fetch_data.initial_fetch_aws.fetch_region_map") as mock_fetch:
        
        # Case: File is fresh, but we force update
        mock_is_fresh.return_value = True
        mock_fetch.return_value = {"fresh": "aws"}
        
        response = client.post("/api/fetch_regions/aws?force_fetch=true")
        
        assert response.status_code == 200
        assert response.json() == {"fresh": "aws"}
        mock_fetch.assert_called_once_with(force_update=True)

def test_fetch_regions_aws_stale():
    """
    Test POST /api/fetch_regions/aws when file is stale.
    Should call fetch_region_map even if force_fetch=False.
    """
    with patch("rest_api.is_file_fresh") as mock_is_fresh, \
         patch("backend.fetch_data.initial_fetch_aws.fetch_region_map") as mock_fetch:
        
        # Case: File is stale
        mock_is_fresh.return_value = False
        mock_fetch.return_value = {"fresh": "aws"}
        
        response = client.post("/api/fetch_regions/aws")
        
        assert response.status_code == 200
        assert response.json() == {"fresh": "aws"}
        mock_fetch.assert_called_once_with(force_update=True)

# ----------------------------------------------------------------
# Azure Region Tests
# ----------------------------------------------------------------

def test_fetch_regions_azure_default():
    with patch("rest_api.is_file_fresh") as mock_is_fresh, \
         patch("rest_api.load_json_file") as mock_load, \
         patch("backend.fetch_data.initial_fetch_azure.fetch_region_map") as mock_fetch:
        
        mock_is_fresh.return_value = True
        mock_load.return_value = {"cached": "azure"}
        
        response = client.post("/api/fetch_regions/azure")
        
        assert response.status_code == 200
        assert response.json() == {"cached": "azure"}
        mock_fetch.assert_not_called()

def test_fetch_regions_azure_force():
    with patch("rest_api.is_file_fresh") as mock_is_fresh, \
         patch("backend.fetch_data.initial_fetch_azure.fetch_region_map") as mock_fetch:
        
        mock_is_fresh.return_value = True
        mock_fetch.return_value = {"fresh": "azure"}
        
        response = client.post("/api/fetch_regions/azure?force_fetch=true")
        
        assert response.status_code == 200
        assert response.json() == {"fresh": "azure"}
        mock_fetch.assert_called_once_with(force_update=True)

# ----------------------------------------------------------------
# GCP Region Tests
# ----------------------------------------------------------------

def test_fetch_regions_gcp_default():
    with patch("rest_api.is_file_fresh") as mock_is_fresh, \
         patch("rest_api.load_json_file") as mock_load, \
         patch("backend.fetch_data.initial_fetch_google.fetch_region_map") as mock_fetch:
        
        mock_is_fresh.return_value = True
        mock_load.return_value = {"cached": "gcp"}
        
        response = client.post("/api/fetch_regions/gcp")
        
        assert response.status_code == 200
        assert response.json() == {"cached": "gcp"}
        mock_fetch.assert_not_called()

def test_fetch_regions_gcp_force():
    with patch("rest_api.is_file_fresh") as mock_is_fresh, \
         patch("backend.fetch_data.initial_fetch_google.fetch_region_map") as mock_fetch:
        
        mock_is_fresh.return_value = True
        mock_fetch.return_value = {"fresh": "gcp"}
        
        response = client.post("/api/fetch_regions/gcp?force_fetch=true")
        
        assert response.status_code == 200
        assert response.json() == {"fresh": "gcp"}
        mock_fetch.assert_called_once_with(force_update=True)
