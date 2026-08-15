import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from rest_api import app
from api.calculation import (
    CalcParams,
    FiveLayerV2CalcParams,
    _calculate_five_layer_v2,
    _five_layer_v2_http_result,
)
from backend.architecture_profiles.diagnostics import (
    ArchitectureResolutionError,
    RejectionCollector,
)
from backend.architecture_profiles.activation import (
    architecture_profile_resolution_enabled,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry
from backend.architecture_profiles.five_layer_v2_workload import (
    CONTRACT_ROOT as FIVE_LAYER_V2_WORKLOAD_ROOT,
)
from backend.calculation_v2.transfer_pricing import TransferPricingContractError
from backend.pricing_catalog_models import PricingCatalogContext
from backend.pricing_catalog_repository import (
    PricingCatalogStaleError,
    get_pricing_catalog_repository,
)
from backend.pricing_catalog_resolver import ResolvedPricingCatalogs

client = TestClient(app)


@pytest.fixture(autouse=True)
def _legacy_calculation_tests_opt_out_of_architecture_resolution(monkeypatch):
    """Keep non-architecture endpoint tests scoped to their original boundary."""

    monkeypatch.setenv("ARCHITECTURE_PROFILE_RESOLUTION_ENABLED", "false")


def _catalog_context() -> PricingCatalogContext:
    repository = get_pricing_catalog_repository()
    return PricingCatalogContext(
        catalogs={
            provider: repository.resolve_baseline(
                provider,
                require_fresh=False,
            ).reference
            for provider in ("aws", "azure", "gcp")
        }
    )


def _resolved_catalogs(pricing: dict) -> ResolvedPricingCatalogs:
    return ResolvedPricingCatalogs(
        pricing=pricing,
        context=_catalog_context(),
    )


def _valid_payload():
    return {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0,
        "providerPricingCatalogs": _catalog_context().to_http_dict(),
    }


def _architecture_fields() -> dict:
    registry = ArchitectureProfileRegistry()
    return {
        "architectureProfile": {
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        "extensionBindings": [
            {
                "slotId": "processor.telemetry",
                "slotVersion": "1",
                "artifactId": "artifact.user.processor.example",
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": "sha256:" + ("2" * 64),
            }
        ],
    }


def _five_layer_v2_payload() -> dict:
    registry = ArchitectureProfileRegistry(profile_version="2")
    workload = json.loads(
        (
            FIVE_LAYER_V2_WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json"
        ).read_text(encoding="utf-8")
    )
    return {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        **workload,
        "optimizationProfileId": "cost-minimization-v2",
        "providerPricingCatalogs": _catalog_context().to_http_dict(),
        "providerPricingContexts": {
            "awsTwinMaker": {
                "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
                "status": "available",
                "sourceRefreshRunId": "aws-refresh-v2",
                "connectionFingerprint": "sha256:" + ("a" * 64),
                "providerAccountId": "123456789012",
                "pricingRegion": "eu-central-1",
                "catalogSnapshotDigest": "sha256:" + ("b" * 64),
                "observedAt": "2026-08-04T12:00:00Z",
                "currentPlan": {
                    "mode": "STANDARD",
                    "billableEntityCount": 100,
                    "effectiveAt": None,
                    "updatedAt": None,
                    "updateReason": None,
                    "bundle": None,
                },
                "pendingPlan": None,
            }
        },
        "architectureProfile": {
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        "extensionBindings": [
            {
                "slotId": "processor.telemetry",
                "slotVersion": "1",
                "artifactId": "artifact.user.processor.example",
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": "sha256:" + ("2" * 64),
            }
        ],
    }


def _six_layer_v1_payload() -> dict:
    payload = _five_layer_v2_payload()
    registry = ArchitectureProfileRegistry(
        profile_id="six-layer-eventing",
        profile_version="1",
    )
    payload["architectureProfile"] = {
        "profileId": registry.profile["profile_id"],
        "profileVersion": registry.profile["profile_version"],
        "contentDigest": registry.profile["content_digest"],
    }
    return payload


def test_five_layer_v2_request_has_a_distinct_strict_shape():
    payload = _five_layer_v2_payload()

    parsed = FiveLayerV2CalcParams.model_validate(payload)

    assert parsed.workload_payload()["schemaVersion"] == "five-layer-workload.v2"
    assert "useEventChecking" not in parsed.workload_payload()


def test_five_layer_v2_request_rejects_retired_event_flags():
    payload = _five_layer_v2_payload()
    payload["useEventChecking"] = True

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422


def test_five_layer_v2_request_rejects_coerced_numeric_fields():
    payload = _five_layer_v2_payload()
    payload["numberOfDevices"] = "100"

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422


def test_five_layer_v2_request_rejects_custom_scenario_values():
    payload = _five_layer_v2_payload()
    payload["numberOfDevices"] = 101

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422
    assert "immutable Small, Medium, or Large" in response.text


def test_five_layer_v2_api_path_remains_dark_while_activation_gate_is_off():
    response = client.put("/calculate", json=_five_layer_v2_payload())

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == (
        "ARCH_PROFILE_BUNDLE_INCOMPATIBLE"
    )


@patch("api.calculation.optimize_five_layer_v2")
@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_five_layer_v2_api_path_is_active_by_default(
    resolve_catalogs,
    optimize,
    monkeypatch,
):
    monkeypatch.delenv("ARCHITECTURE_PROFILE_RESOLUTION_ENABLED", raising=False)
    resolve_catalogs.return_value = _resolved_catalogs({})
    optimize.return_value = SimpleNamespace(
        resolved_architecture={
            "component_assignments": [
                {"logical_component_id": logical, "provider": "aws"}
                for logical in (
                    "component.ingestion",
                    "component.processing",
                    "component.hot-storage",
                    "component.cool-storage",
                    "component.archive-storage",
                    "component.twin-state",
                    "component.visualization",
                )
            ]
        },
        deployment_specification={
            "schema_version": "resolved-deployment-specification.v2"
        },
        cost_evaluation=SimpleNamespace(
            monthly_total=Decimal("0"),
            currency="USD",
        ),
        cost_ledger={
            "schema_version": "five-layer-v2-cost-ledger.v1",
            "currency": "USD",
            "component_costs": [],
            "route_costs": [],
        },
        winning_candidate_id="candidate.single-cloud-aws-small",
        enumerated_candidate_count=1,
        costed_candidate_count=1,
        rejected_by_error_code=(),
    )

    response = client.put("/calculate", json=_five_layer_v2_payload())

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["optimization_profile_id"] == "cost-minimization-v2"
    assert result["resolvedDeploymentSpecification"]["schema_version"] == (
        "resolved-deployment-specification.v2"
    )
    assert optimize.call_args.kwargs["resolution_status"] == (
        "offline_contract_fixture"
    )


@patch("api.calculation.optimize_six_layer_eventing_v1")
@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_six_layer_v1_api_dispatches_exact_profile_and_exposes_eventing(
    resolve_catalogs,
    optimize,
    monkeypatch,
):
    monkeypatch.delenv("ARCHITECTURE_PROFILE_RESOLUTION_ENABLED", raising=False)
    resolve_catalogs.return_value = _resolved_catalogs({})
    optimize.return_value = SimpleNamespace(
        resolved_architecture={
            "component_assignments": [
                {"logical_component_id": logical, "provider": "azure"}
                for logical in (
                    "component.ingestion",
                    "component.processing",
                    "component.hot-storage",
                    "component.cool-storage",
                    "component.archive-storage",
                    "component.twin-state",
                    "component.visualization",
                    "component.eventing",
                )
            ]
        },
        deployment_specification={
            "schema_version": "resolved-deployment-specification.v2"
        },
        cost_evaluation=SimpleNamespace(
            monthly_total=Decimal("1.5"),
            currency="USD",
        ),
        cost_ledger={
            "schema_version": "five-layer-v2-cost-ledger.v1",
            "currency": "USD",
            "component_costs": [],
            "route_costs": [],
        },
        winning_candidate_id="azure|azure|azure|azure|azure|azure|azure|azure",
        enumerated_candidate_count=1,
        costed_candidate_count=1,
        rejected_by_error_code=(),
    )

    response = client.put("/calculate", json=_six_layer_v1_payload())

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["calculationResult"]["Eventing"] == "Azure"
    assert result["cheapestPath"][-1] == "Eventing_Azure"
    assert optimize.call_args.kwargs["architecture_profile"]["profileId"] == (
        "six-layer-eventing"
    )
    assert optimize.call_args.kwargs["resolution_status"] == (
        "offline_contract_fixture"
    )


def test_five_layer_v2_http_projection_uses_the_actual_winning_candidate():
    params = FiveLayerV2CalcParams.model_validate(_five_layer_v2_payload())
    assignments = {
        "component.ingestion": "aws",
        "component.processing": "azure",
        "component.hot-storage": "gcp",
        "component.cool-storage": "aws",
        "component.archive-storage": "azure",
        "component.twin-state": "aws",
        "component.visualization": "gcp",
    }
    optimized = SimpleNamespace(
        resolved_architecture={
            "component_assignments": [
                {"logical_component_id": key, "provider": value}
                for key, value in assignments.items()
            ]
        },
        deployment_specification={
            "schema_version": "resolved-deployment-specification.v2"
        },
        cost_evaluation=SimpleNamespace(
            monthly_total=Decimal("12.5"),
            currency="USD",
        ),
        cost_ledger={
            "schema_version": "five-layer-v2-cost-ledger.v1",
            "currency": "USD",
            "component_costs": [],
            "route_costs": [],
        },
        winning_candidate_id="candidate.actual-winner",
        enumerated_candidate_count=729,
        costed_candidate_count=700,
        rejected_by_error_code=(("ARCH_PRICING_EVIDENCE_MISSING", 29),),
    )

    result = _five_layer_v2_http_result(params, optimized)

    assert result["calculationResult"]["L3"]["Hot"] == "GCP"
    assert result["calculationResult"]["L4"] == "AWS"
    assert result["totalCostExact"] == "12.5"
    assert result["providerPricingContexts"]["awsTwinMaker"]["status"] == ("compatible")
    assert result["costLedger"]["schema_version"] == ("five-layer-v2-cost-ledger.v1")
    assert (
        result["architectureResolutionDiagnostics"]["winningCandidateId"]
        == "candidate.actual-winner"
    )


@patch("api.calculation.optimize_five_layer_v2")
def test_five_layer_v2_unsupervised_api_path_requests_offline_evidence(
    optimize,
):
    params = FiveLayerV2CalcParams.model_validate(_five_layer_v2_payload())
    captured = {}

    def stop_after_capture(**kwargs):
        captured.update(kwargs)
        raise RuntimeError("captured optimizer boundary")

    optimize.side_effect = stop_after_capture

    with pytest.raises(RuntimeError, match="captured optimizer boundary"):
        _calculate_five_layer_v2(
            params,
            resolved_catalogs=_resolved_catalogs({}),
        )

    assert captured["resolution_status"] == "offline_contract_fixture"
    assert "satisfied_live_gate_ids" not in captured
    assert {
        provider: {
            "id": reference["id"],
            "version": reference["version"],
            "digest": reference["digest"],
        }
        for provider, reference in captured["pricing_evidence_refs"].items()
    } == {
        provider: {
            "id": catalog.snapshot_id,
            "version": "1",
            "digest": catalog.content_digest,
        }
        for provider, catalog in _catalog_context().catalogs.items()
    }


# -----------------------------------------------------------------------------
# 1. Input Validation Edge Cases
# -----------------------------------------------------------------------------


def test_calculate_missing_fields():
    """Test that missing required fields returns 422 Unprocessable Entity."""
    # Sending empty body
    response = client.put("/calculate", json={})
    assert response.status_code == 422
    data = response.json()
    # Check that at least one field is missing (e.g., numberOfDevices)
    # detail is a list of dicts
    assert any(err["loc"][-1] == "numberOfDevices" for err in data["detail"])


def test_calculate_rejects_invalid_calculation_run_id():
    payload = _valid_payload()
    payload["calculationRunId"] = "not-a-uuid"

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "calculationRunId" for error in response.json()["detail"]
    )


def test_calculate_invalid_data_types():
    """Test sending string for integer field returns 422."""
    payload = {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        "numberOfDevices": "one_hundred",  # Invalid
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0,
        "providerPricingCatalogs": _catalog_context().to_http_dict(),
    }
    response = client.put("/calculate", json=payload)
    assert response.status_code == 422
    # Check for type error message
    assert (
        "valid integer" in response.text.lower()
        or "valid number" in response.text.lower()
    )


def test_calculate_negative_values():
    """Test validation of negative values where positive are required."""
    payload = {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        "numberOfDevices": -50,  # Invalid
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0,
        "providerPricingCatalogs": _catalog_context().to_http_dict(),
    }
    response = client.put("/calculate", json=payload)
    assert response.status_code == 422


def test_calculate_storage_duration_logic_ordering():
    """Test logic: Hot <= Cool <= Archive."""
    payload = {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 4,  # > Cool (3)
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,  # Valid >= 6
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0,
        "providerPricingCatalogs": _catalog_context().to_http_dict(),
    }
    response = client.put("/calculate", json=payload)
    assert response.status_code == 422
    # Pydantic returns details in JSON
    # Msg: "Value error, Hot storage duration (4) must be <= Cool storage duration (3)"
    assert "Hot storage duration" in response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("averageDigitalTwinQueryUnitsPerQuery", 0),
        ("averageDigitalTwinQueryResponseSizeInKb", 0),
        ("averageDigitalTwinQueryUnitsPerQuery", "invalid"),
        ("averageDigitalTwinQueryResponseSizeInKb", "invalid"),
        ("averageDigitalTwinQueryUnitsPerQuery", "1.0"),
        ("averageDigitalTwinQueryResponseSizeInKb", "1.0"),
    ],
)
def test_calculate_rejects_invalid_adt_assumptions(field, value):
    payload = _valid_payload()
    payload[field] = value

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422


