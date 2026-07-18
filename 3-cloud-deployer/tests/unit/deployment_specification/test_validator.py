"""Contract, semantic validation, and tfvars translation tests."""

from __future__ import annotations

from copy import deepcopy
import io
import json
import zipfile

import pytest

from src.deployment_specification import (
    calculate_digest,
    translate_deployment_tfvars,
    validate_deployment_manifest,
)
from src.deployment_specification.errors import DeploymentSpecificationError
from src.validation.accessors import DirectoryAccessor, ZipFileAccessor
from src.validation.core import (
    ValidationContext,
    check_deployment_manifest,
)
from tests.utils.deployment_specification import (
    CONTRACT_ROOT,
    DEFAULT_PACKAGE_FILES,
    deployment_manifest,
    load_specification,
    provider_config_for_specification,
)


VALID_FIXTURES = tuple(
    path.name
    for path in sorted((CONTRACT_ROOT / "fixtures" / "valid").glob("*.json"))
)
INVALID_FIXTURES = tuple(
    path.name
    for path in sorted((CONTRACT_ROOT / "fixtures" / "invalid").glob("*.json"))
)


@pytest.mark.parametrize("fixture_name", VALID_FIXTURES)
def test_valid_fixtures_translate_only_allowlisted_deployable_dimensions(
    fixture_name,
):
    specification = load_specification(fixture_name)
    providers = provider_config_for_specification(specification)

    validated = validate_deployment_manifest(
        deployment_manifest(specification, providers=providers),
        providers,
    )
    translated = translate_deployment_tfvars(validated.specification)

    expected = {}
    for component in specification["components"]:
        for dimension in component["dimensions"]:
            target = dimension.get("terraform_target")
            if dimension["classification"] == "deployable_selection":
                assert target
                expected.setdefault(target, dimension["value"])
            else:
                assert target is None
    assert dict(translated) == dict(sorted(expected.items()))


@pytest.mark.parametrize("fixture_name", INVALID_FIXTURES)
def test_all_canonical_negative_fixtures_fail_closed(fixture_name):
    specification = load_specification(fixture_name, validity="invalid")
    providers = provider_config_for_specification(specification)
    manifest = deployment_manifest(specification, providers=providers)

    with pytest.raises(DeploymentSpecificationError) as exc_info:
        validate_deployment_manifest(manifest, providers)

    assert exc_info.value.code.startswith("DEPLOYMENT_")
    assert len(str(exc_info.value)) < 512


def test_provider_alias_is_normalized_only_at_manifest_boundary():
    specification = load_specification("mixed-providers.json")
    providers = provider_config_for_specification(specification)
    aliased = {
        key: "google" if value == "gcp" else value
        for key, value in providers.items()
    }

    validated = validate_deployment_manifest(
        deployment_manifest(specification, providers=aliased),
        aliased,
    )

    assert "gcp" in validated.provider_by_slot.values()
    assert "google" not in validated.provider_by_slot.values()


def test_manifest_digest_binding_rejects_tampering_without_echoing_values():
    specification = load_specification()
    providers = provider_config_for_specification(specification)
    manifest = deployment_manifest(specification, providers=providers)
    manifest["resolved_deployment_specification_digest"] = "sha256:" + ("0" * 64)

    with pytest.raises(
        DeploymentSpecificationError,
        match="DEPLOYMENT_SPECIFICATION_DIGEST_MISMATCH",
    ) as exc_info:
        validate_deployment_manifest(manifest, providers)

    assert "0000000000" not in str(exc_info.value)


def test_translation_is_independent_of_json_object_key_order():
    specification = load_specification("all-azure.json")
    reordered = _reverse_mapping_order(specification)
    reordered["digest"] = calculate_digest(reordered)
    providers = provider_config_for_specification(reordered)

    first = validate_deployment_manifest(
        deployment_manifest(specification, providers=providers),
        providers,
    )
    second = validate_deployment_manifest(
        deployment_manifest(reordered, providers=providers),
        providers,
    )

    assert dict(translate_deployment_tfvars(first.specification)) == dict(
        translate_deployment_tfvars(second.specification)
    )


def test_transition_runtime_tfvars_are_source_owned_and_allowlisted():
    specification = load_specification("all-aws.json")
    providers = provider_config_for_specification(specification)

    validated = validate_deployment_manifest(
        deployment_manifest(specification, providers=providers),
        providers,
    )
    translated = translate_deployment_tfvars(validated.specification)

    assert translated["aws_hot_to_cool_mover_memory_mb"] == 512
    assert translated["aws_hot_to_cool_schedule_expression"] == "rate(1 day)"
    assert translated["aws_cool_to_archive_mover_memory_mb"] == 512
    assert translated["aws_cool_to_archive_schedule_expression"] == "rate(7 days)"
    assert "aws_l3_cool_mover_memory_mb" not in translated
    assert "aws_l3_archive_mover_memory_mb" not in translated


