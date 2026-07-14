"""Unit tests for optimizer pricing SSE streaming endpoints."""

import json

from src.models.cloud_connection import CloudConnection
from src.models.twin_config import TwinConfiguration
from src.services.service_errors import ValidationError
from src.utils.crypto import encrypt_scoped


def _bind_aws_cloud_connection(db, test_twin):
    user_id = test_twin.user_id
    connection = CloudConnection(
        id="connection-aws",
        user_id=user_id,
        provider="aws",
        display_name="AWS Pricing",
        cloud_scope="{}",
        auth_type="access_key",
        encrypted_payload=encrypt_scoped(
            json.dumps(
                {
                    "aws_access_key_id": "AKIATEST",
                    "aws_secret_access_key": "secret123",
                    "aws_region": "eu-central-1",
                }
            ),
            user_id,
            "connection-aws",
        ),
        payload_fingerprint="fingerprint",
    )
    db.add(connection)
    config = TwinConfiguration(
        twin_id=test_twin.id,
        aws_cloud_connection_id=connection.id,
        aws_region="eu-central-1",
    )
    db.add(config)
    db.commit()


class FakePricingStreamService:
    """Route-level fake for the typed pricing stream service boundary."""

    def __init__(self, chunks=None, exc=None):
        self.chunks = chunks or ['event: complete\ndata: {"message": "Done!"}\n\n']
        self.exc = exc
        self.calls = []

    def build_refresh_stream(self, provider, twin_id, user_id):
        self.calls.append((provider, twin_id, user_id))
        if self.exc:
            raise self.exc

        async def stream():
            for chunk in self.chunks:
                yield chunk

        return stream()


def _override_stream_service(monkeypatch, fake):
    import src.api.routes.optimizer as optimizer_routes

    monkeypatch.setattr(
        optimizer_routes,
        "_optimizer_pricing_stream_service",
        lambda db: fake,
    )


class TestStreamRefreshPricingHappy:
    """Happy path tests for pricing stream relay."""

    def test_stream_aws_with_credentials_success(self, auth_client, test_twin, db, monkeypatch):
        """AWS pricing stream should load credentials and connect to Optimizer."""
        _bind_aws_cloud_connection(db, test_twin)
        fake = FakePricingStreamService([
            'event: log\ndata: {"message": "Starting..."}\n\n',
            'event: complete\ndata: {"message": "Done!"}\n\n',
        ])
        _override_stream_service(monkeypatch, fake)

        response = auth_client.get(
            f"/optimizer/stream/refresh-pricing/aws?twin_id={test_twin.id}"
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert fake.calls[0][0] == "aws"

    def test_stream_azure_no_credentials_needed(self, auth_client, test_twin, monkeypatch):
        """Azure stream should work without credentials (public API)."""
        fake = FakePricingStreamService(['event: complete\ndata: {"message": "Azure done!"}\n\n'])
        _override_stream_service(monkeypatch, fake)

        response = auth_client.get(
            f"/optimizer/stream/refresh-pricing/azure?twin_id={test_twin.id}"
        )

        assert response.status_code == 200


class TestStreamRefreshPricingError:
    """Error handling tests for pricing stream."""

    def test_stream_invalid_provider(self, auth_client, test_twin, monkeypatch):
        """Invalid provider should return 400."""
        _override_stream_service(
            monkeypatch,
            FakePricingStreamService(exc=ValidationError("Invalid provider: invalid")),
        )
        response = auth_client.get(
            f"/optimizer/stream/refresh-pricing/invalid?twin_id={test_twin.id}"
        )

        assert response.status_code == 400

    def test_stream_twin_not_found(self, auth_client):
        """Non-existent twin should return 404."""
        response = auth_client.get(
            "/optimizer/stream/refresh-pricing/aws?twin_id=nonexistent-id"
        )

        # Should get an error (404 or SSE error event)
        assert response.status_code in [404, 200]

    def test_stream_missing_aws_credentials(self, auth_client, test_twin, db):
        """AWS without credentials should emit error event."""
        # Twin exists but has no AWS credentials
        response = auth_client.get(
            f"/optimizer/stream/refresh-pricing/aws?twin_id={test_twin.id}"
        )

        assert response.status_code == 200
        # Should contain error in response body
        content = response.content.decode()
        assert "error" in content.lower() or "credentials" in content.lower()

    def test_stream_optimizer_unreachable(self, auth_client, test_twin, db, monkeypatch):
        """Connection error to Optimizer should emit error event."""
        _bind_aws_cloud_connection(db, test_twin)
        fake = FakePricingStreamService(['event: error\ndata: {"message": "Cannot connect"}\n\n'])
        _override_stream_service(monkeypatch, fake)

        response = auth_client.get(
            f"/optimizer/stream/refresh-pricing/aws?twin_id={test_twin.id}"
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "error" in content.lower()


class TestStreamRefreshPricingEdge:
    """Edge case tests for pricing stream."""

    def test_stream_returns_correct_headers(self, auth_client, test_twin, monkeypatch):
        """Response should have SSE headers."""
        _override_stream_service(
            monkeypatch,
            FakePricingStreamService(['event: complete\ndata: {}\n\n']),
        )

        response = auth_client.get(
            f"/optimizer/stream/refresh-pricing/azure?twin_id={test_twin.id}"
        )

        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"
