"""Focused tests for the Optimizer's dark architecture-profile reader."""

from __future__ import annotations

import json

import pytest

from backend.architecture_profiles import contracts


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_optimizer_accepts_canonical_profile_without_runtime_selection():
    profile = _read(
        contracts.CONTRACT_ROOT
        / "fixtures"
        / "valid"
        / "five-layer-baseline-profile.json"
    )
    validated = contracts.read_contract(profile)
    assert validated.stable_id == "five-layer-baseline"
    assert validated.content_digest == profile["content_digest"]


def test_optimizer_rejects_tampered_profile():
    wrapper = _read(
        contracts.CONTRACT_ROOT / "fixtures" / "invalid" / "digest-tamper.json"
    )
    with pytest.raises(contracts.ContractError) as raised:
        contracts.read_contract(wrapper["document"])
    assert raised.value.code == "ARCH_DIGEST_MISMATCH"