def test_calculate_rejects_unknown_fields():
    response = client.put(
        "/calculate",
        json={**_valid_payload(), "legacyOptimizerFlag": True},
    )

    assert response.status_code == 422


def test_calculate_rejects_unsupported_error_handling_topology():
    payload = _valid_payload()
    payload["integrateErrorHandling"] = True

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(
        error["loc"][-1] == "integrateErrorHandling"
        and error["type"] == "UNSUPPORTED_ERROR_HANDLING_TOPOLOGY"
        for error in errors
    )


@pytest.mark.parametrize("payload_value", [False, None])
def test_calculate_accepts_false_or_omitted_error_handling_topology(
    payload_value,
):
    payload = _valid_payload()
    if payload_value is not None:
        payload["integrateErrorHandling"] = payload_value

    params = CalcParams.model_validate(payload)

    assert params.integrateErrorHandling is False


# -----------------------------------------------------------------------------
# 2. Engine Robustness / Error Handling
# -----------------------------------------------------------------------------


@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_calculate_load_pricing_failure(mock_resolve_pricing):
    """Test 500 behavior when pricing load completely fails."""
    mock_resolve_pricing.side_effect = Exception("Disk failure simulation")

    payload = {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0,
        "providerPricingCatalogs": _catalog_context().to_http_dict(),
    }

    response = client.put("/calculate", json=payload)
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Calculation failed" in data["detail"]


