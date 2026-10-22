"""Offline checks for the fixed L5 access boundary."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.deployment_access.visualization import (
    MAX_HTML_BYTES, _endpoint, fetch_visualization, validate_visualization_html,
)

HTML = b'<html><section data-bucket-seconds="0" data-point-count="0" data-state="empty"></section><section data-bucket-seconds="3600" data-point-count="1" data-state="data"></section></html>'
URL = 'https://example.lambda-url.eu-central-1.on.aws/'


def output(url=URL):
    return {'aws_component_visualization_output': {'access_url': url,
            'internal_evidence': {'content_revision': 'graphical-l5.v1'}}}


@pytest.mark.parametrize('body', [b'{}', b'', HTML.replace(b'data-state="empty"', b'data-state="data"'),
                                 HTML.replace(b'count="1"', b'count="101"'), b'x' * (MAX_HTML_BYTES + 1)])
def test_rejects_non_graphical_or_invalid_response(body):
    with pytest.raises(ValueError):
        validate_visualization_html(body)


def test_empty_panel_is_readiness_not_data():
    assert validate_visualization_html(HTML) == HTML


@pytest.mark.parametrize('url', ['http://127.0.0.1', 'https://example.com/',
                               URL + '?code=secret', URL + '#token', URL + 'path',
                               'https://user@' + URL.removeprefix('https://')])
def test_rejects_arbitrary_or_credential_bearing_urls(url):
    with pytest.raises(ValueError):
        _endpoint('aws', {'access_url': url})


def test_azure_endpoint_is_fixed_to_app():
    bundle = {'access_url': 'https://l5-app.azurewebsites.net/api/visualization/v1',
              'reader_function_name': 'l5-app'}
    assert _endpoint('azure', bundle) == bundle['access_url']
    with pytest.raises(ValueError):
        _endpoint('azure', bundle | {'reader_function_name': 'other'})


def response(status, body=HTML):
    item = Mock(status_code=status, headers={'Content-Type': 'text/html; charset=utf-8'})
    item.__enter__ = Mock(return_value=item)
    item.__exit__ = Mock(return_value=False)
    item.iter_content.return_value = [body]
    return item


def test_public_endpoint_is_never_accepted(monkeypatch):
    get = Mock(return_value=response(200))
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    with pytest.raises(RuntimeError, match='unauthenticated'):
        fetch_visualization('aws', None, output(), verify_auth=True)
    assert get.call_count == 1


def test_authenticated_read_is_bounded_and_disallows_redirects(monkeypatch):
    from botocore.credentials import Credentials
    provider = SimpleNamespace(region='eu-central-1', clients={'lambda': SimpleNamespace(
        _request_signer=SimpleNamespace(_credentials=Credentials('test', 'test')))})
    get = Mock(side_effect=[response(403), response(200)])
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    assert fetch_visualization('aws', provider, output(), verify_auth=True) == HTML
    assert 'Authorization' in get.call_args.kwargs['headers']
    assert all(call.kwargs['allow_redirects'] is False and call.kwargs['stream'] is True
               for call in get.call_args_list)
    assert all(call.kwargs['timeout'] == 30 for call in get.call_args_list)


def test_reader_alias_fails_before_network(monkeypatch):
    get = Mock()
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    bundle = output()
    bundle['aws_component_visualization_output']['internal_evidence']['content_revision'] = 'raw-history-query.v1'
    with pytest.raises(ValueError, match='L3 JSON'):
        fetch_visualization('aws', None, bundle)
    get.assert_not_called()


def azure_output():
    return {'azure_component_visualization_output': {
        'access_url': 'https://l5-app.azurewebsites.net/api/visualization/v1',
        'reader_function_name': 'l5-app',
        'internal_evidence': {'content_revision': 'graphical-l5.v1'}}}


@pytest.mark.parametrize('first', ['timeout', 503])
def test_azure_initial_readiness_retries_only_transient_failures(monkeypatch, first):
    import requests
    first = requests.ReadTimeout() if first == 'timeout' else response(first)
    get = Mock(side_effect=[first, response(401), response(200)])
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    monkeypatch.setattr('src.deployment_access.visualization.time.sleep', Mock())
    monkeypatch.setattr('src.providers.azure.layers.layer_5_raw_history._reader_key', Mock(return_value='test-key'))
    assert fetch_visualization('azure', None, azure_output(), verify_auth=True) == HTML
    assert get.call_count == 3


def test_azure_readiness_timeout_is_bounded(monkeypatch):
    import requests
    get = Mock(side_effect=requests.ReadTimeout())
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    pause = Mock()
    monkeypatch.setattr('src.deployment_access.visualization.time.sleep', pause)
    with pytest.raises(requests.ReadTimeout):
        fetch_visualization('azure', None, azure_output(), verify_auth=True)
    assert get.call_count == 3 and pause.call_count == 2
    assert all(call.kwargs['timeout'] == 180 for call in get.call_args_list)


def test_azure_initial_readiness_allows_slow_valid_response(monkeypatch):
    import requests
    def delayed_response(*args, **kwargs):
        # The observed valid response took 36 s. Model the former cutoff without
        # sleeping or turning the offline test into another live deployment.
        if kwargs['timeout'] < 36:
            raise requests.ReadTimeout()
        return response(200 if 'headers' in kwargs else 401)
    get = Mock(side_effect=delayed_response)
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    monkeypatch.setattr('src.providers.azure.layers.layer_5_raw_history._reader_key', Mock(return_value='test-key'))
    assert fetch_visualization('azure', None, azure_output(), verify_auth=True) == HTML
    assert get.call_count == 2


def test_azure_ui_read_does_not_retry(monkeypatch):
    import requests
    get = Mock(side_effect=requests.ReadTimeout())
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    monkeypatch.setattr('src.providers.azure.layers.layer_5_raw_history._reader_key', Mock(return_value='test-key'))
    with pytest.raises(requests.ReadTimeout):
        fetch_visualization('azure', None, azure_output())
    assert get.call_count == 1
    assert get.call_args.kwargs['timeout'] == 30


@pytest.mark.parametrize('responses', [[200], [401, 403]])
def test_azure_security_failure_is_not_retried(monkeypatch, responses):
    get = Mock(side_effect=[response(status) for status in responses])
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    monkeypatch.setattr('src.providers.azure.layers.layer_5_raw_history._reader_key', Mock(return_value='test-key'))
    with pytest.raises(RuntimeError):
        fetch_visualization('azure', None, azure_output(), verify_auth=True)
    assert get.call_count == len(responses)


def test_readiness_diagnostics_identify_stage_without_secret_text(monkeypatch, caplog):
    import requests
    get = Mock(side_effect=[response(401), requests.ReadTimeout('secret-key-in-exception')])
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    monkeypatch.setattr('src.providers.azure.layers.layer_5_raw_history._reader_key', Mock(return_value='secret-key'))
    # One request sequence is sufficient to verify logging, without retrying.
    from src.deployment_access.visualization import _fetch_visualization_once
    with caplog.at_level('INFO'), pytest.raises(requests.ReadTimeout):
        _fetch_visualization_once('azure', None, azure_output(), verify_auth=True)
    assert 'phase=unauthenticated' in caplog.text and 'http=401' in caplog.text
    assert 'phase=authenticated' in caplog.text and 'error_type=ReadTimeout' in caplog.text
    assert 'secret-key' not in caplog.text and 'azurewebsites.net' not in caplog.text


@pytest.mark.parametrize('status', [502, 503, 504])
@pytest.mark.parametrize('stage', ['unauthenticated', 'authenticated'])
def test_transient_response_retains_exact_status_and_stage(monkeypatch, caplog, status, stage):
    from src.deployment_access.visualization import _fetch_visualization_once, _L5NotReady
    responses = [response(status)] if stage == 'unauthenticated' else [response(401), response(status)]
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', Mock(side_effect=responses))
    monkeypatch.setattr('src.providers.azure.layers.layer_5_raw_history._reader_key', Mock(return_value='must-not-leak'))
    with caplog.at_level('INFO'), pytest.raises(_L5NotReady) as failure:
        _fetch_visualization_once('azure', None, azure_output(), verify_auth=True)
    assert failure.value.status_code == status
    assert failure.value.request_phase == stage
    assert f'phase={stage}' in caplog.text and f'http={status}' in caplog.text
    assert 'must-not-leak' not in caplog.text and 'azurewebsites.net' not in caplog.text


@pytest.mark.parametrize('body, origin', [
    (b'L5 data unavailable', 'l5-data-unavailable'),
    (b'client_secret=must-not-leak', 'unclassified'),
    (b'L5 data unavailable' + b'x' * 200, 'unclassified'),
])
def test_azure_503_origin_uses_only_the_fixed_public_body(monkeypatch, caplog, body, origin):
    from src.deployment_access.visualization import _fetch_visualization_once, _L5NotReady
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', Mock(side_effect=[response(401), response(503, body)]))
    monkeypatch.setattr('src.providers.azure.layers.layer_5_raw_history._reader_key', Mock(return_value='test-key'))
    with caplog.at_level('INFO'), pytest.raises(_L5NotReady) as failure:
        _fetch_visualization_once('azure', None, azure_output(), verify_auth=True)
    assert failure.value.response_origin == origin
    assert f'origin={origin}' in caplog.text
    assert 'must-not-leak' not in caplog.text
