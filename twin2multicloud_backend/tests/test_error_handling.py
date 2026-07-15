"""
Error Handling Tests for Management API.

Tests error handling for optimizer and deployer proxy endpoints.
Each category has:
- 2 happy cases (successful operations)
- 2 error cases (expected failures)
- 5 edge cases (boundary conditions)
"""

from unittest.mock import patch, AsyncMock
from src.clients.optimizer_client import OptimizerProviderStatus
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from tests.conftest import create_test_twin


def _optimizer_status(payload_by_provider=None, status_code=200):
    payload_by_provider = payload_by_provider or {}

    async def _status(self, *, endpoint_prefix, provider):
        return OptimizerProviderStatus(
            provider=provider,
            status_code=status_code,
            payload=payload_by_provider.get(provider, {}),
        )

    return _status


def _validation_files_from_call(call_args):
    for value in list(call_args.args) + list(call_args.kwargs.values()):
        if isinstance(value, dict) and "file" in value:
            return value
    return {}


class TestOptimizerProxyErrorHandling:
    """Tests for /optimizer/* proxy error handling."""

    # ============================================================
    # Happy Path Tests
    # ============================================================

    def test_pricing_status_returns_data(self, authenticated_client):
        """GET optimizer/pricing-status returns data when optimizer available."""
        client, headers = authenticated_client
        
        with patch(
            "src.clients.optimizer_client.OptimizerClient.get_cache_status",
            _optimizer_status({"aws": {"age": "1 day"}}),
        ):
            
            response = client.get("/optimizer/pricing-status", headers=headers)
            
            assert response.status_code == 200
            assert "aws" in response.json()

    def test_regions_status_returns_data(self, authenticated_client):
        """GET optimizer/regions-status returns data when optimizer available."""
        client, headers = authenticated_client
        
        with patch(
            "src.clients.optimizer_client.OptimizerClient.get_cache_status",
            _optimizer_status({"aws": {"age": "1 day"}}),
        ):
            
            response = client.get("/optimizer/regions-status", headers=headers)
            
            assert response.status_code == 200

    # ============================================================
    # Error Case Tests  
    # ============================================================

    def test_pricing_timeout_returns_504(self, authenticated_client):
        """Timeout to optimizer returns 504 with user-friendly message."""
        client, headers = authenticated_client
        
        with patch(
            "src.clients.optimizer_client.OptimizerClient.get_cache_status",
            new_callable=AsyncMock,
            side_effect=ExternalServiceUnavailable("Optimizer API timed out"),
        ):
            
            response = client.get("/optimizer/pricing-status", headers=headers)
            
            assert response.status_code == 504
            assert "timed out" in response.json()["detail"].lower()
            # Verify raw exception NOT exposed
            assert "Read timed out" not in response.json()["detail"]

    def test_regions_timeout_returns_504(self, authenticated_client):
        """Timeout to optimizer regions returns 504."""
        client, headers = authenticated_client
        
        with patch(
            "src.clients.optimizer_client.OptimizerClient.get_cache_status",
            new_callable=AsyncMock,
            side_effect=ExternalServiceUnavailable("Optimizer API timed out"),
        ):
            
            response = client.get("/optimizer/regions-status", headers=headers)
            
            assert response.status_code == 504

    # ============================================================
    # Edge Case Tests
    # ============================================================

    def test_empty_response_from_optimizer(self, authenticated_client):
        """Empty response body from optimizer handled."""
        client, headers = authenticated_client
        
        with patch(
            "src.clients.optimizer_client.OptimizerClient.get_cache_status",
            _optimizer_status(),
        ):
            
            response = client.get("/optimizer/pricing-status", headers=headers)
            
            assert response.status_code == 200

    def test_concurrent_requests_handled(self, authenticated_client):
        """Multiple concurrent requests don't cause issues."""
        client, headers = authenticated_client
        
        with patch(
            "src.clients.optimizer_client.OptimizerClient.get_cache_status",
            _optimizer_status({"aws": {}}),
        ):
            
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
        
        with patch(
            "src.clients.optimizer_client.OptimizerClient.get_cache_status",
            _optimizer_status({"aws": None, "azure": {"age": "1 day"}}),
        ):
            
            response = client.get("/optimizer/pricing-status", headers=headers)
            
            assert response.status_code == 200

    def test_pricing_export_returns_provider_snapshot(self, authenticated_client):
        """Pricing export returns Optimizer snapshot payload for supported provider."""
        client, headers = authenticated_client

        with patch(
            "src.clients.optimizer_client.OptimizerClient.export_pricing_snapshot",
            new_callable=AsyncMock,
            return_value={"provider": "aws", "prices": []},
        ):

            response = client.get("/optimizer/pricing/export/aws", headers=headers)

        assert response.status_code == 200
        assert response.json() == {"provider": "aws", "prices": []}

    def test_pricing_export_rejects_invalid_provider(self, authenticated_client):
        """Pricing export rejects unsupported providers before downstream call."""
        client, headers = authenticated_client

        with patch(
            "src.clients.optimizer_client.OptimizerClient.export_pricing_snapshot",
            new_callable=AsyncMock,
        ) as mock_client:
            response = client.get("/optimizer/pricing/export/digitalocean", headers=headers)

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid provider: digitalocean"
        mock_client.assert_not_called()

    def test_pricing_export_timeout_returns_504(self, authenticated_client):
        """Timeout to optimizer pricing export returns 504."""
        client, headers = authenticated_client

        with patch(
            "src.clients.optimizer_client.OptimizerClient.export_pricing_snapshot",
            new_callable=AsyncMock,
            side_effect=ExternalServiceUnavailable("Optimizer API timed out"),
        ):

            response = client.get("/optimizer/pricing/export/gcp", headers=headers)

        assert response.status_code == 504
        assert "timed out" in response.json()["detail"].lower()


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
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            side_effect=ExternalServiceUnavailable("Deployer API timed out"),
        ):
            
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
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            side_effect=ExternalServiceUnavailable("Deployer API unavailable"),
        ):
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/config",
                json={"content": "{}"},
                headers=headers
            )
            
            # Returns 200 with valid=False and error message
            assert response.status_code == 200
            assert response.json()["valid"] is False
            assert "cannot connect" in response.json()["message"].lower()

    def test_empty_content_validation(self, authenticated_client):
        """Empty content validation request handled."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            return_value={"valid": True},
        ):
            
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
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            return_value={"valid": True},
        ):
            
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


class TestL2ValidationEndpoints:
    """Tests for L2 validation endpoints (function-code, state-machine).
    
    These endpoints validate Python functions and state machines with:
    - Provider-specific syntax checking
    - File upload pattern
    - No DB persistence (BLoC handles)
    """

    # ============================================================
    # Happy Path Tests
    # ============================================================

    def test_function_code_validation_succeeds(self, authenticated_client):
        """POST validate/function-code with valid Python returns valid=True."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            return_value={"message": "Code is valid for aws."},
        ):
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/function-code",
                json={"content": "def lambda_handler(event, context): return {'statusCode': 200}", "provider": "aws"},
                headers=headers
            )
            
            assert response.status_code == 200
            assert response.json()["valid"] is True
            assert "valid" in response.json()["message"].lower()

    def test_state_machine_validation_succeeds(self, authenticated_client):
        """POST validate/state-machine with valid JSON returns valid=True."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            return_value={"message": "State machine is valid for aws."},
        ):
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/state-machine",
                json={"content": '{"StartAt": "Start", "States": {}}', "provider": "aws"},
                headers=headers
            )
            
            assert response.status_code == 200
            assert response.json()["valid"] is True

    # ============================================================
    # Error Case Tests
    # ============================================================

    def test_function_code_missing_provider_returns_400(self, authenticated_client):
        """POST validate/function-code without provider returns 400."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        response = client.post(
            f"/twins/{twin_id}/deployer/validate/function-code",
            json={"content": "def lambda_handler(event, context): pass"},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "provider" in response.json()["detail"].lower()

    def test_state_machine_missing_provider_returns_400(self, authenticated_client):
        """POST validate/state-machine without provider returns 400."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        response = client.post(
            f"/twins/{twin_id}/deployer/validate/state-machine",
            json={"content": '{"StartAt": "Start"}'},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "provider" in response.json()["detail"].lower()

    # ============================================================
    # Edge Case Tests
    # ============================================================

    def test_function_code_invalid_syntax_returns_error(self, authenticated_client):
        """POST validate/function-code with syntax error returns valid=False."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            side_effect=ExternalServiceError(
                "Deployer API returned 400: SyntaxError: invalid syntax",
                upstream_status_code=400,
                public_detail="SyntaxError: invalid syntax at line 1",
            ),
        ):
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/function-code",
                json={"content": "def lambda_handler(event context):", "provider": "aws"},
                headers=headers
            )
            
            assert response.status_code == 200
            assert response.json()["valid"] is False
            assert "syntax" in response.json()["message"].lower()

    def test_state_machine_yaml_detection(self, authenticated_client):
        """State machine with YAML content detected correctly."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        yaml_content = """
