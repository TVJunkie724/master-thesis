import copy

import pytest

from scripts.prepare_l4_evaluation import EXPECTED, review


def plan(provider):
    return {'resource_changes': [{'mode': 'managed', 'address': a,
                                 'change': {'actions': ['create']}}
                                for a in EXPECTED[provider]]}


@pytest.mark.parametrize('provider,count', [('aws', 7), ('azure', 2)])
def test_exact_infrastructure_cut(provider, count):
    assert review(provider, plan(provider)) == count


@pytest.mark.parametrize('actions', [['delete'], ['update'], ['delete', 'create'], ['no-op']])
def test_existing_state_or_mutation_rejected(actions):
    value = plan('aws')
    value['resource_changes'][0]['change']['actions'] = actions
    with pytest.raises(RuntimeError, match='SCOPE_REJECTED'):
        review('aws', value)


@pytest.mark.parametrize('provider', ['aws', 'azure'])
def test_extra_missing_and_duplicate_resources_rejected(provider):
    value = plan(provider)
    for changes in (value['resource_changes'][:-1],
                    value['resource_changes'] + [copy.deepcopy(value['resource_changes'][0])],
                    value['resource_changes'] + [{'mode': 'managed', 'address': 'aws_lambda_function.unapproved',
                                                 'change': {'actions': ['create']}}]):
        with pytest.raises(RuntimeError, match='SCOPE_REJECTED'):
            review(provider, {'resource_changes': changes})


def test_unrelated_azure_role_map_is_not_admitted():
    value = plan('azure')
    value['resource_changes'].append({'mode': 'managed',
        'address': 'azurerm_role_assignment.azure_azure_entra_layer_access_bindings["twin_seed_deployer"]',
        'change': {'actions': ['create']}})
    with pytest.raises(RuntimeError, match='SCOPE_REJECTED'):
        review('azure', value)
