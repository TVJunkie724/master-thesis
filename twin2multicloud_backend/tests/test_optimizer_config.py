"""
Unit tests for /twins/{id}/optimizer-config API endpoints.

Tests optimizer configuration persistence including:
- Happy path: save/load params and results
- Edge cases: partial saves, overwriting
- Error cases: invalid data, not found
"""

from unittest.mock import AsyncMock, patch

from tests.conftest import create_test_twin
from tests.optimizer_transfer_pricing_test_data import optimizer_transfer_result
from tests.pricing_catalog_test_data import catalog_context


class TestOptimizerConfigRoutes:
    """Tests for /twins/{id}/optimizer-config endpoints."""

    # ============================================================
    # Happy Path Tests
    # ============================================================

    def test_get_optimizer_config_default(self, authenticated_client):
        """GET optimizer-config returns empty defaults for new twin."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.get(f"/twins/{twin_id}/optimizer-config/", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["params"] is None
        assert data["result"] is None
        assert data["cheapest_path"] is None

    def test_save_optimizer_params(self, authenticated_client, sample_calc_params):
        """PUT optimizer-config/params saves calculation parameters."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        response = client.put(
            f"/twins/{twin_id}/optimizer-config/params",
            json={"params": sample_calc_params},
            headers=headers
        )
        
        assert response.status_code == 200
        
        get_response = client.get(f"/twins/{twin_id}/optimizer-config/", headers=headers)
        assert get_response.json()["params"] is not None

    def test_overwrite_params(self, authenticated_client, sample_calc_params):
        """Saving params multiple times overwrites previous."""
        client, headers = authenticated_client
        
        twin_id = create_test_twin(client, headers)
        
        client.put(
            f"/twins/{twin_id}/optimizer-config/params",
            json={"params": sample_calc_params},
            headers=headers
        )
        
        updated_params = {**sample_calc_params, "numberOfDevices": 500}
        client.put(
            f"/twins/{twin_id}/optimizer-config/params",
            json={"params": updated_params},
            headers=headers
        )
        
        get_response = client.get(f"/twins/{twin_id}/optimizer-config/", headers=headers)
        saved_params = get_response.json()["params"]
        assert saved_params["numberOfDevices"] == 500

    def test_save_result_and_get_cheapest_path(self, authenticated_client, sample_calc_params):
        """PUT optimizer-config/result saves calculation output and deployment path."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        calculation_result = {
            "L1": "GCP",
            "L2": "AWS",
            "L3": {
                "Hot": "Azure",
                "Cool": "GCP",
                "Archive": "AWS",
            },
            "L4": "Azure",
            "L5": "GCP",
        }

        with patch(
            "src.services.pricing_catalog_context_service."
            "PricingCatalogContextService.resolve_for_user",
            new=AsyncMock(return_value=catalog_context()),
        ):
            response = client.put(
                f"/twins/{twin_id}/optimizer-config/result",
                json={
                    "params": sample_calc_params,
                    "result": {
                        **optimizer_transfer_result(
                            calculation_result=calculation_result
                        ),
                        "providerCosts": {
                            "aws": 1.2,
                            "azure": 1.1,
                            "gcp": 1.0,
                        },
                        "pricingCatalogs": catalog_context().to_http_dict(),
                    },
                    "cheapest_path": {
                        "l1": "GCP",
                        "l2": "AWS",
                        "l3_hot": "AZURE",
                        "l3_cool": "GCP",
                        "l3_archive": "AWS",
                        "l4": "AZURE",
                        "l5": "GCP",
                    },
                },
                headers=headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["cheapest_path"]["l1"] == "gcp"
        assert data["pricing_catalog_context"] == catalog_context().to_http_dict()
        assert data["calculated_at"] is not None

        path_response = client.get(
            f"/twins/{twin_id}/optimizer-config/cheapest-path",
            headers=headers,
        )
        assert path_response.status_code == 200
        assert path_response.json() == {
            "l1": "gcp",
            "l2": "aws",
            "l3_hot": "azure",
            "l3_cool": "gcp",
            "l3_archive": "aws",
            "l4": "azure",
            "l5": "gcp",
        }

    def test_save_result_rejects_mismatched_client_path(
        self,
        authenticated_client,
        sample_calc_params,
    ):
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        calculation_result = {
            "L1": "GCP",
            "L2": "AWS",
            "L3": {
                "Hot": "Azure",
                "Cool": "GCP",
                "Archive": "AWS",
            },
            "L4": "Azure",
            "L5": "GCP",
        }

        with patch(
            "src.services.pricing_catalog_context_service."
            "PricingCatalogContextService.resolve_for_user",
            new=AsyncMock(return_value=catalog_context()),
        ):
            response = client.put(
                f"/twins/{twin_id}/optimizer-config/result",
                json={
                    "params": sample_calc_params,
                    "result": {
                        **optimizer_transfer_result(
                            calculation_result=calculation_result
                        ),
                        "pricingCatalogs": catalog_context().to_http_dict(),
                    },
                    "cheapest_path": {
                        "l1": "AWS",
                        "l2": "AWS",
                        "l3_hot": "AZURE",
                        "l3_cool": "GCP",
                        "l3_archive": "AWS",
                        "l4": "AZURE",
                        "l5": "GCP",
                    },
                },
                headers=headers,
            )

        assert response.status_code == 422
        assert response.json()["detail"] == {
            "error_code": "OPTIMIZER_RESULT_CONTRACT_INVALID",
            "message": (
                "Client deployment path does not match the validated "
                "Optimizer result."
            ),
            "errors": [
                {
                    "field": "cheapest_path",
                    "message": (
                        "The deployment path must match "
                        "result.calculationResult"
                    ),
                }
            ],
        }

    # ============================================================
    # Error Case Tests
    # ============================================================

    def test_get_optimizer_config_not_found(self, authenticated_client):
        """GET optimizer-config for non-existent twin returns 404."""
        client, headers = authenticated_client
        
        response = client.get("/twins/non-existent-id/optimizer-config/", headers=headers)
        
        assert response.status_code == 404

    def test_save_params_twin_not_found(self, authenticated_client, sample_calc_params):
        """PUT params for non-existent twin returns 404."""
        client, headers = authenticated_client
        
        response = client.put(
            "/twins/non-existent-id/optimizer-config/params",
            json={"params": sample_calc_params},
            headers=headers
        )
        
        assert response.status_code == 404

    def test_get_cheapest_path_without_result_returns_404(self, authenticated_client):
        """GET cheapest-path before calculation returns 404."""
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)

        response = client.get(f"/twins/{twin_id}/optimizer-config/cheapest-path", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "No optimizer result found. Run calculation first."
