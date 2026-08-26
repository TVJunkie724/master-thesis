"""Management read-boundary tests for the active architecture contract."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from src.services.architecture_contract_service import (
    ArchitectureContractService,
    CONTRACT_BUNDLE_ROOT,
    ContractError,
    calculate_digest,
    canonical_json,
)
from tests.architecture_test_data import (
    calculation_result_and_contracts,
    linked_architecture_fixture_documents,
)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_management_reader_accepts_canonical_six_layer_resolution():
    _result, _specification, resolution = calculation_result_and_contracts()
    validated = ArchitectureContractService.read(
        resolution,
        linked_documents=linked_architecture_fixture_documents(),
    )

    assert validated.schema_version == "resolved-twin-architecture.v2"
    assert validated.content_digest == resolution["content_digest"]


def test_management_reader_accepts_only_active_profile_generation():
    profile = _read(
        CONTRACT_BUNDLE_ROOT
        / "definitions"
        / "profiles"
        / "six-layer-eventing"
        / "1"
        / "profile.json"
    )
    validated = ArchitectureContractService.read(profile)

    assert validated.schema_version == "architecture-profile.v2"
    assert validated.as_dict()["profile_version"] == "1"
    assert validated.content_digest == profile["content_digest"]


def test_digest_and_canonical_json_use_set_semantics():
    _result, _specification, resolution = calculation_result_and_contracts()
    reordered = deepcopy(resolution)
    reordered["component_assignments"].reverse()

    assert calculate_digest(reordered) == resolution["content_digest"]
    assert canonical_json(reordered) == canonical_json(resolution)


def test_management_reader_rejects_unknown_generation():
    with pytest.raises(ContractError) as rejected:
        ArchitectureContractService.read(
            {
                "schema_version": "resolved-twin-architecture.v1",
                "content_digest": "sha256:" + ("0" * 64),
            }
        )

    assert rejected.value.code == "ARCH_VERSION_UNSUPPORTED"
