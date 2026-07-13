import shutil

import yaml

from backend.pricing_registry import REGISTRY_ROOT, load_pricing_registry, validate_pricing_registry
from backend.pricing_registry_service import PricingRegistryService


def _copy_registry(tmp_path):
    target = tmp_path / "pricing_registry"
    shutil.copytree(REGISTRY_ROOT, target)
    return target


def _load_yaml(path):
    return yaml.safe_load(path.read_text())


def _write_yaml(path, data):
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_default_classifications_load_and_cover_every_provider_mapping():
    registry = load_pricing_registry()

    assert len(registry.pricing_model_classifications) == 48
    assert len(registry.price_source_classifications) == 48

    for provider, mappings in registry.provider_mappings.items():
        for intent_id in mappings:
            assert any(
                item["provider"] == provider and item["field"] == intent_id
                for item in registry.pricing_model_classifications.values()
            )
            assert any(
                item["provider"] == provider and item["field"] == intent_id
                for item in registry.price_source_classifications.values()
            )


def test_field_verification_matrix_covers_every_active_pricing_field():
    service = PricingRegistryService()

    rows = service.build_field_verification_matrix()

    assert len(rows) == 48
    assert all(row["verification_status"] == "passed" for row in rows)
    assert all(row["publishable"] is True for row in rows)
    assert all(row["selected_source_type"] in row["allowed_source_types"] for row in rows)


def test_fallback_static_source_cannot_be_publishable(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    source = doc["classifications"]["aws.iot_message_ingest.source.v1"]
    source["source_type"] = "fallback_static"
    source["expected_build_path"] = "diagnostic_fallback_only"
    source["allowed_source_types"] = ["fallback_static"]
    source["publishable"] = True
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("fallback_static source cannot be publishable" in error for error in errors)
    assert any("source_type 'fallback_static' cannot be publishable" in error for error in errors)


def test_unsupported_source_cannot_be_publishable(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    source = doc["classifications"]["aws.iot_message_ingest.source.v1"]
    source["source_type"] = "unsupported"
    source["expected_build_path"] = "declared_unsupported"
    source["allowed_source_types"] = ["unsupported"]
    source["publishable"] = True
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("unsupported source cannot be publishable" in error for error in errors)
    assert any("source_type 'unsupported' cannot be publishable" in error for error in errors)


def test_source_type_build_path_mismatch_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    source = doc["classifications"]["aws.iot_message_ingest.source.v1"]
    source["source_type"] = "provider_api"
    source["expected_build_path"] = "loaded_from_official_static_documentation"
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("is incompatible with source_type 'provider_api'" in error for error in errors)


def test_provider_api_requires_evidence_refs(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    doc["classifications"]["aws.iot_message_ingest.source.v1"]["required_evidence_refs"] = []
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("provider_api source requires required_evidence_refs" in error for error in errors)


def test_official_static_source_requires_source_url(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    source = doc["classifications"]["aws.iot_message_ingest.source.v1"]
    source["source_type"] = "official_static_documentation"
    source["expected_build_path"] = "loaded_from_official_static_documentation"
    source["allowed_source_types"] = ["official_static_documentation"]
    source["required_evidence_refs"] = []
    source["source_url"] = ""
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("source_url must be a non-empty string" in error for error in errors)
    assert any("official_static_documentation requires source_url" in error for error in errors)


def test_curated_model_constant_must_be_non_price_assumption(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    source = doc["classifications"]["aws.iot_message_ingest.source.v1"]
    source["source_type"] = "curated_model_constant"
    source["expected_build_path"] = "loaded_from_curated_model_constant"
    source["allowed_source_types"] = ["curated_model_constant"]
    source["required_evidence_refs"] = []
    source["value_kind"] = "price"
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("curated_model_constant must be non-price model data" in error for error in errors)


def test_not_applicable_requires_reason(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    source = doc["classifications"]["aws.iot_message_ingest.source.v1"]
    source["source_type"] = "not_applicable"
    source["expected_build_path"] = "declared_not_applicable"
    source["allowed_source_types"] = ["not_applicable"]
    source["required_evidence_refs"] = []
    source["reason"] = ""
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("not_applicable requires reason" in error for error in errors)


def test_stale_pricing_model_cannot_be_publishable(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "pricing_model_classifications.yaml"
    doc = _load_yaml(path)
    model = doc["classifications"]["aws.iot_message_ingest.model.v1"]
    model["review_status"] = "stale"
    model["publishable"] = True
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("review_status 'stale' cannot be publishable" in error for error in errors)


def test_missing_source_classification_for_active_field_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    doc["classifications"].pop("aws.iot_message_ingest.source.v1")
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("missing classification for aws.iot.message_ingest" in error for error in errors)


def test_duplicate_source_field_coverage_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    duplicate = dict(doc["classifications"]["aws.iot_message_ingest.source.v1"])
    duplicate["id"] = "aws.iot_message_ingest.duplicate_source.v1"
    doc["classifications"][duplicate["id"]] = duplicate
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("duplicate field coverage for aws.iot.message_ingest" in error for error in errors)


def test_source_classification_model_reference_must_match_provider_field(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    doc["classifications"]["aws.iot_message_ingest.source.v1"][
        "pricing_model_classification_id"
    ] = "aws.transfer_egress_gb.model.v1"
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("does not match provider/field" in error for error in errors)


def test_unknown_verification_status_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    doc["classifications"]["aws.iot_message_ingest.source.v1"][
        "verification_status"
    ] = "maybe"
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("unsupported verification_status 'maybe'" in error for error in errors)


def test_failed_verification_requires_failure_reason(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "price_source_classifications.yaml"
    doc = _load_yaml(path)
    source = doc["classifications"]["aws.iot_message_ingest.source.v1"]
    source["verification_status"] = "failed"
    source["failure_reason"] = ""
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("failed verification requires failure_reason" in error for error in errors)
