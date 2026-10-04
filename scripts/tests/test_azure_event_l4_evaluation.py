import json
from unittest.mock import Mock

import pytest

from scripts.run_azure_event_l4_evaluation import ALLOWED, review, expected_projection, AzureEventExperiment
from scripts.run_event_l4_evaluation import processed_fixture
from scripts.l4_projection_check import load_adapter


def plan():
    return {'resource_changes': [{'mode': 'managed', 'address': a, 'change': {'actions': ['create']}} for a in ALLOWED]}


def test_exact_fixed_cut_has_no_ingress_device_or_l5():
    assert len(ALLOWED) == 45
    review(plan())
    assert not any(a.startswith(('aws_', 'google_', 'azurerm_iothub.', 'azurerm_dashboard_grafana.')) for a in ALLOWED)
    assert 'azurerm_role_assignment.azure_azure_entra_layer_access_bindings["twin_projection_writer"]' in ALLOWED
    assert 'azurerm_eventhub_consumer_group.domain_standard["twin-state-update"]' in ALLOWED


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