@patch("backend.calculation_v2.engine.calculate_cheapest_costs")
@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_calculate_engine_internal_error(mock_resolve, mock_engine):
    """Test behavior when engine raises an unexpected error."""
    # PATCH TARGET: backend.calculation_v2.engine.calculate_cheapest_costs
    # Because api/calculation.py imports it locally inside the function 'calc'
    mock_resolve.return_value = _resolved_catalogs({})
    mock_engine.side_effect = ValueError("Calculation logic exploded")

    payload = {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 0,
        "amountOfActiveEditors": 0,
        "amountOfActiveViewers": 0,
        "dashboardRefreshesPerHour": 0,
        "dashboardActiveHoursPerDay": 0,
        "providerPricingCatalogs": _catalog_context().to_http_dict(),
    }

    response = client.put("/calculate", json=payload)
    # ValueError is caught as a 400 by the handler (not 500)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Calculation logic exploded" in data["detail"]


@patch("backend.calculation_v2.engine.calculate_cheapest_costs")
@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_calculate_returns_structured_transfer_contract_conflict(
    mock_resolve,
    mock_engine,
):
    mock_resolve.return_value = _resolved_catalogs({})
    mock_engine.side_effect = TransferPricingContractError(
        "TRANSFER_NO_COMPLETE_PATH",
        "no complete baseline path satisfies the transfer contract",
    )

    response = client.put("/calculate", json=_valid_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "error_code": "TRANSFER_NO_COMPLETE_PATH",
        "message": "no complete baseline path satisfies the transfer contract",
        "fix_suggestion": (
            "Review the selected provider regions, transfer-route contract, "
            "and published transfer pricing evidence."
        ),
        "http_status": 409,
    }


