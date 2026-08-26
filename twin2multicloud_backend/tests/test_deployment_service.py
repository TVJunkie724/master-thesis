"""Six-layer deployment-package contract tests."""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from src.services.credential_resolution_service import DeploymentCredentials
from src.schemas.optimizer_calculation import SIX_LAYER_WORKLOAD_ROOT
from src.services.deployment_service import (
    _architecture_provider_ids,
    _build_deployment_manifest,
    _build_optimization_config_from_params,
    _build_providers_config,
    _component_catalog_ref,
    _manifest_version_for_contracts,
    _validate_architecture_specification_path,
    _validate_six_layer_deployment_regions,
)
from src.services.errors import DeploymentPackageBuildFailed
from tests.architecture_test_data import calculation_result_and_contracts


def _contracts():
    return calculation_result_and_contracts()[1:]


def test_six_layer_contract_pair_produces_manifest_v4_without_secrets():
    specification, architecture = _contracts()
    twin = SimpleNamespace(id="twin-1", name="Six Layer Twin", deployer_config=None)
    credentials = DeploymentCredentials(
        providers=("aws", "azure"),
        config_credentials={
            "aws": {"aws_secret_access_key": "must-not-leak"},
            "azure": {"azure_client_secret": "must-not-leak"},
        },
        sources={"aws": "cloud_connection", "azure": "cloud_connection"},
    )
    providers = _build_providers_config(architecture)
    manifest_providers = {
        key: value for key, value in providers.items() if key != "event_layer_provider"
    }

    manifest = _build_deployment_manifest(
        twin,
        manifest_providers,
        credentials,
        ["config.json", "config_credentials.json"],
        resolved_architecture=architecture,
        deployment_specification=specification,
    )

    serialized = json.dumps(manifest)
    assert manifest["manifest_version"] == "4.0"
    assert manifest["calculation_run_id"] == specification["calculation_run_id"]
    assert manifest["credentials"]["contains_secret_payloads"] is False
    assert "must-not-leak" not in serialized
    assert "azure_client_secret" not in serialized


def test_only_rta_v2_rds_v2_pair_is_supported():
    specification, architecture = _contracts()
    assert _manifest_version_for_contracts(architecture, specification) == "4.0"

    unsupported = copy.deepcopy(architecture)
    unsupported["schema_version"] = "resolved-twin-architecture.v1"
    with pytest.raises(DeploymentPackageBuildFailed):
        _manifest_version_for_contracts(unsupported, specification)


def test_provider_projection_includes_independent_eventing_component():
    specification, architecture = _contracts()
    providers = _build_providers_config(architecture)

    assert set(providers) == {
        "layer_1_provider",
        "layer_2_provider",
        "layer_3_hot_provider",
        "layer_3_cold_provider",
        "layer_3_archive_provider",
        "layer_4_provider",
        "layer_5_provider",
        "event_layer_provider",
    }
    assert _architecture_provider_ids(architecture) == {"aws", "azure"}
    _validate_architecture_specification_path(
        providers,
        architecture,
        specification,
    )


def test_provider_drift_between_architecture_and_specification_is_rejected():
    specification, architecture = _contracts()
    providers = _build_providers_config(architecture)
    specification["component_selections"][0]["provider"] = "azure"

    with pytest.raises(DeploymentPackageBuildFailed):
        _validate_architecture_specification_path(
            providers,
            architecture,
            specification,
        )


def test_active_profile_catalog_reference_is_exact():
    _specification, architecture = _contracts()
    catalog = _component_catalog_ref(architecture["architecture_profile_ref"])

    assert catalog["id"] == "six-layer-eventing-component-catalog"
    assert catalog["version"] == "1"
    assert catalog["digest"].startswith("sha256:")


def test_six_layer_workload_projects_no_removed_feature_flags():
    params = json.loads(
        (SIX_LAYER_WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json").read_text(
            encoding="utf-8"
        )
    )
    optimization = _build_optimization_config_from_params(
        params,
        architecture_profile_ref={"id": "six-layer-eventing", "version": "1"},
    )

    assert optimization == {"result": {"inputParamsUsed": {}}}


def test_fixed_pricing_regions_are_enforced():
    _specification, architecture = _contracts()
    providers = _build_providers_config(architecture)
    valid = {
        "aws": {"aws_region": "eu-central-1"},
        "azure": {
            "azure_region": "westeurope",
            "azure_region_digital_twin": "westeurope",
        },
    }
    _validate_six_layer_deployment_regions(architecture, providers, valid)

    invalid = copy.deepcopy(valid)
    invalid["azure"]["azure_region"] = "eastus"
    with pytest.raises(DeploymentPackageBuildFailed):
        _validate_six_layer_deployment_regions(architecture, providers, invalid)
