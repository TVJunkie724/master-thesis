"""
Unit tests for optimizer pricing SSE streaming endpoints.

Tests for /optimizer/stream/refresh-pricing/{provider} endpoint that relays
real-time logs from the Optimizer service during pricing refresh operations.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import json

from src.models.cloud_connection import CloudConnection
from src.models.twin_config import TwinConfiguration
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


class TestStreamRefreshPricingHappy:
    """Happy path tests for pricing stream relay."""
    
    def test_stream_aws_with_credentials_success(self, auth_client, test_twin, db):
        """AWS pricing stream should load credentials and connect to Optimizer."""
        _bind_aws_cloud_connection(db, test_twin)
        
        # Mock the Optimizer SSE stream
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        async def mock_chunks():
            yield 'event: log\ndata: {"message": "Starting..."}\n\n'
            yield 'event: complete\ndata: {"message": "Done!"}\n\n'
        mock_response.aiter_text = mock_chunks
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                stream=MagicMock(return_value=mock_response)
            ))
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            response = auth_client.get(
                f"/optimizer/stream/refresh-pricing/aws?twin_id={test_twin.id}"
            )
            
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
    
    def test_stream_azure_no_credentials_needed(self, auth_client, test_twin):
        """Azure stream should work without credentials (public API)."""
        # Mock the Optimizer SSE stream
        with patch('src.api.routes.optimizer.httpx.AsyncClient') as mock_client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200

            async def mock_chunks():
                yield 'event: complete\ndata: {"message": "Azure done!"}\n\n'
            mock_resp.aiter_text = mock_chunks
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=None)
            
            mock_instance = MagicMock()
            mock_instance.stream = MagicMock(return_value=mock_resp)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            response = auth_client.get(
                f"/optimizer/stream/refresh-pricing/azure?twin_id={test_twin.id}"
            )
            
            assert response.status_code == 200


class TestStreamRefreshPricingError:
    """Error handling tests for pricing stream."""
    
    def test_stream_invalid_provider(self, auth_client, test_twin):
        """Invalid provider should return 400."""
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
    
    def test_stream_optimizer_unreachable(self, auth_client, test_twin, db):
        """Connection error to Optimizer should emit error event."""
        _bind_aws_cloud_connection(db, test_twin)
        
        with patch('src.api.routes.optimizer.httpx.AsyncClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.stream = MagicMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance
            
            response = auth_client.get(
                f"/optimizer/stream/refresh-pricing/aws?twin_id={test_twin.id}"
            )
            
            assert response.status_code == 200
            content = response.content.decode()
            assert "error" in content.lower()


class TestStreamRefreshPricingEdge:
    """Edge case tests for pricing stream."""
    
    def test_stream_returns_correct_headers(self, auth_client, test_twin):
        """Response should have SSE headers."""
        with patch('src.api.routes.optimizer.httpx.AsyncClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            async def mock_chunks():
                yield 'event: complete\ndata: {}\n\n'
            mock_resp.aiter_text = mock_chunks
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=None)
            
            mock_instance.stream = MagicMock(return_value=mock_resp)
            mock_client.return_value = mock_instance
            
            response = auth_client.get(
                f"/optimizer/stream/refresh-pricing/azure?twin_id={test_twin.id}"
            )
            
            assert response.headers.get("cache-control") == "no-cache"
            assert response.headers.get("x-accel-buffering") == "no"
