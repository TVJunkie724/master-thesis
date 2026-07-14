"""Tests for explicit pre-destroy cleanup outcomes."""

from types import SimpleNamespace

import pytest

from src.providers.terraform import pre_destroy


def _azure_context():
    return SimpleNamespace(
        credentials={
            "azure": {
                "azure_tenant_id": "tenant",
                "azure_client_id": "client",
                "azure_client_secret": "secret",
                "azure_subscription_id": "subscription",
            }
        },
        config=SimpleNamespace(digital_twin_name="factory-twin"),
    )


def test_azure_diagnostic_errors_fail_the_pre_destroy_step(monkeypatch):
    class Helper:
        def __init__(self, *_args):
            pass

        def cleanup_orphaned_by_prefix(self, prefix, *, dry_run):
            assert prefix == "factory-twin"
            assert dry_run is True
            return {"errors": 2}

    monkeypatch.setattr(
        "azure.identity.ClientSecretCredential",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        "src.providers.azure.diagnostic_settings_helper.DiagnosticSettingsHelper",
        Helper,
    )

    with pytest.raises(RuntimeError, match="reported 2 errors"):
        pre_destroy.cleanup_azure_diagnostics(_azure_context(), dry_run=True)


def test_missing_azure_credentials_skip_diagnostic_cleanup(monkeypatch):
    monkeypatch.setattr(
        "azure.identity.ClientSecretCredential",
        lambda **_kwargs: pytest.fail("credential must not be created"),
    )
    context = SimpleNamespace(credentials={})

    pre_destroy.cleanup_azure_diagnostics(context, dry_run=False)