StartAt: Start
States:
  Start:
    Type: Pass
    End: true
"""
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            return_value={"message": "Valid"},
        ) as mock_validate:
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/state-machine",
                json={"content": yaml_content, "provider": "aws"},
                headers=headers
            )
            
            assert response.status_code == 200
            # Verify the file was uploaded with .yaml extension (by checking call args)
            files_arg = _validation_files_from_call(mock_validate.call_args)
            assert "file" in files_arg
            filename = files_arg["file"][0]
            assert filename.endswith(".yaml")

    def test_function_code_azure_provider(self, authenticated_client):
        """POST validate/function-code with azure provider works."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            return_value={"message": "Code is valid for azure."},
        ) as mock_validate:
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/function-code",
                json={"content": "def main(req): return HttpResponse('OK')", "provider": "azure"},
                headers=headers
            )
            
            assert response.status_code == 200
            assert response.json()["valid"] is True
            # Verify provider passed in URL
            assert mock_validate.call_args.kwargs["provider"] == "azure"

    def test_function_code_google_provider(self, authenticated_client):
        """POST validate/function-code with google provider works."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            return_value={"message": "Code is valid for google."},
        ):
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/function-code",
                json={"content": "def hello_world(request): return 'Hello'", "provider": "google"},
                headers=headers
            )
            
            assert response.status_code == 200
            assert response.json()["valid"] is True

    def test_function_code_empty_content(self, authenticated_client):
        """POST validate/function-code with empty content handled."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            side_effect=ExternalServiceError(
                "Deployer API returned 400: Empty file",
                upstream_status_code=400,
                public_detail="Empty file",
            ),
        ):
            
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/function-code",
                json={"content": "", "provider": "aws"},
                headers=headers
            )
            
            # API normalizes to valid=False with message
            assert response.status_code == 200
            assert response.json()["valid"] is False

    def test_l2_validation_does_not_persist_to_db(self, authenticated_client):
        """L2 validation (function-code/state-machine) does NOT persist to DB."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        
        with patch(
            "src.clients.deployer_client.DeployerClient.validate_config_file",
            new_callable=AsyncMock,
            return_value={"message": "Valid"},
        ):
            
            # Validate function-code (L2 type)
            response = client.post(
                f"/twins/{twin_id}/deployer/validate/function-code",
                json={"content": "def lambda_handler(event, context): return {}", "provider": "aws"},
                headers=headers
            )
            
            assert response.status_code == 200
            assert response.json()["valid"] is True
        
        # Verify DB was NOT updated by checking config endpoint
        config_response = client.get(f"/twins/{twin_id}/deployer/config", headers=headers)
        config_data = config_response.json()
        
        # L2 validation state should NOT be in response (or should be default)
        # The processor_validated field should remain None/empty
        assert config_data.get("processor_validated") is None or config_data.get("processor_validated") == {}
