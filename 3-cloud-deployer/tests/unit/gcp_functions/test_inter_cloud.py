"""Unit tests for GCP inter_cloud module - ID token authentication."""
import time
import pytest
from unittest.mock import patch, MagicMock

# Import the module under test
import sys
from pathlib import Path

# Add the GCP cloud functions path
gcp_funcs_path = Path(__file__).parent.parent.parent.parent / "src" / "providers" / "gcp" / "cloud_functions"
sys.path.insert(0, str(gcp_funcs_path))

from _shared.inter_cloud import _get_token_expiry, get_id_token_headers, _token_cache


class TestGetTokenExpiry:
    """Tests for _get_token_expiry helper."""
    
    def test_valid_jwt_token(self):
        """Should parse exp claim from valid JWT."""
        # JWT with exp=1700000000 (Nov 14, 2023)
        # Header: {"alg":"RS256","typ":"JWT"}
        # Payload: {"exp":1700000000}
        token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3MDAwMDAwMDB9.signature"
        expiry = _get_token_expiry(token)
        assert expiry == 1700000000.0
    
    def test_invalid_token_returns_fallback(self):
        """Should return current_time + 3600 for invalid tokens."""
        before = time.time()
        expiry = _get_token_expiry("invalid.token")
        after = time.time()
        assert before + 3500 < expiry < after + 3700
    
    def test_empty_token_returns_fallback(self):
        """Should handle empty string gracefully."""
        expiry = _get_token_expiry("")
        assert expiry > time.time()
    
    def test_malformed_base64_returns_fallback(self):
        """Should handle malformed base64 in payload."""
        token = "header.!!!invalid_base64!!!.signature"
        before = time.time()
        expiry = _get_token_expiry(token)
        after = time.time()
        assert before + 3500 < expiry < after + 3700


class TestGetIdTokenHeaders:
    """Tests for get_id_token_headers function."""
    
    def setup_method(self):
        """Clear token cache before each test."""
        _token_cache.clear()
    
    def test_invalid_url_raises_value_error(self):
        """Should raise ValueError for invalid URLs."""
        with pytest.raises(ValueError, match="Invalid target URL"):
            get_id_token_headers("")
        with pytest.raises(ValueError, match="Invalid target URL"):
            get_id_token_headers("not-a-url")
    
    def test_none_url_raises_value_error(self):
        """Should raise ValueError for None URL."""
        with pytest.raises(ValueError, match="Invalid target URL"):
            get_id_token_headers(None)
    
    def test_ftp_url_raises_value_error(self):
        """Should raise ValueError for non-http URLs."""
        with pytest.raises(ValueError, match="Invalid target URL"):
            get_id_token_headers("ftp://example.com")
    
    @patch('_shared.inter_cloud._GOOGLE_AUTH_AVAILABLE', False)
    def test_missing_google_auth_raises_runtime_error(self):
        """Should raise RuntimeError if google-auth not installed."""
        with pytest.raises(RuntimeError, match="google-auth library not available"):
            get_id_token_headers("https://example.com")
    
    @patch('_shared.inter_cloud._GOOGLE_AUTH_AVAILABLE', True)
    @patch('google.oauth2.id_token.fetch_id_token')
    @patch('google.auth.transport.requests.Request')
    def test_token_fetch_failure_raises_runtime_error(self, mock_request, mock_fetch):
        """Should raise RuntimeError if token fetch fails."""
        mock_fetch.side_effect = Exception("Auth failed")
        mock_request.return_value = MagicMock()
        with pytest.raises(RuntimeError, match="Failed to get ID token"):
            get_id_token_headers("https://example.com")
    
    @patch('_shared.inter_cloud._GOOGLE_AUTH_AVAILABLE', True)
    @patch('google.oauth2.id_token.fetch_id_token')
    @patch('google.auth.transport.requests.Request')
    def test_successful_token_returns_auth_header(self, mock_request, mock_fetch):
        """Should return Authorization header with token."""
        # Create a mock token with exp claim
        mock_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.sig"
        mock_fetch.return_value = mock_token
        mock_request.return_value = MagicMock()
        
        headers = get_id_token_headers("https://example.com")
        
        assert "Authorization" in headers
        assert headers["Authorization"] == f"Bearer {mock_token}"
        assert headers["Content-Type"] == "application/json"
    
    @patch('_shared.inter_cloud._GOOGLE_AUTH_AVAILABLE', True)
    @patch('google.oauth2.id_token.fetch_id_token')
    @patch('google.auth.transport.requests.Request')
    def test_token_is_cached(self, mock_request, mock_fetch):
        """Should cache token after successful fetch."""
        mock_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.sig"
        mock_fetch.return_value = mock_token
        mock_request.return_value = MagicMock()
        
        url = "https://example.com/function"
        
        # First call - should fetch token
        headers1 = get_id_token_headers(url)
        assert mock_fetch.call_count == 1
        
        # Second call - should use cache
        headers2 = get_id_token_headers(url)
        assert mock_fetch.call_count == 1  # Still 1, not 2
        
        assert headers1["Authorization"] == headers2["Authorization"]
    
    @patch('_shared.inter_cloud._GOOGLE_AUTH_AVAILABLE', True)
    @patch('google.oauth2.id_token.fetch_id_token')
    @patch('google.auth.transport.requests.Request')
    def test_different_urls_get_different_cache_entries(self, mock_request, mock_fetch):
        """Should cache tokens per URL."""
        mock_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.sig"
        mock_fetch.return_value = mock_token
        mock_request.return_value = MagicMock()
        
        get_id_token_headers("https://example.com/func1")
        get_id_token_headers("https://example.com/func2")
        
        # Should have called fetch_id_token twice (different URLs)
        assert mock_fetch.call_count == 2
