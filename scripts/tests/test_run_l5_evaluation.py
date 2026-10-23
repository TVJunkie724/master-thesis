from datetime import datetime, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import requests
from scripts.run_l5_evaluation import AWS_ALLOWED, AZURE_ALLOWED, Experiment, fixture, review, state_empty, verify_html
from scripts.tests.test_l5_visualization import module


@pytest.mark.parametrize('provider,allowed', [('aws', AWS_ALLOWED), ('azure', AZURE_ALLOWED)])
def test_exact_create_only_plan(provider, allowed):
    changes = [{'mode': 'managed', 'address': address, 'change': {'actions': ['create'],
                'after': {'maximum_instance_count': 1, 'always_ready': []}}} for address in sorted(allowed)]
    assert review({'resource_changes': changes}, provider) == len(allowed)
    changes[0]['change']['actions'] = ['update']
    with pytest.raises(RuntimeError):
        review({'resource_changes': changes}, provider)


@pytest.mark.parametrize('capacity', [{'maximum_instance_count': 2},
                                     {'maximum_instance_count': 1, 'always_ready': [{'instance_count': 1}]}, {}])
def test_azure_rejects_warm_or_unknown_capacity(capacity):
    changes = [{'mode': 'managed', 'address': address, 'change': {'actions': ['create'],
                'after': capacity}} for address in AZURE_ALLOWED]
    with pytest.raises(RuntimeError, match='CAPACITY_SCOPE_REJECTED'):
        review({'resource_changes': changes}, 'azure')


def test_azure_rejects_unknown_warm_capacity():
    changes = [{'mode': 'managed', 'address': address, 'change': {'actions': ['create'],
                'after': {'maximum_instance_count': 1}, 'after_unknown': {'always_ready': True}}}
               for address in AZURE_ALLOWED]
    with pytest.raises(RuntimeError, match='CAPACITY_SCOPE_REJECTED'):
        review({'resource_changes': changes}, 'azure')


def experiment(tmp_path):
    result = object.__new__(Experiment)
    result.provider, result.root = 'azure', tmp_path
    result.report = {'http_observations': []}
    result.auth_headers = Mock(return_value={'x-functions-key': 'synthetic-private-key'})
    return result


@pytest.mark.parametrize('body,origin', [(b'L5 data unavailable', 'l5-data-unavailable'),
                                       (b'private upstream error', 'unclassified'),
                                       (b' ' * 128 + b'L5 data unavailable', 'unclassified')])
def test_response_classification_retains_no_secret_or_body(tmp_path, monkeypatch, body, origin):
    exp = experiment(tmp_path)
    response = SimpleNamespace(status_code=503, content=body)
    get = Mock(return_value=response)
    monkeypatch.setattr(requests, 'get', get)
    assert exp.fetch('https://synthetic.invalid/private-url', app='visualization') is response
    observation = exp.report['http_observations'][0]
    assert observation['http_status'] == 503 and observation['response_origin'] == origin
    assert get.call_args.kwargs['timeout'] == 180
    assert get.call_args.kwargs['allow_redirects'] is False
    saved = (tmp_path / 'http-observations.json').read_text()
    assert 'synthetic-private-key' not in saved and 'private-url' not in saved
    assert 'private upstream error' not in saved


def test_client_timeout_not_misclassified_as_http_503(tmp_path, monkeypatch):
    exp = experiment(tmp_path)
    monkeypatch.setattr(requests, 'get', Mock(side_effect=requests.ReadTimeout('private detail')))
    with pytest.raises(requests.ReadTimeout):
        exp.fetch('https://synthetic.invalid', app='visualization')
    observation = exp.report['http_observations'][0]
    assert observation['error_type'] == 'ReadTimeout' and 'http_status' not in observation
    assert 'private detail' not in json.dumps(observation)


