import shutil
from copy import deepcopy

import yaml

from backend.pricing_contract_validation import (
    DISALLOWED_PRICE_SOURCE_TYPE,
    FAILED,
    G1_REGISTRY_COMPLETENESS,
    G2_SOURCE_BUILDABILITY,
    G3_EVIDENCE_PRESENCE,
    G4_NORMALIZATION,
    G5_CONTRACT_COMPATIBILITY,
    G6_PUBLISHABILITY,
    G7_CALCULATION_READINESS,
    INVALID_OFFICIAL_STATIC_SOURCE,
    PASSED,
    TIER_SEMANTICS_MISMATCH,
    UNIT_SEMANTICS_MISMATCH,
    UNKNOWN_CALCULATION_COMPONENT,
    UNKNOWN_FORMULA_REF,
    UNPUBLISHABLE_PRICING_MODEL_CLASSIFICATION,
    UNPUBLISHABLE_SOURCE_STATE,
    PricingContractValidationService,
)
from backend.pricing_evidence import FETCHED, OFFICIAL_CLOUD_EVIDENCE
from backend.pricing_registry import REGISTRY_ROOT
from backend.pricing_registry_service import PricingRegistryService


def _copy_registry(tmp_path):
    target = tmp_path / "pricing_registry"
    shutil.copytree(REGISTRY_ROOT, target)
    return target


def _load_yaml(path):
    return yaml.safe_load(path.read_text())


def _write_yaml(path, doc):
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def _record(provider, intent_id, *, unit, normalization_rule, source_type=FETCHED):
    record = {
        "schema_version": "pricing-evidence.v1",
        "provider": provider,
        "intent_id": intent_id,
        "field_path": intent_id,
        "source_type": source_type,
        "source_api": f"{provider}-pricing-api",
        "request_scope": {"provider": provider, "region": "test-region"},
        "normalization_rule": normalization_rule,
        "normalization": {"target_unit": unit},
        "normalized_value": 0.01,
        "currency": "USD",
        "mapping_version": "2026.06.08",
        "registry_version": "2026.06.08",
        "fetched_at": "2026-06-08T13:00:00Z",
        "review_required": False,
        "match_status": "matched",
        "selected_row": {
            "candidate_id": f"{provider}-{intent_id}",
            "unit": unit,
            "description": intent_id,
            "tier": {"minimum": 0},
        },
        "candidate_rows": [],
        "rejected_rows": [],
        "tier": {"minimum": 0},
        "errors": [],
    }
    if source_type == OFFICIAL_CLOUD_EVIDENCE:
        record["selected_row"] = None
        record["source_reference"] = {
            "url": "https://example.invalid/provider-pricing",
            "retrieved_at": "2026-06-08T13:00:00Z",
        }
        record["reproducible"] = True
    return record


def _validator(root=None):
    return PricingContractValidationService(PricingRegistryService(root or REGISTRY_ROOT))


def _validate(
    provider="aws",
    field="transfer.egress_gb",
    expected_unit="gb",
    normalization_rule="per_gb",
    record=None,
    root=None,
):
    service = _validator(root)
    evidence_record = record or _record(
        provider,
        field,
        unit=expected_unit,
        normalization_rule=normalization_rule,
    )
    return service.validate_field(
        provider=provider,
        field=field,
        expected_unit=expected_unit,
        evidence_record=evidence_record,
    )


def _error_codes(report):
    return {error["error_code"] for error in report["errors"]}


class DriftedRegistryService:
    def __init__(self, *, contract_overrides=None, source_overrides=None, strategy_overrides=None):
        self.real = PricingRegistryService()
        self.contract_overrides = contract_overrides or {}
        self.source_overrides = source_overrides or {}
        self.strategy_overrides = strategy_overrides or {}

    def get_optimization_bundle(self, bundle_id):
        return self.real.get_optimization_bundle(bundle_id)

    def get_calculation_strategy(self, strategy_id):
        strategy = self.real.get_calculation_strategy(strategy_id)
        strategy.update(deepcopy(self.strategy_overrides))
        return strategy

    def get_formula_set(self, formula_set_id):
        return self.real.get_formula_set(formula_set_id)

    def get_workload_contract(self, workload_contract_id):
        return self.real.get_workload_contract(workload_contract_id)

    def get_provider_pricing_contract_for_field(self, provider, field):
        contract = self.real.get_provider_pricing_contract_for_field(provider, field)
        contract.update(deepcopy(self.contract_overrides))
        return contract

    def get_pricing_model_classification(self, classification_id):
        return self.real.get_pricing_model_classification(classification_id)

    def get_price_source_classification(self, classification_id):
        source = self.real.get_price_source_classification(classification_id)
        source.update(deepcopy(self.source_overrides))
        return source


