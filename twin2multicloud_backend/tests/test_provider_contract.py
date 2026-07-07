"""Tests for provider identifier boundary contracts."""

import pytest

from src.services.provider_contract import (
    is_gcp_provider,
    normalize_optional_provider_id,
    normalize_provider_id,
    provider_id_for_deployer_api,
    provider_id_for_deployer_project,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("AWS", "aws"),
        (" azure ", "azure"),
        ("GCP", "gcp"),
        ("Google", "gcp"),
    ],
)
def test_normalize_provider_id_returns_canonical_management_id(value, expected):
    assert normalize_provider_id(value) == expected


def test_normalize_optional_provider_id_preserves_absence():
    assert normalize_optional_provider_id(None) is None
    assert normalize_optional_provider_id(" ") is None


def test_normalize_provider_id_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        normalize_provider_id("oracle")


def test_deployer_project_contract_uses_google_for_gcp():
    assert provider_id_for_deployer_project("GCP") == "google"
    assert provider_id_for_deployer_project("google") == "google"
    assert provider_id_for_deployer_project("aws") == "aws"


def test_deployer_api_contract_uses_canonical_provider_ids():
    assert provider_id_for_deployer_api("Google") == "gcp"
    assert provider_id_for_deployer_api(None) == "aws"


def test_is_gcp_provider_accepts_every_gcp_alias():
    assert is_gcp_provider("GCP") is True
    assert is_gcp_provider("google") is True
    assert is_gcp_provider("aws") is False
