import shutil

import yaml

from backend.pricing_registry import REGISTRY_ROOT, validate_pricing_registry
from backend.pricing_registry_service import PricingRegistryService


def _copy_registry(tmp_path):
    target = tmp_path / "pricing_registry"
    shutil.copytree(REGISTRY_ROOT, target)
    return target


def _load_yaml(path):
    return yaml.safe_load(path.read_text())


def _write_yaml(path, doc):
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def test_default_bundle_resolves_complete_contract_graph():
    service = PricingRegistryService()

    bundle = service.get_optimization_bundle("cost_minimization_v1")
    strategy = service.get_calculation_strategy(bundle["calculation_strategy_id"])
    formula_set = service.get_formula_set(bundle["formula_set_id"])
    workload_contract = service.get_workload_contract(bundle["workload_contract_id"])
    contract = service.get_provider_pricing_contract(
        "azure",
        "iot",
        "IoT Hub",
        field="iot.message_ingest",
    )

    assert bundle["enabled"] is True
    assert strategy["formula_set_id"] == "cost_formula_set_v1"
    assert set(contract["allowed_formula_refs"]) <= set(formula_set["formulas"])
    assert set(contract["consumed_workload_fields"]) <= set(workload_contract["fields"])
    assert len(bundle["provider_pricing_contract_ids"]) == (
        service.get_status()["provider_pricing_contract_count"]
    )


def test_unknown_formula_ref_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "provider_pricing_contracts.yaml"
    doc = _load_yaml(path)
    doc["provider_pricing_contracts"]["aws.iot_message_ingest.pricing_contract.v1"][
        "allowed_formula_refs"
    ] = ["does_not_exist"]
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("unknown allowed_formula_refs ['does_not_exist']" in error for error in errors)


def test_unknown_workload_field_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "provider_pricing_contracts.yaml"
    doc = _load_yaml(path)
    doc["provider_pricing_contracts"]["aws.iot_message_ingest.pricing_contract.v1"][
        "consumed_workload_fields"
    ] = ["does_not_exist"]
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any(
        "unknown consumed_workload_fields ['does_not_exist']" in error
        for error in errors
    )


def test_missing_pricing_model_classification_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "provider_pricing_contracts.yaml"
    doc = _load_yaml(path)
    doc["provider_pricing_contracts"]["aws.iot_message_ingest.pricing_contract.v1"][
        "pricing_model_classification_id"
    ] = "does_not_exist"
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("unknown pricing_model_classification_id 'does_not_exist'" in error for error in errors)


def test_missing_price_source_classification_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "provider_pricing_contracts.yaml"
    doc = _load_yaml(path)
    doc["provider_pricing_contracts"]["aws.iot_message_ingest.pricing_contract.v1"][
        "price_source_classification_id"
    ] = "does_not_exist"
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("unknown price_source_classification_id 'does_not_exist'" in error for error in errors)


def test_disallowed_source_type_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "provider_pricing_contracts.yaml"
    doc = _load_yaml(path)
    doc["provider_pricing_contracts"]["aws.iot_message_ingest.pricing_contract.v1"][
        "allowed_price_source_types_by_field"
    ] = {"iot.message_ingest": ["official_static_documentation"]}
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("selected source_type 'provider_api' must be allowed" in error for error in errors)


def test_duplicate_provider_pricing_contract_id_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "provider_pricing_contracts.yaml"
    content = path.read_text()
    marker = "  aws.iot_message_ingest.pricing_contract.v1:\n"
    path.write_text(content.replace(marker, marker + marker, 1))

    errors = validate_pricing_registry(root)

    assert any("duplicate key 'aws.iot_message_ingest.pricing_contract.v1'" in error for error in errors)


def test_bundle_unknown_calculation_strategy_fails_validation(tmp_path):
    root = _copy_registry(tmp_path)
    path = root / "optimization_bundles.yaml"
    doc = _load_yaml(path)
    doc["bundles"]["cost_minimization_v1"]["calculation_strategy_id"] = "does_not_exist"
    _write_yaml(path, doc)

    errors = validate_pricing_registry(root)

    assert any("unknown calculation_strategy_id 'does_not_exist'" in error for error in errors)
