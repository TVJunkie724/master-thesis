from datetime import datetime, timezone
import pytest
from scripts.run_l5_evaluation import AWS_ALLOWED, AZURE_ALLOWED, fixture, review, verify_html
from scripts.tests.test_l5_visualization import module


@pytest.mark.parametrize('provider,allowed', [('aws', AWS_ALLOWED), ('azure', AZURE_ALLOWED)])
def test_exact_create_only_plan(provider, allowed):
    changes = [{'mode': 'managed', 'address': address, 'change': {'actions': ['create']}} for address in sorted(allowed)]
    assert review({'resource_changes': changes}, provider) == len(allowed)
    changes[0]['change']['actions'] = ['update']
    with pytest.raises(RuntimeError):
        review({'resource_changes': changes}, provider)


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