def _validate_with_service(service, record=None):
    validator = PricingContractValidationService(service)
    evidence_record = record or _record(
        "aws",
        "transfer.egress_gb",
        unit="gb",
        normalization_rule="per_gb",
    )
    return validator.validate_field(
        provider="aws",
        field="transfer.egress_gb",
        expected_unit="gb",
        evidence_record=evidence_record,
    )


def test_representative_aws_azure_gcp_paths_pass_all_required_gates():
    cases = [
        ("aws", "iot.message_ingest", "message", "per_1m_messages"),
        ("azure", "iot.message_ingest", "message", "per_1m_messages"),
        ("gcp", "transfer.egress_gb", "gb", "per_gb"),
    ]

    for provider, field, unit, normalization_rule in cases:
        report = _validate(
            provider=provider,
            field=field,
            expected_unit=unit,
            normalization_rule=normalization_rule,
        )

        assert report["status"] == PASSED
        assert all(gate["status"] == PASSED for gate in report["gates"].values())


def test_official_static_source_passes_only_when_contract_allows_it(tmp_path):
    root = _copy_registry(tmp_path)
    _allow_official_static(root, "aws.transfer_egress_gb")
    record = _record(
        "aws",
        "transfer.egress_gb",
        unit="gb",
        normalization_rule="per_gb",
        source_type=OFFICIAL_CLOUD_EVIDENCE,
    )

    report = _validate(record=record, root=root)

    assert report["status"] == PASSED


def test_official_static_source_is_rejected_when_contract_requires_provider_api():
    record = _record(
        "aws",
        "transfer.egress_gb",
        unit="gb",
        normalization_rule="per_gb",
        source_type=OFFICIAL_CLOUD_EVIDENCE,
    )

    report = _validate(record=record)

    assert report["status"] == FAILED
    assert DISALLOWED_PRICE_SOURCE_TYPE in _error_codes(report)


def test_official_static_source_requires_reference_metadata(tmp_path):
    root = _copy_registry(tmp_path)
    _allow_official_static(root, "aws.transfer_egress_gb")
    record = _record(
        "aws",
        "transfer.egress_gb",
        unit="gb",
        normalization_rule="per_gb",
        source_type=OFFICIAL_CLOUD_EVIDENCE,
    )
    record.pop("source_reference")

    report = _validate(record=record, root=root)

    assert INVALID_OFFICIAL_STATIC_SOURCE in _error_codes(report)
    assert report["gates"][G3_EVIDENCE_PRESENCE]["status"] == FAILED


def test_missing_required_evidence_field_blocks_calculation():
    record = _record("aws", "transfer.egress_gb", unit="gb", normalization_rule="per_gb")
    record.pop("request_scope")

    report = _validate(record=record)

    assert report["gates"][G3_EVIDENCE_PRESENCE]["status"] == FAILED
    assert report["gates"][G7_CALCULATION_READINESS]["status"] == FAILED


def test_wrong_normalized_unit_fails_normalization_gate():
    record = _record("aws", "transfer.egress_gb", unit="message", normalization_rule="per_gb")

    report = _validate(record=record, expected_unit="gb")

    assert UNIT_SEMANTICS_MISMATCH in _error_codes(report)
    assert report["gates"][G4_NORMALIZATION]["status"] == FAILED


def test_missing_tier_metadata_fails_contract_compatibility_gate():
    record = _record("aws", "transfer.egress_gb", unit="gb", normalization_rule="per_gb")
    record.pop("tier")
    record["selected_row"].pop("tier")

    report = _validate(record=record)

    assert TIER_SEMANTICS_MISMATCH in _error_codes(report)
    assert report["gates"][G5_CONTRACT_COMPATIBILITY]["status"] == FAILED


