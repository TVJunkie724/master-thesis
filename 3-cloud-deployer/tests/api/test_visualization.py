"""The fixed HTML route consumes one operation package, never a client URL."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import visualization


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(visualization.router)
    return TestClient(app)


def test_package_header_is_required(client):
    assert client.get('/projects/test/visualization').status_code == 422


@pytest.mark.parametrize('provider', ['aws', 'azure'])
@pytest.mark.parametrize('fail', [False, True])
def test_fixed_output_and_package_cleanup(client, monkeypatch, tmp_path, provider, fail):
    released = []

    @contextmanager
    def acquire(name, token):
        assert (name, token) == ('test', 'one-shot')
        try:
            yield tmp_path
        finally:
            released.append(True)

    context = SimpleNamespace(config=SimpleNamespace(providers={'layer_5_provider': provider}),
                              credentials={}, providers={provider: object()})
    outputs = {'owned-output': 'not-a-client-url'}
    monkeypatch.setattr(visualization, 'operation_project_path', acquire)
    monkeypatch.setattr(visualization, 'ProjectConfigLoader', lambda: SimpleNamespace(
        create_context_from_path=Mock(return_value=context)))
    initialize = Mock()
    monkeypatch.setattr(visualization, 'initialize_providers', initialize)
    load = Mock(return_value=outputs)
    monkeypatch.setattr(visualization, 'load_terraform_outputs', load)
    fetch = Mock(side_effect=RuntimeError('secret=do-not-leak') if fail else None,
                 return_value=b'<html>two charts</html>')
    monkeypatch.setattr(visualization, 'fetch_visualization', fetch)
    response = client.get('/projects/test/visualization', headers={'X-Operation-Package': 'one-shot'})
    assert released == [True]
    initialize.assert_called_once_with(context, {'layer_5_provider': provider}, context.credentials)
    load.assert_called_once_with('test', tmp_path)
    fetch.assert_called_once_with(provider, context.providers[provider], outputs)
    assert response.status_code == (502 if fail else 200)
    assert 'do-not-leak' not in response.text
    if not fail:
        assert response.headers['content-type'].startswith('text/html')
        assert response.headers['cache-control'] == 'no-store'
