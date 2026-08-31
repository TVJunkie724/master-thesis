"""Unit coverage for the non-mutating Phase 8 provider probe."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from scripts import probe_phase8_readiness as probe


def test_tracked_credential_examples_include_split_azure_authority() -> None:
    for path in (
        probe.ROOT / "config_credentials.json.example",
        probe.ROOT
        / "3-cloud-deployer"
        / "upload"
        / "template"
        / "config_credentials.json.example",
        probe.ROOT
        / "3-cloud-deployer"
        / "templates"
        / "digital-twin"
        / "config_credentials.json.example",
    ):
        azure = json.loads(path.read_text(encoding="utf-8"))["azure"]
        assert azure["azure_client_id"] != azure["azure_preparation_client_id"]
        assert azure["azure_client_secret"] != azure[
            "azure_preparation_client_secret"
        ]


def test_location_normalization_matches_azure_region_spellings() -> None:
    assert probe._normalize_location("West Europe") == "westeurope"
    assert probe._normalize_location("westeurope") == "westeurope"


def test_latest_stable_api_version_excludes_preview_versions() -> None:
    resource_type = {
        "apiVersions": ["2026-01-01-preview", "2025-10-01", "2024-01-01"]
    }

    assert probe._latest_stable_api_version(resource_type) == "2025-10-01"


def test_gcp_effective_limit_prefers_exact_region_bucket() -> None:
    quotas = [
        {
            "relevant_limits": [
                {
                    "metric": "compute.googleapis.com/cpus",
                    "effective_limits": [
                        {"dimensions": {}, "effective_limit": "32"},
                        {
                            "dimensions": {"region": "europe-west1"},
                            "effective_limit": "200",
                        },
                    ],
                }
            ]
        }
    ]

    assert (
        probe._gcp_effective_limit(
            quotas,
            "compute.googleapis.com/cpus",
            dimension_value="europe-west1",
        )
        == 200
    )


def test_minimum_status_fails_closed_for_missing_or_small_limit() -> None:
    assert probe._minimum_status(None, 1) == "unknown"
    assert probe._minimum_status(10, 10, 1) == "blocked"
    assert probe._minimum_status(10, 9, 1) == "passed"


def test_sensitive_provider_scope_and_secret_values_are_rejected() -> None:
    credentials = {
        "aws": {"aws_access_key_id": "ACCESS-EXAMPLE"},
        "azure": {
            "azure_subscription_id": "SUBSCRIPTION-EXAMPLE",
            "azure_preparation_client_id": "PREPARATION-CLIENT-EXAMPLE",
            "azure_preparation_client_secret": "PREPARATION-SECRET-EXAMPLE",
        },
        "gcp": {"gcp_project_id": "PROJECT-EXAMPLE"},
    }
    record = {"status": "safe", "checked_at": datetime.now(timezone.utc).isoformat()}
    probe._assert_sensitive_values_absent(record, credentials)

    with pytest.raises(ValueError, match="gcp_project_id"):
        probe._assert_sensitive_values_absent(
            {"unsafe": "PROJECT-EXAMPLE"}, credentials
        )

    with pytest.raises(ValueError, match="azure_preparation_client_secret"):
        probe._assert_sensitive_values_absent(
            {"unsafe": "PREPARATION-SECRET-EXAMPLE"}, credentials
        )
