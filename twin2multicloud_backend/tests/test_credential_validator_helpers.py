"""Tests for legacy credential helper provider normalization."""

from src.api.helpers.credential_validator import (
    build_deployer_credentials,
    build_optimizer_credentials,
    get_required_fields,
)


def test_credential_helpers_accept_google_alias_as_gcp():
    raw = {
        "project_id": "alias-project",
        "service_account_json": "{}",
        "region": "europe-west1",
    }

    assert build_optimizer_credentials("Google", raw) == {
        "project_id": "alias-project",
        "service_account_json": "{}",
    }
    assert build_deployer_credentials("Google", raw) == {
        "project_id": "alias-project",
        "service_account_json": "{}",
        "region": "europe-west1",
    }
    assert get_required_fields("Google") == get_required_fields("gcp")
