import shutil

import pytest

from backend.pricing_evidence import (
    FALLBACK_STATIC,
    FETCHED,
    OFFICIAL_CLOUD_EVIDENCE,
    validate_evidence_record,
    validate_evidence_report,
)
from backend.pricing_intent_registry import CANONICAL_PRICING_INTENTS
from backend.pricing_registry import (
    REGISTRY_ROOT,
    PricingRegistryError,
    load_pricing_registry,
    validate_pricing_registry,
)


def _copy_registry(tmp_path):
    target = tmp_path / "pricing_registry"
    shutil.copytree(REGISTRY_ROOT, target)
    return target


def _valid_evidence(**overrides):
    record = {
        "provider": "azure",
        "intent_id": "api.request_million",
        "field_path": "azure.data_access.pricePerMillionCalls",
        "source_type": FETCHED,
        "source_api": "azure-retail-prices",
        "request_scope": {"region": "westeurope"},
        "selected_row": {"meterId": "meter-api-consumption"},
        "candidate_rows": [{"meterId": "meter-api-consumption"}],
        "rejected_rows": [],
        "normalization_rule": "per_1m_requests",
        "normalized_value": 3.5,
        "currency": "USD",
        "region": "westeurope",
        "tier": {"minimum": 0},
        "mapping_version": "2026.06.08",
        "registry_version": "2026.06.08",
        "fetched_at": "2026-06-08T00:00:00+00:00",
        "review_required": False,
        "errors": [],
    }
    record.update(overrides)
    return record


def test_default_registry_loads_and_covers_canonical_intents():
    registry = load_pricing_registry()

    assert registry.registry_version == "2026.06.08"
    assert set(registry.intents) == set(CANONICAL_PRICING_INTENTS)
    assert set(registry.provider_mappings) == {"aws", "azure", "gcp"}

    for intent_id in CANONICAL_PRICING_INTENTS:
        for provider in ("aws", "azure", "gcp"):
            mapping = registry.mapping_for(provider, intent_id)
            assert mapping["intent_id"] == intent_id
            assert mapping["provider"] == provider
            assert mapping["normalization_rule"] in registry.normalization_rules


def test_registry_validation_rejects_missing_provider_mapping(tmp_path):
    root = _copy_registry(tmp_path)
    aws_mappings = root / "providers" / "aws" / "mappings.yaml"
    content = aws_mappings.read_text()
    content = content.replace(
        "  - intent_id: api.request_million\n"
        "    review_status: draft\n"
        "    normalization_rule: per_1m_requests\n"
        "    expected_cardinality: one_or_more_per_region\n"
        "    match: {service_code: AmazonApiGateway, unit: Requests}\n",
        "",
    )
    aws_mappings.write_text(content)

    errors = validate_pricing_registry(root)

    assert "Missing provider mapping for aws.api.request_million" in errors


def test_registry_validation_rejects_unknown_normalization_rule(tmp_path):
    root = _copy_registry(tmp_path)
    azure_mappings = root / "providers" / "azure" / "mappings.yaml"
    azure_mappings.write_text(
        azure_mappings.read_text().replace(
            "normalization_rule: per_1m_requests",
            "normalization_rule: not_a_rule",
            1,
        )
    )

    errors = validate_pricing_registry(root)

    assert any("unknown normalization_rule 'not_a_rule'" in error for error in errors)


def test_registry_validation_rejects_unit_mismatch_without_quantity_transform(tmp_path):
    root = _copy_registry(tmp_path)
    gcp_mappings = root / "providers" / "gcp" / "mappings.yaml"
    content = gcp_mappings.read_text()
    content = content.replace(
        "    quantity_transform:\n"
        "      from_unit: message\n"
        "      to_unit: gb\n"
        "      input_parameter: averageSizeOfMessageInKb\n"
        "      reason: Google Pub/Sub pricing is volume-based, while the workload model starts from messages.\n",
        "",
    )
    gcp_mappings.write_text(content)

    errors = validate_pricing_registry(root)

    assert any(
        "gcp/mappings.yaml:iot.message_ingest" in error
        and "declare a valid quantity_transform" in error
        for error in errors
    )


def test_registry_loader_rejects_duplicate_yaml_keys(tmp_path):
    root = _copy_registry(tmp_path)
    intents = root / "intents.yaml"
    intents.write_text(
        "schema_version: pricing-registry-intents.v1\n"
        "schema_version: pricing-registry-intents.v1\n"
        "registry_version: '2026.06.08'\n"
        "intent_groups: {}\n"
        "intents: {}\n"
    )

    with pytest.raises(PricingRegistryError) as exc:
        load_pricing_registry(root)

    assert "duplicate key 'schema_version'" in str(exc.value)


def test_registry_rejects_review_decision_price_overrides(tmp_path):
    root = _copy_registry(tmp_path)
    decisions = root / "review_decisions.yaml"
    decisions.write_text(
        "schema_version: pricing-registry-review-decisions.v1\n"
        "registry_version: '2026.06.08'\n"
        "decisions:\n"
        "  - intent_id: api.request_million\n"
        "    decision: approve\n"
        "    price_override: 3.5\n"
    )

    errors = validate_pricing_registry(root)

    assert any("forbidden price override keys ['price_override']" in error for error in errors)


def test_evidence_record_requires_selected_row_for_fetched_source():
    errors = validate_evidence_record(_valid_evidence(selected_row=None))

    assert "Fetched evidence requires selected_row" in errors


def test_publishable_evidence_rejects_fallback_static():
    record = _valid_evidence(
        source_type=FALLBACK_STATIC,
        selected_row=None,
        source_api="fallback_static",
        review_required=False,
    )

    errors = validate_evidence_report([record], publishable=True)

    assert "record[0]: fallback_static is not publishable" in errors


def test_publishable_evidence_rejects_non_reproducible_official_evidence():
    record = _valid_evidence(
        source_type=OFFICIAL_CLOUD_EVIDENCE,
        selected_row=None,
        source_reference={},
        reproducible=False,
    )

    errors = validate_evidence_report([record], publishable=True)

    assert "record[0]: Official cloud evidence requires source_reference" in errors
    assert "record[0]: Official cloud evidence must be reproducible" in errors
