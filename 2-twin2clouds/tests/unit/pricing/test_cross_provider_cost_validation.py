from copy import deepcopy

from backend.cross_provider_cost_validation import (
    FAILED,
    NON_APPLICABLE,
    PUBLISHABLE,
    REVIEW_REQUIRED,
    build_cross_provider_cost_validation,
)
from backend.pricing_evidence import FALLBACK_STATIC, FETCHED, NOT_APPLICABLE


class FakeRegistryService:
    def __init__(self, intents=None):
        self.intents = intents or {
            "functions.request": {
                "group": "cost",
                "description": "Serverless function request",
                "normalized_unit": "request",
                "expected_providers": ["aws", "azure", "gcp"],
            },
            "transfer.egress_gb": {
                "group": "cost",
                "description": "Egress transfer",
                "normalized_unit": "gb",
                "expected_providers": ["aws", "azure", "gcp"],
            },
        }

    def list_intents(self, metric=None):
        assert metric in (None, "cost")
        return deepcopy(self.intents)

    def list_intent_groups(self):
        return {"cost": {"metric": "cost", "enabled": True}}

    def get_registry_version(self):
        return "test-registry.v1"


def _record(
    provider,
    intent_id,
    *,
    unit,
    source_type=FETCHED,
    review_required=False,
    selected=True,
):
    return {
        "schema_version": "pricing-evidence.v1",
        "provider": provider,
        "intent_id": intent_id,
        "field_path": intent_id,
        "source_type": source_type,
        "source_api": f"{provider}-api",
        "request_scope": {"provider": provider, "region": "test-region"},
        "normalization_rule": f"per_{unit}",
        "normalization": {"target_unit": unit},
        "normalized_value": 0.01 if source_type != NOT_APPLICABLE else None,
        "currency": "USD" if source_type != NOT_APPLICABLE else None,
        "mapping_version": "2026.06.08",
        "registry_version": "test-registry.v1",
        "fetched_at": "2026-06-08T13:00:00Z",
        "review_required": review_required,
        "match_status": "matched" if selected else "missing",
        "selected_row": (
            {
                "candidate_id": f"{provider}-{intent_id}",
                "skuId": f"{provider}-sku",
                "unit": unit,
                "description": intent_id,
            }
            if selected and source_type != NOT_APPLICABLE
            else None
        ),
        "candidate_rows": [],
        "rejected_rows": [],
        "errors": [],
    }


def _reports(*, source_type=FETCHED, review_required=False, unit_overrides=None):
    unit_overrides = unit_overrides or {}
    reports = {}
    for provider in ("aws", "azure", "gcp"):
        records = [
            _record(
                provider,
                "functions.request",
                unit=unit_overrides.get((provider, "functions.request"), "request"),
                source_type=source_type,
                review_required=review_required,
            ),
            _record(
                provider,
                "transfer.egress_gb",
                unit=unit_overrides.get((provider, "transfer.egress_gb"), "gb"),
                source_type=source_type,
                review_required=review_required,
            ),
        ]
        reports[provider] = {"provider": provider, "records": records}
    return reports


def _calculation_result():
    return {
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
            "pricing_registry_version": "test-registry.v1",
        },
        "evidenceReferences": {
            "pricing_registry": "pricing_registry:test-registry.v1",
            "pricing_evidence_contract": "pricing-evidence.v1",
            "intent_group_ids": ["cost"],
        },
        "calculationResult": {"L1": "AWS"},
        "cheapestPath": ["L1_AWS"],
        "totalCost": 1.23,
    }


def test_cross_provider_validation_is_publishable_with_complete_compatible_evidence():
    summary = build_cross_provider_cost_validation(
        _reports(),
        pricing_registry_service=FakeRegistryService(),
        calculation_result=_calculation_result(),
    )

    assert summary["status"] == PUBLISHABLE
    assert summary["publishable"] is True
    assert summary["intent_count"] == 2
    assert summary["counts"]["provider_statuses"][PUBLISHABLE] == 6
    assert summary["management_run_compatibility"]["status"] == PUBLISHABLE
    assert summary["management_run_compatibility"]["evidence_reference_count"] == 6
    assert (
        summary["records"][0]["providers"]["aws"]["evidence_id"]
        == "aws:functions.request:aws-functions.request"
    )


def test_missing_provider_report_fails_validation():
    reports = _reports()
    reports.pop("gcp")

    summary = build_cross_provider_cost_validation(
        reports,
        pricing_registry_service=FakeRegistryService(),
        calculation_result=_calculation_result(),
    )

    assert summary["status"] == FAILED
    assert any("Missing provider evidence report" in error for error in summary["errors"])