def test_formula_ref_outside_active_formula_set_is_rejected():
    service = DriftedRegistryService(
        contract_overrides={"allowed_formula_refs": ["does_not_exist"]}
    )

    report = _validate_with_service(service)

    assert UNKNOWN_FORMULA_REF in _error_codes(report)


def test_unknown_calculation_component_is_rejected(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "provider_pricing_contracts.yaml"
    doc = _load_yaml(path)
    doc["provider_pricing_contracts"]["aws.transfer_egress_gb.pricing_contract.v1"][
        "calculation_component"
    ] = "does_not_exist"
    _write_yaml(path, doc)

    report = _validate(root=root)

    assert UNKNOWN_CALCULATION_COMPONENT in _error_codes(report)


def test_stale_model_classification_is_rejected(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "pricing_model_classifications.yaml"
    doc = _load_yaml(path)
    doc["classifications"]["aws.transfer_egress_gb.model.v1"]["review_status"] = "stale"
    doc["classifications"]["aws.transfer_egress_gb.model.v1"]["publishable"] = False
    _write_yaml(path, doc)

    report = _validate(root=root)

    assert UNPUBLISHABLE_PRICING_MODEL_CLASSIFICATION in _error_codes(report)
    assert report["gates"][G6_PUBLISHABILITY]["status"] == FAILED


def test_ambiguous_source_classification_is_rejected(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    doc["classifications"]["aws.transfer_egress_gb.source.v1"]["review_status"] = "ambiguous"
    doc["classifications"]["aws.transfer_egress_gb.source.v1"]["publishable"] = False
    _write_yaml(path, doc)

    report = _validate(root=root)

    assert UNPUBLISHABLE_SOURCE_STATE in _error_codes(report)
    assert report["gates"][G6_PUBLISHABILITY]["status"] == FAILED


def test_unsupported_source_marked_publishable_is_rejected():
    service = DriftedRegistryService(
        source_overrides={
            "source_type": "fallback_static",
            "expected_build_path": "diagnostic_fallback_only",
            "publishable": False,
        },
        contract_overrides={
            "allowed_price_source_types_by_field": {
                "transfer.egress_gb": ["fallback_static"]
            }
        },
    )

    report = _validate_with_service(service)

    assert UNPUBLISHABLE_SOURCE_STATE in _error_codes(report)


def test_error_messages_are_secret_free():
    record = _record("aws", "transfer.egress_gb", unit="gb", normalization_rule="per_gb")
    record["normalization"] = {"target_unit": "/Users/caroline/private_key.json"}

    report = _validate(record=record)
    serialized_errors = str(report["errors"])

    assert "/Users/" not in serialized_errors
    assert "private_key" not in serialized_errors
    assert "[redacted]" in serialized_errors


def test_registry_completeness_gate_fails_for_unknown_provider_field():
    report = _validate(field="does.not.exist", expected_unit="unit", normalization_rule="per_unit")

    assert report["status"] == FAILED
    assert report["gates"][G1_REGISTRY_COMPLETENESS]["status"] == FAILED
    assert report["gates"][G7_CALCULATION_READINESS]["status"] == FAILED


def test_source_buildability_gate_rejects_incompatible_build_path():
    service = DriftedRegistryService(
        source_overrides={"expected_build_path": "declared_not_applicable"}
    )

    report = _validate_with_service(service)

    assert report["gates"][G2_SOURCE_BUILDABILITY]["status"] == FAILED


def _allow_official_static(root, slug):
    source_path = root / "price_source_classifications.yaml"
    source_doc = _load_yaml(source_path)
    source_doc["classifications"][f"{slug}.source.v1"].update(
        {
            "source_type": "official_static_documentation",
            "allowed_source_types": ["official_static_documentation"],
            "expected_build_path": "loaded_from_official_static_documentation",
            "source_url": "https://example.invalid/provider-pricing",
        }
    )
    _write_yaml(source_path, source_doc)

    contract_path = root / "provider_pricing_contracts.yaml"
    contract_doc = _load_yaml(contract_path)
    field = "transfer.egress_gb"
    contract_doc["provider_pricing_contracts"][f"{slug}.pricing_contract.v1"][
        "allowed_price_source_types_by_field"
    ] = {field: ["official_static_documentation"]}
    _write_yaml(contract_path, contract_doc)
