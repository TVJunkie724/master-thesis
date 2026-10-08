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


def test_reader_alias_fails_before_network(monkeypatch):
    get = Mock()
    monkeypatch.setattr('src.deployment_access.visualization.requests.get', get)
    bundle = output()
    bundle['aws_component_visualization_output']['internal_evidence']['content_revision'] = 'raw-history-query.v1'
    with pytest.raises(ValueError, match='L3 JSON'):
        fetch_visualization('aws', None, bundle)
    get.assert_not_called()