def test_missing_intent_evidence_fails_validation():
    reports = _reports()
    reports["azure"]["records"] = [
        record
        for record in reports["azure"]["records"]
        if record["intent_id"] != "transfer.egress_gb"
    ]

    summary = build_cross_provider_cost_validation(
        reports,
        pricing_registry_service=FakeRegistryService(),
        calculation_result=_calculation_result(),
    )

    assert summary["status"] == FAILED
    assert any("Missing provider intent evidence" in error for error in summary["errors"])


def test_fallback_static_is_never_publishable():
    summary = build_cross_provider_cost_validation(
        _reports(source_type=FALLBACK_STATIC),
        pricing_registry_service=FakeRegistryService(),
        calculation_result=_calculation_result(),
    )

    assert summary["status"] == FAILED
    assert any("fallback_static is not publishable" in error for error in summary["errors"])


def test_review_required_fails_publishable_validation():
    summary = build_cross_provider_cost_validation(
        _reports(review_required=True),
        pricing_registry_service=FakeRegistryService(),
        calculation_result=_calculation_result(),
    )

    assert summary["status"] == FAILED
    assert any(
        "review_required evidence is not publishable" in error
        for error in summary["errors"]
    )


def test_incompatible_normalized_unit_fails_validation():
    summary = build_cross_provider_cost_validation(
        _reports(unit_overrides={("gcp", "functions.request"): "gb_second"}),
        pricing_registry_service=FakeRegistryService(),
        calculation_result=_calculation_result(),
    )

    assert summary["status"] == FAILED
    assert any("Normalized unit mismatch" in error for error in summary["errors"])


def test_explicit_non_applicability_is_allowed_when_declared_by_provider_evidence():
    intents = {
        "digital_twin.query_unit": {
            "group": "cost",
            "description": "Digital twin query unit",
            "normalized_unit": "query_unit",
            "expected_providers": ["aws", "azure", "gcp"],
        }
    }
    reports = {
        "aws": {
            "records": [
                _record("aws", "digital_twin.query_unit", unit="query_unit"),
            ]
        },
        "azure": {
            "records": [
                _record("azure", "digital_twin.query_unit", unit="query_unit"),
            ]
        },
        "gcp": {
            "records": [
                _record(
                    "gcp",
                    "digital_twin.query_unit",
                    unit="not_applicable",
                    source_type=NOT_APPLICABLE,
                    selected=False,
                ),
            ]
        },
    }

    summary = build_cross_provider_cost_validation(
        reports,
        pricing_registry_service=FakeRegistryService(intents),
        calculation_result=_calculation_result(),
    )

    assert summary["status"] == PUBLISHABLE
    assert summary["records"][0]["providers"]["gcp"]["status"] == NON_APPLICABLE


def test_review_required_non_applicability_is_not_publishable():
    intents = {
        "digital_twin.query_unit": {
            "group": "cost",
            "description": "Digital twin query unit",
            "normalized_unit": "query_unit",
            "expected_providers": ["aws", "azure", "gcp"],
        }
    }
    reports = {
        provider: {
            "records": [
                _record(
                    provider,
                    "digital_twin.query_unit",
                    unit="not_applicable" if provider == "gcp" else "query_unit",
                    source_type=NOT_APPLICABLE if provider == "gcp" else FETCHED,
                    selected=provider != "gcp",
                    review_required=provider == "gcp",
                ),
            ]
        }
        for provider in ("aws", "azure", "gcp")
    }

    summary = build_cross_provider_cost_validation(
        reports,
        pricing_registry_service=FakeRegistryService(intents),
        calculation_result=_calculation_result(),
    )

    assert summary["status"] == FAILED
    assert any(
        "review_required evidence is not publishable" in error
        for error in summary["errors"]
    )


def test_invalid_profile_fails_validation():
    summary = build_cross_provider_cost_validation(
        _reports(),
        pricing_registry_service=FakeRegistryService(),
        calculation_result=_calculation_result(),
        optimization_profile_id="weighted_multi_objective_v1",
    )

    assert summary["status"] == FAILED
    assert any("weighted_multi_objective_v1" in error for error in summary["errors"])


def test_calculation_result_metadata_is_required_for_run_store_compatibility():
    result = _calculation_result()
    result.pop("evidenceReferences")

    summary = build_cross_provider_cost_validation(
        _reports(),
        pricing_registry_service=FakeRegistryService(),
        calculation_result=result,
    )

    assert summary["status"] == FAILED
    compatibility = summary["management_run_compatibility"]
    assert compatibility["status"] == FAILED
    assert any("evidenceReferences" in error for error in compatibility["errors"])


def test_publishable_validation_requires_calculation_result_metadata():
    summary = build_cross_provider_cost_validation(
        _reports(),
        pricing_registry_service=FakeRegistryService(),
    )

    assert summary["status"] == FAILED
    assert any(
        "Calculation result is required for publishable validation" in error
        for error in summary["errors"]
    )