def test_direct_reader_diagnostic_cannot_claim_l5_pass(tmp_path):
    exp = experiment(tmp_path)
    exp.outputs = {'reader_url': 'https://synthetic.invalid/reader'}
    exp.points = fixture()
    responses = []
    for time_key, value_key in [('stored_at', 'value'), ('bucket_start', 'avg')]:
        responses.append(Mock(status_code=200, json=Mock(return_value={
            'schema_version': 'raw-history-query.v1', 'device_id': 'l5-device', 'metric': 'temperature',
            'truncated': False, 'next_cursor': None,
            'points': [{time_key: p['time'], value_key: p['value']} for p in exp.points]})))
    exp.fetch = Mock(side_effect=responses)
    exp.diagnose_reader()
    assert all(item['passed'] for item in exp.report['reader_diagnostics'])
    assert not exp.report.get('functional_pass')


def test_failed_reader_diagnostic_records_class_only(tmp_path):
    exp = experiment(tmp_path)
    exp.outputs, exp.points = {'reader_url': 'https://synthetic.invalid/reader'}, fixture()
    exp.fetch = Mock(side_effect=requests.ReadTimeout('private detail'))
    exp.diagnose_reader()
    assert all(not item['passed'] and item['error_type'] == 'ReadTimeout'
               for item in exp.report['reader_diagnostics'])
    assert 'private detail' not in (tmp_path / 'reader-diagnostics.json').read_text()


def test_package_module_residual_is_not_empty_state():
    assert state_empty({'resources': [{'mode': 'data'}]})
    assert not state_empty({'child_modules': [{'resources': [{'mode': 'managed'}]}]})


def test_diagnostic_is_after_l5_and_not_a_pre_warm(tmp_path):
    exp = experiment(tmp_path)
    exp.points = fixture()
    exp.outputs = {'reader_url': 'reader', 'visualization_url': 'visualization'}
    exp.fetch = Mock(return_value=Mock(status_code=500))
    # A failed authenticated L5 response remains a failure, regardless of later diagnostics.
    with pytest.raises(RuntimeError, match='L5_AUTHENTICATED_READ_FAILED'):
        exp.verify_surface()
    exp.fetch.assert_called_once_with('visualization', app='visualization')
    assert not exp.report.get('functional_pass')


def test_azure_transient_failures_leave_time_for_reader_followup(tmp_path, monkeypatch):
    from scripts import run_l5_evaluation as runner
    exp = experiment(tmp_path)
    exp.outputs = {'visualization_url': 'visualization'}
    exp.fetch = Mock(return_value=Mock(status_code=503))
    monkeypatch.setattr(runner.time, 'sleep', Mock())
    with pytest.raises(RuntimeError, match='L5_READINESS_DEADLINE'):
        exp.verify_surface()
    assert exp.fetch.call_count == 3
    assert exp.report['last_http_status'] == 503
    assert not exp.report.get('functional_pass')


@pytest.mark.parametrize('provider', ['aws', 'azure'])
def test_extra_resource_rejected(provider):
    with pytest.raises(RuntimeError):
        review({'resource_changes': [{'mode': 'managed', 'address': 'extra', 'change': {'actions': ['create']}}]}, provider)


def test_exact_cloud_svg_verification():
    now = datetime(2026, 10, 5, 13, 10, tzinfo=timezone.utc)
    points = fixture(now)
    def fetch(q):
        bucket = q['bucket_seconds']
        return {'schema_version': 'raw-history-query.v1', 'device_id': 'l5-device', 'metric': 'temperature',
                'truncated': False, 'next_cursor': None,
                'points': [({'stored_at': p['time'], 'value': p['value']} if bucket == '0' else
                            {'bucket_start': p['time'], 'avg': p['value']}) for p in points]}
    html = module.page(fetch, 'l5-device', 'temperature', now)
    verify_html(html, points)
    with pytest.raises(RuntimeError):
        verify_html(html.replace('data-value="42"', 'data-value="43"', 1), points)
    with pytest.raises(RuntimeError):
        verify_html(html.replace(points[0]['time'], '2026-01-01T00:00:00Z'), points)
