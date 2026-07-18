"""Route tests for read-only optimizer results and parameter drafts."""

from tests.conftest import create_test_twin


class TestOptimizerConfigRoutes:
    def test_get_optimizer_config_default(self, authenticated_client):
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)

        response = client.get(
            f"/twins/{twin_id}/optimizer-config/",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["params"] is None
        assert data["result"] is None
        assert data["cheapest_path"] is None

    def test_save_optimizer_params(
        self,
        authenticated_client,
        sample_calc_params,
    ):
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)

        response = client.put(
            f"/twins/{twin_id}/optimizer-config/params",
            json={"params": sample_calc_params},
            headers=headers,
        )

        assert response.status_code == 200
        saved = client.get(
            f"/twins/{twin_id}/optimizer-config/",
            headers=headers,
        ).json()
        assert saved["params"] is not None
        assert saved["result"] is None

    def test_overwrite_params(
        self,
        authenticated_client,
        sample_calc_params,
    ):
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)
        client.put(
            f"/twins/{twin_id}/optimizer-config/params",
            json={"params": sample_calc_params},
            headers=headers,
        )

        updated_params = {**sample_calc_params, "numberOfDevices": 500}
        response = client.put(
            f"/twins/{twin_id}/optimizer-config/params",
            json={"params": updated_params},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["params"]["numberOfDevices"] == 500

    def test_client_result_write_endpoint_is_removed(
        self,
        authenticated_client,
        sample_calc_params,
    ):
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)

        response = client.put(
            f"/twins/{twin_id}/optimizer-config/result",
            json={
                "params": sample_calc_params,
                "result": {"totalCost": 1},
                "cheapest_path": {"l1": "aws"},
            },
            headers=headers,
        )

        assert response.status_code in {404, 405}
        schema = client.get("/openapi.json", headers=headers).json()
        assert "/twins/{twin_id}/optimizer-config/result" not in schema["paths"]
        operation_ids = {
            operation["operationId"]
            for path in schema["paths"].values()
            for operation in path.values()
            if isinstance(operation, dict) and "operationId" in operation
        }
        assert "saveOptimizerResult" not in operation_ids

    def test_generic_twin_update_rejects_optimizer_result(
        self,
        authenticated_client,
    ):
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)

        response = client.put(
            f"/twins/{twin_id}/config/",
            json={"optimizer_result": {"totalCost": 1}},
            headers=headers,
        )

        assert response.status_code == 422
        config = client.get(
            f"/twins/{twin_id}/optimizer-config/",
            headers=headers,
        ).json()
        assert config["result"] is None

    def test_get_optimizer_config_not_found(self, authenticated_client):
        client, headers = authenticated_client

        response = client.get(
            "/twins/non-existent-id/optimizer-config/",
            headers=headers,
        )

        assert response.status_code == 404

    def test_save_params_twin_not_found(
        self,
        authenticated_client,
        sample_calc_params,
    ):
        client, headers = authenticated_client

        response = client.put(
            "/twins/non-existent-id/optimizer-config/params",
            json={"params": sample_calc_params},
            headers=headers,
        )

        assert response.status_code == 404

    def test_get_cheapest_path_without_result_returns_404(
        self,
        authenticated_client,
    ):
        client, headers = authenticated_client
        twin_id = create_test_twin(client, headers)

        response = client.get(
            f"/twins/{twin_id}/optimizer-config/cheapest-path",
            headers=headers,
        )

        assert response.status_code == 404
        assert response.json()["detail"] == (
            "No optimizer result found. Run calculation first."
        )
