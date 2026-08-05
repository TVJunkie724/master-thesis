"""Focused tests for the Deployer's non-executing profile reader."""

from __future__ import annotations

import json
from types import MappingProxyType

import pytest

from src.architecture_profiles import contracts
from src.architecture_profiles.catalog import DeploymentComponentCatalog
from src.architecture_profiles.registry import ArchitectureProfileRegistry


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_deployer_accepts_catalog_without_compiling_terraform():
    catalog = _read(
        contracts.CONTRACT_ROOT
        / "fixtures"
        / "valid"
        / "baseline-component-catalog.json"
    )
    validated = contracts.read_contract(catalog)
    assert validated.stable_id == "baseline-component-catalog"
    assert validated.content_digest == catalog["content_digest"]


def test_deployer_reader_dispatches_five_layer_v2_contract():
    profile = _read(
        contracts.CONTRACT_ROOT.parent
        / "v2"
        / "fixtures"
        / "valid"
        / "five-layer-baseline-v2-profile.json"
    )
    validated = contracts.read_contract(profile)
    assert validated.schema_version == "architecture-profile.v2"
    assert validated.content_digest == profile["content_digest"]


def test_deployer_rejects_secret_like_fields_before_execution():
    wrapper = _read(
        contracts.CONTRACT_ROOT / "fixtures" / "invalid" / "secret-like-field.json"
    )
    with pytest.raises(contracts.ContractError) as raised:
        contracts.read_contract(wrapper["document"])
    assert raised.value.code == "ARCH_SECRET_FIELD_FORBIDDEN"


def test_deployer_registry_exposes_exact_dark_catalog_without_execution():
    registry = ArchitectureProfileRegistry()
    catalog = DeploymentComponentCatalog(registry)
    processing = catalog.component("deployment.aws.processing")

    assert len(catalog.components) == 22
    assert len(catalog.edges) == 36
    assert len(catalog.artifacts) == 50
    assert processing["extension_slot_refs"][0]["id"] == "processor.telemetry"
    assert {
        binding["terraform_variable"]
        for binding in processing["terraform_binding"]["input_bindings"]
    } == {"aws_l2_lambda_memory_mb", "validated_extension_packages"}


def test_deployer_registry_definitions_are_deeply_immutable():
    registry = ArchitectureProfileRegistry()

    assert isinstance(registry.catalog, MappingProxyType)
    assert isinstance(registry.catalog["components"], tuple)
    assert isinstance(registry.catalog["components"][0], MappingProxyType)
    with pytest.raises(TypeError):
        registry.catalog["components"][0]["service_id"] = "changed"
