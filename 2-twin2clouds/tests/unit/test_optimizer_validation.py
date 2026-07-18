"""
Unit tests for the Optimizer validation endpoint.

Tests O1-O4 from the implementation plan.
"""
from fastapi.testclient import TestClient
from rest_api import app


client = TestClient(app)


class TestOptimizerConfigValidation:
    """Tests for POST /validate/optimizer-config endpoint."""
    
    def test_O1_valid_params_and_result(self):
        """O1: Valid params + result should return valid=true."""
        response = client.post("/validate/optimizer-config", json={
            "params": {
                "numberOfDevices": 10,
                "useEventChecking": True,
                "returnFeedbackToDevice": False,
                "triggerNotificationWorkflow": True
            },
            "result": {
                "cheapestPath": [
                    "L1_aws",
                    "L2_azure",
                    "L3_gcp",
                    "L4_aws",
                    "L5_azure"
                ],
                "calculationResult": {
                    "L1": "aws",
                    "L2": "azure",
                    "L3_hot": "gcp",
                    "L4": "aws",
                    "L5": "azure"
                },
                "total_cost": 123.45
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] == []
    
    def test_O2_missing_params(self):
        """O2: Missing params should return MISSING_PARAMS error."""
        response = client.post("/validate/optimizer-config", json={
            "params": None,
            "result": {
                "cheapestPath": ["L1_aws"]
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) == 1
        assert data["errors"][0]["code"] == "MISSING_PARAMS"
        assert data["errors"][0]["field"] == "params"
    
    def test_O3_missing_result(self):
        """O3: Missing result should return MISSING_RESULT error."""
        response = client.post("/validate/optimizer-config", json={
            "params": {"numberOfDevices": 10},
            "result": None
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) == 1
        assert data["errors"][0]["code"] == "MISSING_RESULT"
        assert data["errors"][0]["field"] == "result"
    
    def test_O4_result_without_cheapest_path(self):
        """O4: Result without cheapest_path should return MISSING_CHEAPEST_PATH error."""
        response = client.post("/validate/optimizer-config", json={
            "params": {"numberOfDevices": 10},
            "result": {
                "total_cost": 123.45
                # Missing cheapest_path
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) == 1
        assert data["errors"][0]["code"] == "MISSING_CHEAPEST_PATH"
        assert data["errors"][0]["field"] == "cheapest_path"
    
    def test_multiple_errors_aggregated(self):
        """Multiple errors should all be returned."""
        response = client.post("/validate/optimizer-config", json={
            "params": None,
            "result": None
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) == 2
        error_codes = [e["code"] for e in data["errors"]]
        assert "MISSING_PARAMS" in error_codes
        assert "MISSING_RESULT" in error_codes
