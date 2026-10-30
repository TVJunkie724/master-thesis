import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.run_azure_event_l4_evaluation import ALLOWED, review, expected_projection, AzureEventExperiment
from scripts.run_event_l4_evaluation import processed_fixture
from scripts.l4_projection_check import load_adapter
from scripts import run_azure_event_l4_evaluation as runner


def plan():
    return {'resource_changes': [{'mode': 'managed', 'address': a, 'change': {'actions': ['create']}} for a in ALLOWED]}


def test_exact_fixed_cut_has_no_ingress_device_or_l5():
    assert len(ALLOWED) == 45
    review(plan())
    assert not any(a.startswith(('aws_', 'google_', 'azurerm_iothub.', 'azurerm_dashboard_grafana.')) for a in ALLOWED)
    assert 'azurerm_role_assignment.azure_azure_entra_layer_access_bindings["twin_projection_writer"]' in ALLOWED
    assert 'azurerm_eventhub_consumer_group.domain_standard["twin-state-update"]' in ALLOWED


@pytest.mark.parametrize('missing_module', ['azure.eventhub', 'websocket'])
def test_missing_publisher_sdk_fails_before_output_or_cloud_work(tmp_path, monkeypatch, missing_module):
    output = tmp_path / 'unstarted'
    def import_module(name):
        if name == missing_module:
            raise ModuleNotFoundError(name)
        return Mock()
    missing = Mock(side_effect=import_module)
    monkeypatch.setattr(runner.importlib, 'import_module', missing)
    with pytest.raises(ModuleNotFoundError):
        runner.run(SimpleNamespace(output_dir=output))
    assert missing.call_args.args == (missing_module,)
    assert not output.exists()


def test_partial_cut_does_not_require_cold_storage_outputs():
    source = (Path(__file__).resolve().parents[2] / '3-cloud-deployer/src/terraform/azure_six_layer.tf').read_text()
    for layer in ('cool', 'archive'):
        block = source.split('output "azure_component_' + layer + '_storage_output" {', 1)[1].split('\n}\n', 1)[0]
        assert 'value = local.azure_six_layer_' + layer + '_enabled ? try({' in block
        assert '}, null) : null' in block
    assert not any('azure_azure_blob_cool' in address for address in ALLOWED)


@pytest.mark.parametrize('mutation', ['extra', 'missing', 'duplicate', 'update'])
def test_scope_rejects_unreviewed_changes(mutation):
    data = plan()
    if mutation == 'extra':
        data['resource_changes'].append({'mode': 'managed', 'address': 'azurerm_iothub.extra', 'change': {'actions': ['create']}})
    elif mutation == 'missing':
        data['resource_changes'].pop()
    elif mutation == 'duplicate':
        data['resource_changes'].append(data['resource_changes'][0])
    else:
        data['resource_changes'][0]['change']['actions'] = ['update']
    with pytest.raises(RuntimeError, match='SCOPE_REJECTED'):
        review(data)


def test_expected_identity_matches_actual_domain_projection():
    runtime, _ = load_adapter('azure')
    event = processed_fixture('l4-azure-offline')
    assert expected_projection(event)['event_id'] == runtime.build_twin_projection(event)['event_id']


@pytest.mark.parametrize('foreign', [False, True])
def test_state_validates_child_module_addresses(tmp_path, foreign):
    experiment = object.__new__(AzureEventExperiment)
    experiment.folder = tmp_path
    (tmp_path / 'fresh.tfstate').touch()
    address = 'module.azure_six_layer_ingress_package[0].azurerm_storage_blob.package'
    data = {'values': {'root_module': {'child_modules': [{'resources': [
        {'mode': 'managed', 'address': 'foreign.resource' if foreign else address, 'values': {}}]}]}}}
    output = tmp_path / 'show.json'
    output.write_text(json.dumps(data))
    experiment.terraform = Mock(return_value=output)
    if foreign:
        with pytest.raises(RuntimeError, match='STATE_SCOPE_REJECTED'):
            experiment.state()
    else:
        assert experiment.state() == {address: {}}
