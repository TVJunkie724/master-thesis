"""Tests for the provider cleanup registry boundary."""

import pytest

from src.providers import cleanup_registry
from src.providers.cleanup_registry import (
    CleanupRequest,
    cleanup_provider_resources,
    normalize_cleanup_provider,
    supported_cleanup_providers,
)


def test_supported_cleanup_providers_are_explicit_and_sorted():
    assert supported_cleanup_providers() == ("aws", "azure", "gcp")


def test_google_alias_normalizes_to_gcp():
    assert normalize_cleanup_provider("google") == "gcp"


def test_unknown_cleanup_provider_fails_with_supported_list():
    with pytest.raises(ValueError, match="Supported providers: aws, azure, gcp"):
        cleanup_provider_resources(
            CleanupRequest(
                provider="oracle",
                credentials={},
                prefix="factory-twin",
            )
        )


def test_aws_cleanup_dispatch_maps_contract_to_provider_signature(monkeypatch):
    calls = []

    def fake_cleanup_aws_resources(
        credentials,
        prefix,
        cleanup_identity_user=False,
        platform_user_email="",
        dry_run=False,
    ):
        calls.append((credentials, prefix, cleanup_identity_user, platform_user_email, dry_run))

    monkeypatch.setattr(
        cleanup_registry,
        "cleanup_aws_resources",
        fake_cleanup_aws_resources,
    )

    cleanup_provider_resources(
        CleanupRequest(
            provider="aws",
            credentials={"aws": {"region": "eu-central-1"}},
            prefix="factory-twin",
            cleanup_identity_user=True,
            platform_user_email="owner@example.test",
            dry_run=True,
        )
    )

    assert calls == [
        (
            {"aws": {"region": "eu-central-1"}},
            "factory-twin",
            True,
            "owner@example.test",
            True,
        )
    ]


def test_azure_cleanup_dispatch_maps_contract_to_provider_signature(monkeypatch):
    calls = []

    def fake_cleanup_azure_resources(
        credentials,
        prefix,
        cleanup_entra_user=False,
        platform_user_email="",
        dry_run=False,
    ):
        calls.append((credentials, prefix, cleanup_entra_user, platform_user_email, dry_run))

    monkeypatch.setattr(
        cleanup_registry,
        "cleanup_azure_resources",
        fake_cleanup_azure_resources,
    )

    cleanup_provider_resources(
        CleanupRequest(
            provider="azure",
            credentials={"azure": {"subscription": "sub"}},
            prefix="factory-twin",
            cleanup_identity_user=True,
            platform_user_email="owner@example.test",
            dry_run=True,
        )
    )

    assert calls == [
        (
            {"azure": {"subscription": "sub"}},
            "factory-twin",
            True,
            "owner@example.test",
            True,
        )
    ]


def test_gcp_cleanup_dispatch_ignores_identity_user_options(monkeypatch):
    calls = []

    def fake_cleanup_gcp_resources(credentials, prefix, dry_run=False):
        calls.append((credentials, prefix, dry_run))

    monkeypatch.setattr(
        cleanup_registry,
        "cleanup_gcp_resources",
        fake_cleanup_gcp_resources,
    )

    cleanup_provider_resources(
        CleanupRequest(
            provider="google",
            credentials={"gcp": {"project": "demo"}},
            prefix="factory-twin",
            cleanup_identity_user=True,
            platform_user_email="owner@example.test",
            dry_run=True,
        )
    )

    assert calls == [
        (
            {"gcp": {"project": "demo"}},
            "factory-twin",
            True,
        )
    ]
