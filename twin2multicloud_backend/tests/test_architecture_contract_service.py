"""Focused tests for the Management API architecture contract read boundary."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from src.services.architecture_contract_service import (
    ArchitectureContractService,
    CONTRACT_ROOT,
    ContractError,
    calculate_digest,
    canonical_json,
)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_management_reader_accepts_resolution_without_persistence():
    resolution = _read(
        CONTRACT_ROOT
        / "fixtures"
        / "valid"
        / "mixed-baseline-resolved-architecture.json"
    )
    validated = ArchitectureContractService.read(resolution)
    assert validated.schema_version == "resolved-twin-architecture.v1"
    assert validated.content_digest == resolution["content_digest"]


def test_management_reader_dispatches_five_layer_v2_contract():
    profile = _read(
        CONTRACT_ROOT.parent
        / "v2"
        / "fixtures"
        / "valid"
        / "five-layer-baseline-v2-profile.json"
    )
    validated = ArchitectureContractService.read(profile)
    assert validated.schema_version == "architecture-profile.v2"
    assert validated.content_digest == profile["content_digest"]


def test_management_reader_dispatches_six_layer_profile_version_one_to_v2():
    profile = _read(
        CONTRACT_ROOT.parent
        / "definitions"
        / "profiles"
        / "six-layer-eventing"
        / "1"
        / "profile.json"
    )
    validated = ArchitectureContractService.read(profile)
    assert validated.schema_version == "architecture-profile.v2"
    assert validated.content_digest == profile["content_digest"]


def test_exported_digest_and_canonical_json_dispatch_to_v2_runtime():
    resolution = _read(
        CONTRACT_ROOT.parent
        / "v2"
        / "fixtures"
        / "valid"
        / "single-cloud-aws-small-resolved.json"
    )
    reordered = deepcopy(resolution)
    reordered["component_assignments"].reverse()

    assert calculate_digest(reordered) == resolution["content_digest"]
    assert canonical_json(reordered) == canonical_json(resolution)


def test_management_reader_rejects_unknown_version():
    wrapper = _read(CONTRACT_ROOT / "fixtures" / "invalid" / "unknown-version.json")
    with pytest.raises(ContractError) as raised:
        ArchitectureContractService.read(wrapper["document"])
    assert raised.value.code == "ARCH_VERSION_UNSUPPORTED"