# -----------------------------------------------------------------------------
# 3. Feature Toggle Verification
# -----------------------------------------------------------------------------


def test_architecture_resolution_is_enabled_by_default(monkeypatch):
    monkeypatch.delenv(
        "ARCHITECTURE_PROFILE_RESOLUTION_ENABLED",
        raising=False,
    )

    assert architecture_profile_resolution_enabled() is True


@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_architecture_resolution_gate_off_rejects_profile_fields(
    mock_resolve_pricing,
    monkeypatch,
):
    monkeypatch.setenv(
        "ARCHITECTURE_PROFILE_RESOLUTION_ENABLED",
        "false",
    )

    response = client.put(
        "/calculate",
        json={**_valid_payload(), **_architecture_fields()},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == (
        "ARCH_PROFILE_BUNDLE_INCOMPATIBLE"
    )
    mock_resolve_pricing.assert_not_called()


def test_architecture_resolution_gate_on_never_falls_back_to_legacy(
    monkeypatch,
):
    monkeypatch.setenv(
        "ARCHITECTURE_PROFILE_RESOLUTION_ENABLED",
        "true",
    )

    response = client.put("/calculate", json=_valid_payload())

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == (
        "ARCH_PROFILE_BUNDLE_INCOMPATIBLE"
    )


@patch("backend.calculation_v2.engine.calculate_cheapest_costs")
@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_architecture_resolution_gate_on_passes_trusted_context_only(
    mock_resolve_pricing,
    mock_engine,
    monkeypatch,
    caplog,
):
    monkeypatch.setenv(
        "ARCHITECTURE_PROFILE_RESOLUTION_ENABLED",
        "true",
    )
    mock_resolve_pricing.return_value = _resolved_catalogs({})
    mock_engine.return_value = {
        "architectureResolutionDiagnostics": {
            "enumeratedCandidateCount": 128,
            "admissibleCandidateCount": 3,
            "rejectedCandidateCount": 125,
            "winningCandidateId": "aws|aws|aws|aws|aws|aws|aws",
        }
    }

    with caplog.at_level("INFO", logger="digital_twin"):
        response = client.put(
            "/calculate",
            json={**_valid_payload(), **_architecture_fields()},
            headers={"X-Request-ID": "phase-8.5-request"},
        )

    assert response.status_code == 200
    params_arg = mock_engine.call_args.args[0]
    kwargs = mock_engine.call_args.kwargs
    assert "architectureProfile" not in params_arg
    assert "extensionBindings" not in params_arg
    assert kwargs["architecture_context"].profile_ref.profile_id == (
        "five-layer-baseline"
    )
    assert "architecture_resolution outcome=success" in caplog.text
    assert "correlation_id=phase-8.5-request" in caplog.text
    assert "enumerated_candidate_count=128" in caplog.text
    assert "admissible_candidate_count=3" in caplog.text
    assert "rejected_candidate_count=125" in caplog.text
    assert "winner_candidate_id=aws|aws|aws|aws|aws|aws|aws" in caplog.text
    assert "numberOfDevices" not in caplog.text
    assert "providerPricingCatalogs" not in caplog.text


@patch("backend.calculation_v2.engine.calculate_cheapest_costs")
@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_architecture_resolution_errors_use_stable_conflict_envelope(
    mock_resolve_pricing,
    mock_engine,
    monkeypatch,
    caplog,
):
    monkeypatch.setenv(
        "ARCHITECTURE_PROFILE_RESOLUTION_ENABLED",
        "true",
    )
    mock_resolve_pricing.return_value = _resolved_catalogs({})
    rejections = RejectionCollector()
    for index in range(125):
        rejections.record(
            "ARCH_EDGE_IMPLEMENTATION_MISSING",
            f"candidate:{index}",
        )
    mock_engine.side_effect = ArchitectureResolutionError(
        "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
        "providerProfiles",
        "No active supported provider profile is available",
        enumerated_candidate_count=128,
        admissible_candidate_count=0,
        diagnostics=rejections.freeze(),
    )

    with caplog.at_level("WARNING", logger="digital_twin"):
        response = client.put(
            "/calculate",
            json={**_valid_payload(), **_architecture_fields()},
            headers={"X-Request-ID": "phase-8.5-error"},
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert {key: value for key, value in detail.items() if key != "diagnostics"} == {
        "error_code": "ARCH_PROVIDER_IMPLEMENTATION_MISSING",
        "message": "No active supported provider profile is available",
        "fix_suggestion": (
            "Use the exact active Management-owned architecture profile and "
            "extension references, then retry."
        ),
        "http_status": 409,
    }
    assert detail["diagnostics"]["enumeratedCandidateCount"] == 128
    assert detail["diagnostics"]["admissibleCandidateCount"] == 0
    assert detail["diagnostics"]["rejectedCandidateCount"] == 125
    assert detail["diagnostics"]["rejectedByErrorCode"] == {
        "ARCH_EDGE_IMPLEMENTATION_MISSING": 125
    }
    assert len(detail["diagnostics"]["representativeCandidateIds"]) == 25
    assert "architecture_resolution outcome=failure" in caplog.text
    assert "correlation_id=phase-8.5-error" in caplog.text
    assert "enumerated_candidate_count=128" in caplog.text
    assert "rejected_candidate_count=125" in caplog.text
    assert "error_code=ARCH_PROVIDER_IMPLEMENTATION_MISSING" in caplog.text
    assert "No active supported provider profile is available" not in caplog.text


@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_feature_toggle_gcp_l4_disabled(mock_resolve_pricing):
    """Verify that disabling 'allowGcpSelfHostedL4' in params passes correct flag to engine."""

    # We patch the ENGINE function (backend.calculation_v2.engine.calculate_cheapest_costs)
    # to inspect arguments passed to it.
    with patch("backend.calculation_v2.engine.calculate_cheapest_costs") as mock_calc:
        mock_calc.return_value = {}
        mock_resolve_pricing.return_value = _resolved_catalogs({})

        payload = {
            "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
            "numberOfDevices": 100,
            "deviceSendingIntervalInMinutes": 2.0,
            "averageSizeOfMessageInKb": 0.25,
            "hotStorageDurationInMonths": 1,
            "coolStorageDurationInMonths": 3,
            "archiveStorageDurationInMonths": 12,
            "needs3DModel": False,
            "entityCount": 0,
            "amountOfActiveEditors": 0,
            "amountOfActiveViewers": 0,
            "dashboardRefreshesPerHour": 0,
            "dashboardActiveHoursPerDay": 0,
            "allowGcpSelfHostedL4": False,  # Flag
            "allowGcpSelfHostedL5": False,
            "providerPricingCatalogs": _catalog_context().to_http_dict(),
        }

        client.put("/calculate", json=payload)

        # Verify call args
        args, kwargs = mock_calc.call_args
        params_arg = args[0]
        assert params_arg["allowGcpSelfHostedL4"] is False
        assert params_arg["allowGcpSelfHostedL5"] is False
        assert kwargs["pricing_catalog_context"] == _catalog_context()
        assert "architecture_context" not in kwargs


@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_calculate_response_exposes_additive_trace_metadata(mock_resolve_pricing):
    """The public calculate endpoint exposes read-only intent trace metadata."""
    from tests.unit.calculation_v2.test_intent_to_result_traceability import (
        _sample_pricing,
    )

    mock_resolve_pricing.return_value = _resolved_catalogs(_sample_pricing())
    payload = {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 1,
        "amountOfActiveEditors": 2,
        "amountOfActiveViewers": 5,
        "dashboardRefreshesPerHour": 4,
        "dashboardActiveHoursPerDay": 8,
        "allowGcpSelfHostedL4": False,
        "allowGcpSelfHostedL5": False,
        "providerPricingCatalogs": _catalog_context().to_http_dict(),
    }

    response = client.put("/calculate", json=payload)

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["trace_schema_version"] == "intent-result-trace.v1"
    assert result["intentTrace"]["summary"]["record_count"] > 0
    assert result["intentTrace"]["profile"]["profile_id"] == "cost_minimization_v1"
    assert result["intentTrace"]["workload"]["assumption_sources"] == {
        "averageDigitalTwinQueryUnitsPerQuery": "compatibility_default",
        "averageDigitalTwinQueryResponseSizeInKb": "compatibility_default",
    }
    assert result["pricingCatalogs"] == _catalog_context().to_http_dict()


@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_calculate_preserves_explicit_adt_assumptions_in_trace(
    mock_resolve_pricing,
):
    from tests.unit.calculation_v2.test_intent_to_result_traceability import (
        _sample_pricing,
    )

    mock_resolve_pricing.return_value = _resolved_catalogs(_sample_pricing())
    payload = {
        **_valid_payload(),
        "dashboardRefreshesPerHour": 2,
        "dashboardActiveHoursPerDay": 1,
        "averageDigitalTwinQueryUnitsPerQuery": 2.5,
        "averageDigitalTwinQueryResponseSizeInKb": 1.1,
    }

    response = client.put("/calculate", json=payload)

    assert response.status_code == 200
    workload = response.json()["result"]["intentTrace"]["workload"]
    assert workload["inputs"]["averageDigitalTwinQueryUnitsPerQuery"] == 2.5
    assert workload["inputs"]["averageDigitalTwinQueryResponseSizeInKb"] == 1.1
    assert workload["assumption_sources"] == {
        "averageDigitalTwinQueryUnitsPerQuery": "explicit_input",
        "averageDigitalTwinQueryResponseSizeInKb": "explicit_input",
    }
    assert workload["derived"]["queries_per_month"] == 60
    assert workload["derived"]["digital_twin_query_response_operations"] == 120
    assert workload["derived"]["monthly_digital_twin_query_units"] == 150


def test_calculate_rejects_unimplemented_gcp_self_hosted_paths():
    payload = {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 1,
        "amountOfActiveEditors": 2,
        "amountOfActiveViewers": 5,
        "dashboardRefreshesPerHour": 4,
        "dashboardActiveHoursPerDay": 8,
        "allowGcpSelfHostedL4": True,
        "providerPricingCatalogs": _catalog_context().to_http_dict(),
    }

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422
    assert "cannot be enabled" in response.text


@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_calculate_rejects_stale_exact_catalog_context(mock_resolve_pricing):
    mock_resolve_pricing.side_effect = PricingCatalogStaleError(
        "Pricing catalog snapshot is stale"
    )

    response = client.put("/calculate", json=_valid_payload())

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "PRICING_CATALOG_STALE"


def test_calculate_rejects_tampered_catalog_reference_identity():
    payload = _valid_payload()
    payload["providerPricingCatalogs"]["catalogs"]["azure"]["snapshotId"] = "pcs_" + (
        "0" * 64
    )

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422
    assert "snapshot_id does not match reference identity" in response.text
