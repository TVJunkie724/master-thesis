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


def test_deployer_reader_accepts_standalone_six_layer_profile():
    profile = _read(
        contracts.CONTRACT_ROOT.parent
        / "definitions"
        / "profiles"
        / "six-layer-eventing"
        / "1"
        / "profile.json"
    )
    validated = contracts.read_contract(profile)
    assert validated.schema_version == "architecture-profile.v2"
    assert validated.content_digest == profile["content_digest"]


def test_deployer_rejects_tampered_contract_before_execution():
    wrapper = _read(
        contracts.CONTRACT_ROOT
        / "fixtures"
        / "valid"
        / "six-layer-aws-azure-eventing-small-resolved.json"
    )
    wrapper["content_digest"] = "sha256:" + ("0" * 64)
    with pytest.raises(contracts.ContractError) as raised:
        contracts.read_contract(wrapper)
    assert raised.value.code == "ARCH_DIGEST_MISMATCH"


def test_deployer_registry_exposes_exact_dark_catalog_without_execution():
    registry = ArchitectureProfileRegistry()
    catalog = DeploymentComponentCatalog(registry)
    processing = catalog.component("deployment.aws.processing.v2")

    assert len(catalog.components) == 24
    assert len(catalog.edges) == 75
    assert len(catalog.artifacts) == 7
    assert processing["extension_slot_refs"][0]["id"] == "processor.telemetry"
    assert processing["required_permission_capabilities"] == (
        "credential.aws.administrator",
    )


def test_deployer_registry_definitions_are_deeply_immutable():
    registry = ArchitectureProfileRegistry()

    assert isinstance(registry.catalog, MappingProxyType)
    assert isinstance(registry.catalog["components"], tuple)
    assert isinstance(registry.catalog["components"][0], MappingProxyType)
    with pytest.raises(TypeError):
        registry.catalog["components"][0]["service_id"] = "changed"


def test_deployer_registry_loads_exact_six_layer_bundle():
    registry = ArchitectureProfileRegistry(
        profile_id="six-layer-eventing",
        profile_version="1",
    )
    catalog = DeploymentComponentCatalog(registry)

    assert registry.profile["profile_id"] == "six-layer-eventing"
    assert registry.catalog["catalog_id"] == ("six-layer-eventing-component-catalog")
    assert catalog.component("deployment.aws.eventing.v1")["provider"] == "aws"
    assert catalog.component("deployment.azure.eventing.v1")["provider"] == "azure"
    assert catalog.component("deployment.gcp.eventing.v1")["provider"] == "gcp"
