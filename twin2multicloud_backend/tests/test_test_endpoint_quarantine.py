"""Tests for test-only endpoint quarantine."""

from src.config import settings
from src.main import app


def test_test_endpoints_are_not_registered_by_default(authenticated_client):
    client, headers = authenticated_client

    assert settings.ENABLE_TEST_ENDPOINTS is False
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/twins/{twin_id}/test-deploy" not in route_paths
    assert "/twins/{twin_id}/test-destroy" not in route_paths
    assert "/twins/{twin_id}/test-log-trace/start" not in route_paths
    assert "/twins/{twin_id}/simulator/test-download" not in route_paths

    response = client.post("/twins/not-a-real-twin/test-deploy", headers=headers)
    assert response.status_code == 404
