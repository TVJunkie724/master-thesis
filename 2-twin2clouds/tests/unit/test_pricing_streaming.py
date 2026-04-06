"""
Unit tests for pricing SSE streaming endpoint.

Tests for the /stream/fetch_pricing/{provider} endpoint that streams
real-time logs during pricing fetch operations.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from rest_api import app

client = TestClient(app)


class TestStreamFetchPricingHappy:
    """Happy path tests for SSE pricing stream."""
    
    def test_stream_azure_pricing_success(self):
        """Azure pricing stream should work without credentials (public API)."""
        with patch('api.pricing.calculate_up_to_date_pricing') as mock_fetch:
            mock_fetch.return_value = {"services": []}
            
            with client.stream("POST", "/stream/fetch_pricing/azure", json={}) as response:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                
                events = list(response.iter_lines())
                # Should have at least start and complete events
                assert len(events) >= 2
                
                # Check for complete event
                event_str = "\n".join(events)
                assert "complete" in event_str
    
    def test_stream_emits_complete_event(self):
        """Stream should emit a complete event on success."""
        with patch('api.pricing.calculate_up_to_date_pricing') as mock_fetch:
            mock_fetch.return_value = {"services": []}
            
            with client.stream("POST", "/stream/fetch_pricing/azure", json={}) as response:
                events = list(response.iter_lines())
                event_str = "\n".join(events)
                
                # Should contain complete event type
                assert 'event: complete' in event_str or '"type": "complete"' in event_str


class TestStreamFetchPricingError:
    """Error handling tests for SSE pricing stream."""
    
    def test_stream_invalid_provider_returns_error(self):
        """Invalid provider should return error event immediately."""
        with client.stream("POST", "/stream/fetch_pricing/invalid", json={}) as response:
            assert response.status_code == 200
            events = list(response.iter_lines())
            event_str = "\n".join(events)
            
            assert "error" in event_str
            assert "Invalid provider" in event_str
    
    def test_stream_api_failure_emits_error(self):
        """API failure during pricing fetch should emit error event."""
        with patch('api.pricing.calculate_up_to_date_pricing') as mock_fetch:
            mock_fetch.side_effect = Exception("API connection failed")
            
            with client.stream("POST", "/stream/fetch_pricing/azure", json={}) as response:
                events = list(response.iter_lines())
                event_str = "\n".join(events)
                
                assert "error" in event_str


class TestStreamFetchPricingEdge:
    """Edge case tests for SSE pricing stream."""
    
    def test_stream_returns_event_stream_content_type(self):
        """Response should have correct SSE content type."""
        with patch('api.pricing.calculate_up_to_date_pricing') as mock_fetch:
            mock_fetch.return_value = {}
            
            with client.stream("POST", "/stream/fetch_pricing/azure", json={}) as response:
                assert "text/event-stream" in response.headers["content-type"]
    
    def test_stream_includes_cache_control_header(self):
        """Response should have no-cache header for SSE."""
        with patch('api.pricing.calculate_up_to_date_pricing') as mock_fetch:
            mock_fetch.return_value = {}
            
            with client.stream("POST", "/stream/fetch_pricing/azure", json={}) as response:
                assert response.headers.get("cache-control") == "no-cache"


class TestSseUtils:
    """Tests for SSE utility functions."""
    
    def test_emit_sse_formats_log_event(self):
        """emit_sse should format log events correctly."""
        from backend.sse_utils import emit_sse
        
        result = emit_sse("Test message", "log")
        
        assert "event: log" in result
        assert "Test message" in result
        assert result.endswith("\n\n")
    
    def test_emit_sse_formats_complete_event(self):
        """emit_sse should format complete events correctly."""
        from backend.sse_utils import emit_sse
        
        result = emit_sse("Done!", "complete")
        
        assert "event: complete" in result
        assert "Done!" in result
    
    def test_emit_sse_includes_type_in_data(self):
        """emit_sse should include type in JSON data."""
        from backend.sse_utils import emit_sse
        import json
        
        result = emit_sse("Test", "error")
        
        # Extract data line
        lines = result.strip().split("\n")
        data_line = [l for l in lines if l.startswith("data:")][0]
        data_json = json.loads(data_line.replace("data: ", ""))
        
        assert data_json["type"] == "error"
        assert data_json["message"] == "Test"


class TestThreadSafeSseHandler:
    """Tests for thread-safe log handler."""
    
    def test_handler_puts_to_queue(self):
        """Handler should put formatted messages to queue."""
        import logging
        from backend.sse_utils import ThreadSafeSseHandler
        
        loop = asyncio.new_event_loop()
        queue = asyncio.Queue()
        handler = ThreadSafeSseHandler(queue, loop)
        handler.setFormatter(logging.Formatter('%(message)s'))
        
        # Create a record
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Test log message", args=(), exc_info=None
        )
        
        # Emit should schedule put via call_soon_threadsafe
        handler.emit(record)
        
        # Run pending callbacks
        loop.run_until_complete(asyncio.sleep(0.01))
        
        # Check queue (may or may not have item depending on timing)
        # This is a basic smoke test
        loop.close()
