"""Bounded renderer contract; no cloud, data or credential access."""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import pytest

SOURCE = Path(__file__).resolve().parents[2] / "3-cloud-deployer/src/runtime/six_layer_eventing/visualization.py"
spec = importlib.util.spec_from_file_location("l5_visualization", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def payload(bucket):
    return {"schema_version": "raw-history-query.v1", "device_id": "device", "metric": "temperature",
            "truncated": False, "next_cursor": None,
            "points": [{"stored_at": "2026-10-05T12:00:00Z", "value": 42}] if bucket == '0' else
                      [{"bucket_start": "2026-10-05T12:00:00Z", "avg": 41, "min": 40, "max": 42, "count": 2}]}


def test_authenticated_contract_two_charts():
    calls = []
    def fetch(query):
        calls.append(query)
        return payload(query['bucket_seconds'])
    html = module.page(fetch, 'device', 'temperature', datetime(2026, 10, 5, 13, tzinfo=timezone.utc))
    assert [q['bucket_seconds'] for q in calls] == ['0', '3600']
    assert all(q['limit'] == '100' for q in calls)
    assert html.count('<svg ') == 2
    assert 'data-value="42"' in html and 'data-value="41"' in html


@pytest.mark.parametrize('change', [
    {'points': []}, {'points': [{'stored_at': '2026-10-05T12:00:00Z', 'value': float('nan')}]},
    {'points': [{'stored_at': '2026-10-05T12:00:00Z', 'value': True}]},
    {'schema_version': 'other'}, {'truncated': True}, {'next_cursor': 'cursor'}, {'device_id': 'other'},
])
def test_no_false_ready(change):
    with pytest.raises(ValueError):
        module.page(lambda q: payload(q['bucket_seconds']) | change, 'device', 'temperature')


def test_no_unescaped_labels():
    def fetch(q):
        return payload(q['bucket_seconds']) | {'device_id': '<script>', 'metric': '<b>'}
    html = module.page(fetch, '<script>', '<b>')
    assert '<script>' not in html and '&lt;script&gt;' in html


def test_reader_failure_propagates():
    def fetch(q):
        raise PermissionError('denied')
    with pytest.raises(PermissionError):
        module.page(fetch, 'device', 'temperature')


def test_fresh_deployment_reports_empty_without_claiming_data():
    html = module.page(lambda q: payload(q['bucket_seconds']) | {'points': []},
                       'device', 'temperature', allow_empty=True)
    assert html.count('data-state="empty"') == 2
    assert html.count('data-point-count="0"') == 2
    assert '<svg' not in html


def test_normal_view_discloses_bounded_results_without_exposing_cursor():
    html = module.page(lambda q: payload(q['bucket_seconds']) |
                       {'truncated': True, 'next_cursor': 'private-pagination-token'},
                       'device', 'temperature', allow_empty=True)
    assert html.count('additional records are not shown') == 2
    assert 'private-pagination-token' not in html


@pytest.mark.parametrize('change', [{'schema_version': 'bad'}, {'truncated': 'false'},
                                   {'points': [], 'truncated': True, 'next_cursor': 'cursor'}])
def test_empty_mode_still_rejects_invalid_reader_contract(change):
    with pytest.raises(ValueError):
        module.page(lambda q: payload(q['bucket_seconds']) | change,
                    'device', 'temperature', allow_empty=True)


def test_azure_response_is_html_without_client_credentials():
    import azure.functions as func
    response = func.HttpResponse('<!doctype html>', status_code=200, headers=module.HEADERS)
    assert response.headers['Content-Type'] == 'text/html; charset=utf-8'
    assert response.headers['Cache-Control'] == 'no-store'
    assert "default-src 'none'" in response.headers['Content-Security-Policy']
