import json

import pytest

from src.api.routes.optimizer_runs import get_optimizer_client
from src.models.cost_calculation import CostCalculationRun
from src.models.optimizer_config import OptimizerConfiguration
from src.models.twin import DigitalTwin, TwinState
from src.models.user import User
from src.services.cost_calculation_run_service import CostCalculationRunService
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from tests.conftest import create_test_twin


class FakeOptimizerClient:
    def __init__(self, payload=None, exc=None):
        self.payload = payload if payload is not None else _optimizer_payload()
        self.exc = exc
        self.calls = []

    async def calculate(self, params):
        self.calls.append(params)
        if self.exc:
            raise self.exc
        return self.payload


def _optimizer_payload(overrides=None):
    result = {
        "optimization_profile_id": "cost_minimization_v1",
        "result_schema_version": "cost-result.v1",
        "optimizationProfile": {
            "profile_id": "cost_minimization_v1",
            "profile_version": "2026.06.08",
            "enabled": True,
            "metric_provider_ids": ["cost"],
            "calculation_model_ids": ["cost_model_v1"],
            "scoring_strategy_id": "min_total_cost_v1",
            "intent_group_ids": ["cost"],
            "pricing_registry_version": "2026.06.08",
        },
        "evidenceReferences": {
            "pricing_registry": "pricing_registry:2026.06.08",
            "pricing_evidence_contract": "pricing-evidence.v1",
            "intent_group_ids": ["cost"],
        },
        "calculationResult": {
            "L1": "AWS",
            "L2": "Azure",
            "L3": {"Hot": "GCP", "Cool": "AWS", "Archive": "Azure"},
            "L4": "AWS",
            "L5": "Azure",
        },
        "awsCosts": {
            "L1": {"cost": 1.0},
            "L2": {"cost": 9.0},
            "L3_hot": {"cost": 9.0},
            "L3_cool": {"cost": 2.0},
            "L3_archive": {"cost": 9.0},
            "L4": {"cost": 3.0},
            "L5": {"cost": 9.0},
        },
        "azureCosts": {
            "L1": {"cost": 9.0},
            "L2": {"cost": 1.5},
            "L3_hot": {"cost": 9.0},
            "L3_cool": {"cost": 9.0},
            "L3_archive": {"cost": 2.5},
            "L4": {"cost": 9.0},
            "L5": {"cost": 4.0},
        },
        "gcpCosts": {
            "L1": {"cost": 9.0},
            "L2": {"cost": 9.0},
            "L3_hot": {"cost": 1.25},
            "L3_cool": {"cost": 9.0},
            "L3_archive": {"cost": 9.0},
            "L4": {"cost": 9.0},
            "L5": {"cost": 9.0},
        },
        "transferCosts": {"L1_to_L2": 0.5},
        "cheapestPath": [
            "L1_AWS",
            "L2_Azure",
            "L3_hot_GCP",
            "L3_cool_AWS",
            "L3_archive_Azure",
            "L4_AWS",
            "L5_Azure",
        ],
        "totalCost": 14.75,
        "currency": "USD",
    }
    if overrides:
        result.update(overrides)
    return {"result": result}


def _override_optimizer(client, fake):
    client.app.dependency_overrides[get_optimizer_client] = lambda: fake


