"""Focused tests for the Deployer's non-executing profile reader."""

from __future__ import annotations

import json

import pytest

from src.architecture_profiles import contracts


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


def test_deployer_rejects_secret_like_fields_before_execution():
    wrapper = _read(
        contracts.CONTRACT_ROOT / "fixtures" / "invalid" / "secret-like-field.json"
    )
    with pytest.raises(contracts.ContractError) as raised:
        contracts.read_contract(wrapper["document"])
    assert raised.value.code == "ARCH_SECRET_FIELD_FORBIDDEN"
