"""Tests for explicit pre-destroy cleanup outcomes."""

from types import SimpleNamespace
import json
from unittest.mock import Mock

import pytest

from src.providers.terraform import pre_destroy


def test_twinmaker_without_sdk_paginator_reads_all_pages():
    client = Mock()
    client.can_paginate.return_value = False
    client.list_workspaces.side_effect = [
        {"workspaceSummaries": [{"workspaceId": "first"}], "nextToken": "page-2"},
        {"workspaceSummaries": [{"workspaceId": "second"}]},
    ]
    assert list(pre_destroy._paginate(client, "list_workspaces", "workspaceSummaries")) == [
        {"workspaceId": "first"}, {"workspaceId": "second"},
    ]
    client.get_paginator.assert_not_called()
    assert client.list_workspaces.call_args_list[0].kwargs == {}
    assert client.list_workspaces.call_args_list[1].kwargs == {"nextToken": "page-2"}


def test_pre_destroy_preserves_sdk_paginator_and_scope():
    client = Mock()
    client.can_paginate.return_value = True
    paginator = client.get_paginator.return_value
    paginator.paginate.return_value = [{"entitySummaries": [{"entityId": "one"}]}]
    assert list(pre_destroy._paginate(client, "list_entities", "entitySummaries", workspaceId="owned")) == [{"entityId": "one"}]
    paginator.paginate.assert_called_once_with(workspaceId="owned")


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


@pytest.mark.parametrize("shared", [False, True])
def test_simulator_cleanup_removes_only_exclusive_configured_identity(monkeypatch, shared):
    context = SimpleNamespace(credentials={"aws": {
        "aws_region": "eu-central-1", "aws_access_key_id": "test", "aws_secret_access_key": "test",
    }}, config=SimpleNamespace(digital_twin_name="owned", iot_devices=[{"id": "sensor"}]))
    client = Mock()
    target = "arn:aws:iot:eu-central-1:123456789012:cert/test-certificate"
    client.list_targets_for_policy.return_value = {"targets": [target]}
    client.list_principal_things.return_value = {"things": ["unrelated" if shared else "owned-sensor"]}
    client.list_attached_policies.return_value = {"policies": [{"policyName": "owned-sensor-policy"}]}
    client.list_policy_versions.return_value = {"policyVersions": [{"versionId": "1", "isDefaultVersion": True}]}
    monkeypatch.setattr("boto3.client", Mock(return_value=client))
    if shared:
        with pytest.raises(RuntimeError, match="shared"):
            pre_destroy.cleanup_aws_simulator_identities(context, dry_run=False)
        client.detach_policy.assert_not_called()
        client.delete_certificate.assert_not_called()
        client.delete_policy.assert_not_called()
    else:
        pre_destroy.cleanup_aws_simulator_identities(context, dry_run=False)
        client.detach_thing_principal.assert_called_once_with(thingName="owned-sensor", principal=target)
        client.delete_certificate.assert_called_once_with(certificateId="test-certificate")
        client.delete_policy.assert_called_once_with(policyName="owned-sensor-policy")


def test_simulator_cleanup_dry_run_does_not_create_client(monkeypatch):
    factory = Mock()
    monkeypatch.setattr("boto3.client", factory)
    context = SimpleNamespace(credentials={"aws": {"aws_region": "eu-central-1"}},
                              config=SimpleNamespace(iot_devices=[{"id": "sensor"}]))
    pre_destroy.cleanup_aws_simulator_identities(context, dry_run=True)
    factory.assert_not_called()


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
