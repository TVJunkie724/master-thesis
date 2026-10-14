"""Tests for explicit pre-destroy cleanup outcomes."""

from types import SimpleNamespace
import json
from unittest.mock import Mock

import pytest

from src.providers.terraform import pre_destroy


@pytest.mark.parametrize('dry_run', [False, True])
def test_sns_archive_cleanup_uses_only_owned_state_topics(tmp_path, monkeypatch, dry_run):
    context = SimpleNamespace(credentials={'aws': {
        'aws_region': 'eu-central-1', 'aws_access_key_id': 'test', 'aws_secret_access_key': 'test',
    }}, config=SimpleNamespace(digital_twin_name='factory'))
    state = tmp_path / 'terraform.tfstate'
    owned = 'arn:aws:sns:eu-central-1:123456789012:factory-control.fifo'
    state.write_text(json.dumps({'resources': [{
        'mode': 'managed', 'type': 'aws_sns_topic', 'instances': [
            {'attributes': {'arn': owned, 'archive_policy': '{"MessageRetentionPeriod":1}'}},
            {'attributes': {'arn': 'arn:aws:sns:eu-central-1:123456789012:unrelated.fifo', 'archive_policy': '{}'}},
            {'attributes': {'arn': 'arn:aws:sns:eu-central-1:123456789012:factory-no-archive.fifo', 'archive_policy': None}},
        ],
    }]}))
    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setattr('boto3.client', factory)
    pre_destroy.disable_owned_sns_archives(context, state, dry_run=dry_run)
    if dry_run:
        factory.assert_not_called()
    else:
        client.set_topic_attributes.assert_called_once_with(
            TopicArn=owned, AttributeName='ArchivePolicy', AttributeValue='{}'
        )


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