def test_create_run_persists_history_items_and_compatibility_state(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    fake = FakeOptimizerClient()
    _override_optimizer(client, fake)

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={
            "params": sample_calc_params,
            "pricing_snapshots": {"aws": {"snapshot": "aws"}},
            "pricing_timestamps": {"aws": "2026-06-08T12:00:00Z"},
            "pricing_evidence_version": "evidence.v1",
            "pricing_run_reference": "pricing-run-1",
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["optimization_profile_id"] == "cost_minimization_v1"
    assert data["optimization_profile_version"] == "2026.06.08"
    assert data["scoring_strategy_id"] == "min_total_cost_v1"
    assert data["calculation_model_version"] == "cost_model_v1"
    assert data["pricing_registry_version"] == "2026.06.08"
    assert data["pricing_evidence_version"] == "evidence.v1"
    assert data["pricing_run_reference"] == "pricing-run-1"
    assert data["total_monthly_cost"] == 14.75
    assert data["cheapest_path"]["l1"] == "AWS"
    assert len(data["result_items"]) == 8

    run = db_session.query(CostCalculationRun).filter_by(id=data["id"]).one()
    config = db_session.query(OptimizerConfiguration).filter_by(twin_id=twin_id).one()
    assert run.optimizer_config_id == config.id
    assert config.cheapest_l1 == "AWS"
    assert config.cheapest_l2 == "Azure"
    assert config.cheapest_l3_hot == "GCP"
    assert config.cheapest_l4 == "AWS"
    assert json.loads(config.params)["numberOfDevices"] == sample_calc_params["numberOfDevices"]
    assert json.loads(config.result_json)["totalCost"] == 14.75
    assert fake.calls == [sample_calc_params]


def test_list_and_detail_are_scoped_to_current_user(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    own_twin_id = create_test_twin(client, headers, name="Own Twin")
    fake = FakeOptimizerClient()
    _override_optimizer(client, fake)

    create_response = client.post(
        f"/twins/{own_twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    assert create_response.status_code == 200
    run_id = create_response.json()["id"]

    other_user = User(email="other@example.com", name="Other")
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_twin = DigitalTwin(
        name="Other Twin",
        user_id=other_user.id,
        state=TwinState.DRAFT,
    )
    db_session.add(other_twin)
    db_session.commit()
    db_session.refresh(other_twin)

    list_response = client.get(f"/twins/{own_twin_id}/optimizer-runs/", headers=headers)
    assert list_response.status_code == 200
    assert [run["id"] for run in list_response.json()] == [run_id]

    detail_response = client.get(
        f"/twins/{own_twin_id}/optimizer-runs/{run_id}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == run_id

    foreign_response = client.get(
        f"/twins/{other_twin.id}/optimizer-runs/",
        headers=headers,
    )
    assert foreign_response.status_code == 404


def test_detail_returns_explicit_evidence_references(
    authenticated_client,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload(
        {
            "resultItems": [
                {
                    "layer": "L1",
                    "component": "ingestion",
                    "provider": "AWS",
                    "service_intent_id": "iot.message_ingest",
                    "cost_amount": 1.23,
                    "currency": "USD",
                    "unit": "message",
                    "quantity": 1000,
                    "unit_price": 0.00123,
                    "evidence_id": "aws-iot-evidence-1",
                    "service_model_id": "iot_ingestion_v1",
                    "calculation_notes": {"selected_row": "sku-1"},
                    "review_status": "reviewed",
                }
            ]
        }
    )
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 200
    item = response.json()["result_items"][0]
    assert item["evidence_id"] == "aws-iot-evidence-1"
    assert item["service_intent_id"] == "iot.message_ingest"
    assert item["calculation_notes"] == {"selected_row": "sku-1"}


def test_create_run_persists_optimizer_evidence_reference_metadata(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(client, FakeOptimizerClient())

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 200
    run = db_session.query(CostCalculationRun).filter_by(id=response.json()["id"]).one()
    result_summary = json.loads(run.result_summary_json)
    assert result_summary["evidenceReferences"]["pricing_registry"] == (
        "pricing_registry:2026.06.08"
    )
    assert result_summary["evidenceReferences"]["pricing_evidence_contract"] == (
        "pricing-evidence.v1"
    )


def test_missing_evidence_references_are_rejected(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload()
    payload["result"].pop("evidenceReferences")
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert "evidenceReferences" in str(response.json()["detail"]["field_errors"])
    assert db_session.query(CostCalculationRun).count() == 0


def test_invalid_optimizer_contract_returns_structured_502_without_successful_run(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(client, FakeOptimizerClient(payload={"result": {"totalCost": 1.0}}))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error_code"] == "OPTIMIZER_CONTRACT_INVALID"
    assert db_session.query(CostCalculationRun).count() == 0


def test_disabled_optimizer_profile_is_rejected(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    payload = _optimizer_payload({"optimization_profile_id": "latency_minimization_v1"})
    _override_optimizer(client, FakeOptimizerClient(payload=payload))

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    assert "disabled profile" in str(response.json()["detail"]["field_errors"])
    assert db_session.query(CostCalculationRun).count() == 0


def test_optimizer_unavailable_returns_503_without_successful_run(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(
        client,
        FakeOptimizerClient(exc=ExternalServiceUnavailable("Optimizer API unavailable")),
    )

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "OPTIMIZER_UNAVAILABLE"
    assert db_session.query(CostCalculationRun).count() == 0


def test_optimizer_error_response_does_not_echo_raw_downstream_body(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(
        client,
        FakeOptimizerClient(
            exc=ExternalServiceError(
                "Optimizer API returned 500: private_key=SHOULD_NOT_LEAK"
            )
        ),
    )

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["error_code"] == "OPTIMIZER_ERROR"
    assert "SHOULD_NOT_LEAK" not in str(payload)
    assert db_session.query(CostCalculationRun).count() == 0


def test_select_for_deployment_marks_run_and_preserves_compatibility(
    authenticated_client,
    db_session,
    sample_calc_params,
):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    _override_optimizer(client, FakeOptimizerClient())
    create_response = client.post(
        f"/twins/{twin_id}/optimizer-runs/",
        json={"params": sample_calc_params},
        headers=headers,
    )
    run_id = create_response.json()["id"]

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/{run_id}/select-for-deployment",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["run"]["selected_for_deployment_at"] is not None
    config = db_session.query(OptimizerConfiguration).filter_by(twin_id=twin_id).one()
    assert config.cheapest_l1 == "AWS"
    assert config.cheapest_l3_archive == "Azure"


def test_select_for_deployment_rejects_failed_run(authenticated_client, db_session):
    client, headers = authenticated_client
    twin_id = create_test_twin(client, headers)
    dev_user = db_session.query(User).filter_by(email="dev@example.com").one()
    failed = CostCalculationRun(
        twin_id=twin_id,
        user_id=dev_user.id,
        status="failed",
        params_json="{}",
        optimization_profile_id="cost_minimization_v1",
        scoring_strategy_id="min_total_cost_v1",
        currency="USD",
    )
    db_session.add(failed)
    db_session.commit()
    db_session.refresh(failed)

    response = client.post(
        f"/twins/{twin_id}/optimizer-runs/{failed.id}/select-for-deployment",
        headers=headers,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_run_rolls_back_run_items_and_compatibility_on_db_failure(
    db_session,
    sample_calc_params,
):
    user = User(email="rollback@example.com", name="Rollback")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    twin = DigitalTwin(name="Rollback Twin", user_id=user.id, state=TwinState.DRAFT)
    db_session.add(twin)
    db_session.commit()
    db_session.refresh(twin)

    class FailingService(CostCalculationRunService):
        def _before_commit(self):
            raise RuntimeError("forced persistence failure")

    service = FailingService(db_session, optimizer_client=FakeOptimizerClient())

    with pytest.raises(RuntimeError):
        await service.create_run(twin.id, user.id, sample_calc_params)

    assert db_session.query(CostCalculationRun).count() == 0
    assert db_session.query(OptimizerConfiguration).filter_by(twin_id=twin.id).count() == 0