@pytest.mark.parametrize(
    "terraform_target",
    (
        "aws_l1_lambda_memory_mb",
        "aws_l2_lambda_memory_mb",
        "aws_dynamodb_billing_mode",
        "aws_l3_reader_lambda_memory_mb",
        "aws_l3_cool_storage_class",
        "aws_hot_to_cool_mover_memory_mb",
        "aws_hot_to_cool_schedule_expression",
        "aws_l3_archive_storage_class",
        "aws_cool_to_archive_mover_memory_mb",
        "aws_cool_to_archive_schedule_expression",
        "aws_l4_lambda_memory_mb",
        "aws_glue_lambda_memory_mb",
    ),
)
def test_unsupported_aws_deployable_values_fail_preflight(terraform_target):
    fixture_name = (
        "mixed-providers.json"
        if terraform_target == "aws_glue_lambda_memory_mb"
        else "all-aws.json"
    )
    specification = load_specification(fixture_name)
    providers = provider_config_for_specification(specification)
    matched = False
    for component in specification["components"]:
        for dimension in component["dimensions"]:
            if dimension.get("terraform_target") != terraform_target:
                continue
            matched = True
            dimension["value"] = (
                -1 if isinstance(dimension["value"], int) else "__unsupported__"
            )
    assert matched, f"Missing fixture target: {terraform_target}"
    specification["digest"] = calculate_digest(specification)

    with pytest.raises(DeploymentSpecificationError) as exc_info:
        validate_deployment_manifest(
            deployment_manifest(specification, providers=providers),
            providers,
        )

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH"
    assert terraform_target.removeprefix("aws_").split("_")[0] in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    "terraform_target",
    (
        "azure_iot_hub_sku",
        "azure_iot_hub_capacity",
        "azure_l1_function_plan_sku",
        "azure_l2_function_plan_sku",
        "azure_cosmos_capacity_mode",
        "azure_l3_function_plan_sku",
        "azure_storage_account_tier",
        "azure_storage_replication_type",
        "azure_l3_cool_blob_tier",
        "azure_hot_to_cool_timer_schedule",
        "azure_l3_archive_blob_tier",
        "azure_cool_to_archive_timer_schedule",
        "azure_l4_function_plan_sku",
        "azure_grafana_sku",
        "azure_glue_function_plan_sku",
    ),
)
def test_unsupported_azure_deployable_values_fail_preflight(terraform_target):
    fixture_name = (
        "mixed-providers.json"
        if terraform_target == "azure_glue_function_plan_sku"
        else "all-azure.json"
    )
    specification = load_specification(fixture_name)
    providers = provider_config_for_specification(specification)
    matched = False
    for component in specification["components"]:
        for dimension in component["dimensions"]:
            if dimension.get("terraform_target") != terraform_target:
                continue
            matched = True
            dimension["value"] = (
                -1 if isinstance(dimension["value"], int) else "__unsupported__"
            )
    assert matched, f"Missing fixture target: {terraform_target}"
    specification["digest"] = calculate_digest(specification)

    with pytest.raises(DeploymentSpecificationError) as exc_info:
        validate_deployment_manifest(
            deployment_manifest(specification, providers=providers),
            providers,
        )

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH"


def test_azure_iot_hub_sku_capacity_combination_fails_preflight():
    specification = load_specification("all-azure.json")
    providers = provider_config_for_specification(specification)
    for component in specification["components"]:
        if component["component_id"] != "l1.azure.iot_hub":
            continue
        for dimension in component["dimensions"]:
            if dimension.get("terraform_target") == "azure_iot_hub_capacity":
                dimension["value"] = 2
    specification["digest"] = calculate_digest(specification)

    with pytest.raises(DeploymentSpecificationError) as exc_info:
        validate_deployment_manifest(
            deployment_manifest(specification, providers=providers),
            providers,
        )

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_DIMENSION_MISMATCH"
    assert exc_info.value.field.endswith("l1.azure.iot_hub")
    assert "combination is unsupported" in str(exc_info.value)


@pytest.mark.parametrize(
    "fixture_name",
    (
        "missing-transition-runtime.json",
        "wrong-transition-provider.json",
        "reordered-transition-runtime.json",
    ),
)
def test_transition_runtime_contract_tampering_fails_closed(fixture_name):
    specification = load_specification(
        fixture_name,
        validity="invalid",
    )
    providers = provider_config_for_specification(specification)

    with pytest.raises(DeploymentSpecificationError) as exc_info:
        validate_deployment_manifest(
            deployment_manifest(specification, providers=providers),
            providers,
        )

    assert exc_info.value.code == "DEPLOYMENT_SPECIFICATION_COMPONENT_MISMATCH"
    assert "transition" in exc_info.value.field


def test_zip_and_directory_manifest_validation_are_equivalent(tmp_path):
    specification = load_specification()
    providers = provider_config_for_specification(specification)
    manifest = deployment_manifest(specification, providers=providers)
    files = {
        **{name: "{}" for name in DEFAULT_PACKAGE_FILES},
        "config_iot_devices.json": "[]",
        "config_events.json": "[]",
        "deployment_manifest.json": json.dumps(manifest),
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content, encoding="utf-8")

    directory_accessor = DirectoryAccessor(tmp_path)
    directory_context = ValidationContext(
        all_files=directory_accessor.list_files(),
        prov_config=providers,
    )
    check_deployment_manifest(directory_accessor, directory_context, required=True)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    buffer.seek(0)
    with zipfile.ZipFile(buffer) as archive:
        zip_accessor = ZipFileAccessor(archive)
        zip_context = ValidationContext(
            all_files=zip_accessor.list_files(),
            prov_config=providers,
        )
        check_deployment_manifest(zip_accessor, zip_context, required=True)


def _reverse_mapping_order(value):
    if isinstance(value, dict):
        return {
            key: _reverse_mapping_order(nested)
            for key, nested in reversed(tuple(value.items()))
        }
    if isinstance(value, list):
        return [_reverse_mapping_order(item) for item in value]
    return deepcopy(value)
