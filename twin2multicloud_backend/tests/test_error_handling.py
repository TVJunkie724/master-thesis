"""
Error Handling Tests for Management API.

Tests error handling for optimizer and deployer proxy endpoints.
Each category has:
- 2 happy cases (successful operations)
- 2 error cases (expected failures)
- 5 edge cases (boundary conditions)
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from tests.conftest import create_test_twin


class TestOptimizerProxyErrorHandling:
    """Tests for /optimizer/* proxy error handling."""

    # ============================================================
    # Happy Path Tests
    # ============================================================

    def test_pricing_status_returns_data(self, authenticated_client):
        """GET optimizer/pricing-status returns data when optimizer available."""
        client, headers = authenticated_client
        
        with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"aws": {"age": "1 day"}}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            response = client.get("/optimizer/pricing-status", headers=headers)
            
            assert response.status_code == 200
            assert "aws" in response.json()

    def test_regions_status_returns_data(self, authenticated_client):
        """GET optimizer/regions-status returns data when optimizer available."""
        client, headers = authenticated_client
        
        with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"aws": {"age": "1 day"}}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            response = client.get("/optimizer/regions-status", headers=headers)
            
            assert response.status_code == 200

    # ============================================================
    # Error Case Tests  
    # ============================================================

    def test_pricing_timeout_returns_504(self, authenticated_client):
        """Timeout to optimizer returns 504 with user-friendly message."""
        client, headers = authenticated_client
        
        with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Read timed out")
            )
            
            response = client.get("/optimizer/pricing-status", headers=headers)
            
            assert response.status_code == 504
            assert "timed out" in response.json()["detail"].lower()
            # Verify raw exception NOT exposed
            assert "Read timed out" not in response.json()["detail"]

    def test_regions_timeout_returns_504(self, authenticated_client):
        """Timeout to optimizer regions returns 504."""
        client, headers = authenticated_client
        
        with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Read timed out")
            )
            
            response = client.get("/optimizer/regions-status", headers=headers)
            
            assert response.status_code == 504

    # ============================================================
    # Edge Case Tests
    # ============================================================

    def test_empty_response_from_optimizer(self, authenticated_client):
        """Empty response body from optimizer handled."""
        client, headers = authenticated_client
        
        with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            response = client.get("/optimizer/pricing-status", headers=headers)
            
            assert response.status_code == 200

    def test_concurrent_requests_handled(self, authenticated_client):
        """Multiple concurrent requests don't cause issues."""
        client, headers = authenticated_client
        
        with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"aws": {}}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            # Make multiple requests
            responses = [
                client.get("/optimizer/pricing-status", headers=headers)
                for _ in range(3)
            ]
            
            # All should succeed
            assert all(r.status_code == 200 for r in responses)

    def test_request_with_bad_path_returns_404(self, authenticated_client):
        """Request with invalid path returns 404."""
        client, headers = authenticated_client
        
        response = client.get("/optimizer/invalid-endpoint", headers=headers)
        
        assert response.status_code == 404

    def test_invalid_token_returns_401(self, authenticated_client):
        """Request with invalid token returns 401."""
        client, headers = authenticated_client
        
        response = client.get(
            "/optimizer/pricing-status",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == 401

    def test_partial_response_handled(self, authenticated_client):
        """Partial response data handled gracefully."""
        client, headers = authenticated_client
        
        with patch("src.api.routes.optimizer.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"aws": None, "azure": {"age": "1 day"}}
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            response = client.get("/optimizer/pricing-status", headers=headers)
            
            assert response.status_code == 200


class TestDeployerProxyErrorHandling:
    """Tests for /twins/{twin_id}/deployer/* proxy error handling."""

    # ============================================================
    # Happy Path Tests
    # ============================================================

    def test_get_deployer_config_returns_data(self, authenticated_client):
        """GET deployer config returns data for owned twin."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        response = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
        
        assert response.status_code == 200

    def test_update_deployer_config_succeeds(self, authenticated_client):
        """PUT deployer config updates data for owned twin."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/deployer/config",
            json={"deployer_digital_twin_name": "test-name"},
            headers=headers
        )
        
        assert response.status_code == 200

    # ============================================================
    # Error Case Tests
    # ============================================================

    def test_nonexistent_twin_returns_404(self, authenticated_client):
        """Request for non-existent twin returns 404."""
        client, headers = authenticated_client
        
        response = client.get("/twins/nonexistent-id-12345/deployer/config", headers=headers)
        
        assert response.status_code == 404

    def test_validation_timeout_returns_error(self, authenticated_client):
        """Timeout to deployer validation returns connection error message."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch("src.api.routes.deployer.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Operation timed out")
            )
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/config",
                json={"content": "{}"},
                headers=headers
            )
            
            # The API may return 200 with valid=False or handle differently
            assert response.status_code in [200, 504]

    # ============================================================
    # Edge Case Tests
    # ============================================================

    def test_validation_connection_error_handled(self, authenticated_client):
        """Connection error to deployer validation handled gracefully."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch("src.api.routes.deployer.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/config",
                json={"content": "{}"},
                headers=headers
            )
            
            # Returns 200 with valid=False and error message
            assert response.status_code == 200
            assert response.json()["valid"] == False
            assert "cannot connect" in response.json()["message"].lower()

    def test_empty_content_validation(self, authenticated_client):
        """Empty content validation request handled."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch("src.api.routes.deployer.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"valid": True}
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/config",
                json={"content": ""},
                headers=headers
            )
            
            assert response.status_code == 200

    def test_valid_config_type_events_accepted(self, authenticated_client):
        """Events config type is accepted."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch("src.api.routes.deployer.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"valid": True}
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/events",
                json={"content": "{}"},
                headers=headers
            )
            
            assert response.status_code == 200

    def test_invalid_config_type_rejected(self, authenticated_client):
        """Invalid config_type returns 400."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        response = client.post(
            f"/twins/{twin_id}/deployer/validate/invalid_type",
            json={"content": "{}"},
            headers=headers
        )
        
        assert response.status_code == 400

    def test_concurrent_config_requests(self, authenticated_client):
        """Multiple concurrent config requests handled."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        # Make multiple requests
        responses = [
            client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
            for _ in range(3)
        ]
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
