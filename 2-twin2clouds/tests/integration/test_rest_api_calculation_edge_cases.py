"""Integration boundaries for the standalone Six-layer calculation API."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.calculation import (
    SixLayerCalcParams,
    _calculate_six_layer,
    _six_layer_http_result,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry
from backend.architecture_profiles.six_layer_workload import (
    CONTRACT_ROOT as SIX_LAYER_WORKLOAD_ROOT,
)
from backend.pricing_catalog_models import PricingCatalogContext
from backend.pricing_catalog_repository import get_pricing_catalog_repository
from backend.pricing_catalog_resolver import ResolvedPricingCatalogs
from rest_api import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def _explicit_architecture_activation(monkeypatch):
    """Keep the default path explicit while allowing the dark-gate test."""

    monkeypatch.setenv("ARCHITECTURE_PROFILE_RESOLUTION_ENABLED", "true")


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
    return ResolvedPricingCatalogs(pricing=pricing, context=_catalog_context())


def _six_layer_payload() -> dict:
    registry = ArchitectureProfileRegistry(
        profile_id="six-layer-eventing",
        profile_version="1",
    )
    workload = json.loads(
        (SIX_LAYER_WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json").read_text(
            encoding="utf-8"
        )
    )
    return {
        "calculationRunId": "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01",
        **workload,
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


def _optimized(assignments: dict[str, str], *, total: str = "1.5"):
    return SimpleNamespace(
        resolved_architecture={
            "component_assignments": [
                {"logical_component_id": logical, "provider": provider}
                for logical, provider in assignments.items()
            ]
        },
        deployment_specification={
            "schema_version": "resolved-deployment-specification.v2"
        },
        cost_evaluation=SimpleNamespace(
            monthly_total=Decimal(total),
            currency="USD",
        ),
        cost_ledger={
            "schema_version": "six-layer-cost-ledger.v1",
            "currency": "USD",
            "component_costs": [],
            "route_costs": [],
        },
        winning_candidate_id="candidate.fixture",
        enumerated_candidate_count=1,
        costed_candidate_count=1,
        rejected_by_error_code=(),
    )


def _all_aws_assignments() -> dict[str, str]:
    return {
        logical: "aws"
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
    }


def test_six_layer_request_has_a_distinct_strict_shape():
    parsed = SixLayerCalcParams.model_validate(_six_layer_payload())

    assert parsed.workload_payload()["schemaVersion"] == "six-layer-workload.v1"
    assert "useEventChecking" not in parsed.workload_payload()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("useEventChecking", True),
        ("numberOfDevices", "100"),
        ("unknownField", True),
    ],
)
def test_six_layer_request_rejects_retired_coerced_and_unknown_fields(field, value):
    payload = _six_layer_payload()
    payload[field] = value

    assert client.put("/calculate", json=payload).status_code == 422


def test_six_layer_request_rejects_custom_scenario_values():
    payload = _six_layer_payload()
    payload["numberOfDevices"] = 101

    response = client.put("/calculate", json=payload)

    assert response.status_code == 422
    assert "immutable Small, Medium, or Large" in response.text


def test_six_layer_api_path_remains_dark_while_activation_gate_is_off(monkeypatch):
    monkeypatch.setenv("ARCHITECTURE_PROFILE_RESOLUTION_ENABLED", "false")

    response = client.put("/calculate", json=_six_layer_payload())

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == (
        "ARCH_PROFILE_BUNDLE_INCOMPATIBLE"
    )


@patch("api.calculation.optimize_six_layer_eventing_v1")
@patch("api.calculation.PricingCatalogResolver.resolve_context")
def test_six_layer_api_dispatches_exact_standalone_profile(
    resolve_catalogs,
    optimize,
):
    resolve_catalogs.return_value = _resolved_catalogs({})
    optimize.return_value = _optimized(_all_aws_assignments())

    response = client.put("/calculate", json=_six_layer_payload())

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["calculationResult"]["Eventing"] == "AWS"
    assert result["cheapestPath"][-1] == "Eventing_AWS"
    assert result["resolvedDeploymentSpecification"]["schema_version"] == (
        "resolved-deployment-specification.v2"
    )
    assert optimize.call_args.kwargs["architecture_profile"]["profileId"] == (
        "six-layer-eventing"
    )
    assert optimize.call_args.kwargs["architecture_profile"]["profileVersion"] == "1"
    assert optimize.call_args.kwargs["resolution_status"] == (
        "offline_contract_fixture"
    )


def test_six_layer_http_projection_uses_the_actual_winning_candidate():
    params = SixLayerCalcParams.model_validate(_six_layer_payload())
    assignments = {
        "component.ingestion": "aws",
        "component.processing": "azure",
        "component.hot-storage": "gcp",
        "component.cool-storage": "aws",
        "component.archive-storage": "azure",
        "component.twin-state": "aws",
        "component.visualization": "gcp",
        "component.eventing": "azure",
    }
    optimized = _optimized(assignments, total="12.5")
    optimized.winning_candidate_id = "candidate.actual-winner"
    optimized.enumerated_candidate_count = 729
    optimized.costed_candidate_count = 700
    optimized.rejected_by_error_code = (("ARCH_PRICING_EVIDENCE_MISSING", 29),)

    result = _six_layer_http_result(params, optimized)

    assert result["calculationResult"]["L3"]["Hot"] == "GCP"
    assert result["calculationResult"]["L4"] == "AWS"
    assert result["calculationResult"]["Eventing"] == "Azure"
    assert result["totalCostExact"] == "12.5"
    assert result["providerPricingContexts"]["awsTwinMaker"]["status"] == ("compatible")
    assert result["costLedger"]["schema_version"] == "six-layer-cost-ledger.v1"
    assert (
        result["architectureResolutionDiagnostics"]["winningCandidateId"]
        == "candidate.actual-winner"
    )


@patch("api.calculation.optimize_six_layer_eventing_v1")
def test_six_layer_unsupervised_api_path_requests_offline_evidence(optimize):
    params = SixLayerCalcParams.model_validate(_six_layer_payload())
    captured = {}

    def stop_after_capture(**kwargs):
        captured.update(kwargs)
        raise RuntimeError("captured optimizer boundary")

    optimize.side_effect = stop_after_capture

    with pytest.raises(RuntimeError, match="captured optimizer boundary"):
        _calculate_six_layer(params, resolved_catalogs=_resolved_catalogs({}))

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
