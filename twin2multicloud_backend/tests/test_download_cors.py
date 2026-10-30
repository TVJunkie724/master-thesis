"""Browser clients must be able to read download metadata, never secrets."""
from fastapi.testclient import TestClient
from src.main import app


def test_local_browser_can_read_download_metadata_headers():
    with TestClient(app) as client:
        response = client.get('/health', headers={'Origin': 'http://127.0.0.1:18924'})
    exposed = {v.strip().lower() for v in response.headers['access-control-expose-headers'].split(',')}
    assert exposed == {'content-disposition', 'x-twin2multicloud-provider', 'x-twin2multicloud-credential-class'}
    assert response.headers['access-control-allow-origin'] == 'http://127.0.0.1:18924'


def test_untrusted_browser_origin_is_not_granted_access():
    with TestClient(app) as client:
        response = client.get('/health', headers={'Origin': 'https://untrusted.example'})
    assert 'access-control-allow-origin' not in response.headers
