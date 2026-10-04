import importlib.util
from pathlib import Path
from unittest.mock import Mock
import uuid

import pytest

from scripts.run_event_l4_evaluation import ALLOWED, review, processed_fixture, EventExperiment
from scripts.run_l4_evaluation import Experiment
from scripts.prepare_l4_evaluation import EXPECTED


def plan():
    return {'resource_changes': [{'mode': 'managed', 'address': a, 'change': {'actions': ['create']}} for a in ALLOWED]}


def test_exact_research_cut_has_no_image_cluster_or_graphical_resources():
    assert len(ALLOWED) == 33
    review(plan())
    assert not any(a.startswith(('azurerm_', 'google_', 'aws_grafana_', 'aws_ecr_', 'aws_ecs_')) for a in ALLOWED)


@pytest.mark.parametrize('change', ['extra', 'missing', 'duplicate', 'update'])
def test_scope_rejects_any_unreviewed_change(change):
    value = plan()
    if change == 'extra':
        value['resource_changes'].append({'mode': 'managed', 'address': 'aws_grafana_workspace.extra', 'change': {'actions': ['create']}})
    elif change == 'missing':
        value['resource_changes'].pop()
    elif change == 'duplicate':
        value['resource_changes'].append(value['resource_changes'][0])
    else:
        value['resource_changes'][0]['change']['actions'] = ['update']
    with pytest.raises(RuntimeError, match='SCOPE_REJECTED'):
        review(value)


def test_isolated_l4_allowlist_unchanged():
    base = object.__new__(Experiment)
    base.provider = 'aws'
    assert base.allowed_resources() == EXPECTED['aws']
    assert object.__new__(EventExperiment).allowed_resources() == ALLOWED


def test_fixture_routes_through_real_projection_and_expected_identity(monkeypatch):
    path = Path(__file__).resolve().parents[2] / '3-cloud-deployer/src/providers/aws/lambda_functions/six-layer-domain/handler.py'
    spec = importlib.util.spec_from_file_location('event_l4_domain', path)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    monkeypatch.setenv('SIX_LAYER_EVALUATION_SCOPE', 'full')
    monkeypatch.setenv('TWIN_PROVIDER', 'aws')
    monkeypatch.setenv('TWINMAKER_WORKSPACE', 'test-workspace')
    client = Mock()
    client.update_entity.return_value = {'state': 'ACTIVE'}
    monkeypatch.setattr(runtime, '_client', lambda _: client)
    event = processed_fixture('l4-aws-test')
    runtime._validate_canonical_event(event)
    runtime._project_twin(event)
    props = client.update_entity.call_args.kwargs['componentUpdates']['telemetry']['propertyUpdates']
    assert props['value']['value']['doubleValue'] == 20.5
    assert props['sourceSequence']['value']['stringValue'] == event['source_sequence']
    assert props['lastEventId']['value']['stringValue'] == str(uuid.uuid5(uuid.NAMESPACE_URL, event['event_id'] + ':twin.state.upserted'))
