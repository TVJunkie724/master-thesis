"""Focused tests for the Optimizer's dark architecture-profile reader."""

from __future__ import annotations

import json
from types import MappingProxyType

import pytest

from backend.architecture_profiles import contracts
from backend.architecture_profiles.capability_resolver import (
    resolve_provider_capabilities,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_optimizer_reader_accepts_standalone_six_layer_profile():
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


def test_optimizer_rejects_tampered_profile():
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


def test_optimizer_registry_projects_fail_closed_provider_capabilities():
    registry = ArchitectureProfileRegistry()
    aws = resolve_provider_capabilities("aws", registry=registry)
    gcp = resolve_provider_capabilities("gcp", registry=registry)

    assert registry.profile["profile_id"] == "six-layer-eventing"
    assert len(registry.profile["optimization_slot_ids"]) == 8
    assert registry.profile["lifecycle_status"] == "active"
    assert aws.supported is True
    assert aws.missing_capability_ids == ()
    assert aws.reason_codes == ()
    assert gcp.supported is True
    assert gcp.missing_capability_ids == ()
    assert gcp.reason_codes == ()


def test_optimizer_registry_definitions_are_deeply_immutable():
    registry = ArchitectureProfileRegistry()

    assert isinstance(registry.profile, MappingProxyType)
    assert isinstance(registry.profile["components"], tuple)
    assert isinstance(registry.profile["components"][0], MappingProxyType)
    with pytest.raises(TypeError):
        registry.profile["components"][0]["component_id"] = "component.changed"
