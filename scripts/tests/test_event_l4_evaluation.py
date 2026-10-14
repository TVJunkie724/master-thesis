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
    assert len(ALLOWED) == 34  # Includes the bounded local IAM propagation wait.
    review(plan())
    assert not any(a.startswith(('azurerm_', 'google_', 'aws_grafana_', 'aws_ecr_', 'aws_ecs_')) for a in ALLOWED)


def test_partial_event_cut_does_not_require_storage_mover_log_output():
    source = (Path(__file__).resolve().parents[2] / '3-cloud-deployer/src/terraform/outputs.tf').read_text()
    assert 'local.aws_six_layer_storage_mover_enabled ? try({' in source
    assert '"L3-storage-mover" = aws_cloudwatch_log_group.aws_aws_cloudwatch[0].name\n    }, {}) : {}' in source
    assert not any('aws_aws_cloudwatch' in address for address in ALLOWED)


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


@pytest.mark.parametrize('diagnostic_error', [False, True])
def test_failed_event_cut_retains_diagnostics_without_blocking_cleanup(tmp_path, monkeypatch, diagnostic_error):
    from scripts import run_event_l4_evaluation as runner
    experiment = object.__new__(EventExperiment)
    experiment.apply_started, experiment.folder = True, tmp_path
    experiment.variables, experiment.report = {}, {'functional_pass': False}
    diagnostic = Mock(side_effect=TimeoutError() if diagnostic_error else None, return_value={'logs': []})
    monkeypatch.setattr(runner.core, 'diagnostics', diagnostic)
    cleanup = Mock(return_value=True)
    monkeypatch.setattr(Experiment, 'cleanup', cleanup)
    assert experiment.cleanup() is True
    cleanup.assert_called_once()
    assert (tmp_path / 'runtime-diagnostics.json').exists() is not diagnostic_error
    assert ('diagnostics_error_type' in experiment.report) is diagnostic_error


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
