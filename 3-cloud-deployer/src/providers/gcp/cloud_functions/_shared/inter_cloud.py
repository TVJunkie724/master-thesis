"""
Inter-Cloud HTTP Communication Module for GCP.

Centralized HTTP POST logic for all multi-cloud sender functions.
This module is used by: Connector, Persister, Hot-to-Cold Mover,
Cold-to-Archive Mover, and Digital Twin Data Connector.

Source: src/providers/gcp/cloud_functions/_shared/inter_cloud.py
Editable: Yes - This is shared runtime code packaged with Cloud Functions
"""
import json
import time
import base64
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Optional

# Google Auth for ID token (GCP service-to-service authentication)
try:
    import google.auth.transport.requests
    import google.oauth2.id_token
    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    _GOOGLE_AUTH_AVAILABLE = False


# ==========================================
# Constants
# ==========================================

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # seconds
DEFAULT_TIMEOUT = 30  # seconds

# Token cache for performance (ID tokens valid ~1 hour)
_token_cache = {}
_TOKEN_REFRESH_MARGIN = 60  # Refresh 60 seconds before expiry


# ==========================================
# GCP Service-to-Service Authentication
# ==========================================

def _get_token_expiry(token: str) -> float:
    """
    Parse the expiry time from a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Expiry timestamp as float, or current_time + 3600 if parsing fails
    """
    try:
        # JWT format: header.payload.signature
        payload = token.split('.')[1]
        # Add padding if needed for base64 decoding
        payload += '=' * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        return float(decoded.get('exp', time.time() + 3600))
    except Exception:
        # Fallback to 1 hour if parsing fails
        return time.time() + 3600


def get_id_token_headers(target_url: str) -> dict:
    """
    Get headers with ID token for GCP Cloud Functions Gen2 service-to-service calls.
    
    Uses caching to avoid fetching a new token on every request.
    Tokens are refreshed 60 seconds before their actual expiry.
    
    Args:
        target_url: The URL of the target Cloud Function (used as audience)
    
    Returns:
        dict: Headers including Authorization bearer token and Content-Type
    
    Raises:
        ValueError: If target_url is empty or invalid
        RuntimeError: If google-auth library is unavailable or token fetch fails
    """
    global _token_cache
    
    # Validate URL
    if not target_url or not target_url.startswith('http'):
        raise ValueError(f"Invalid target URL for ID token: {target_url}")
    
    headers = {"Content-Type": "application/json"}
    
    if not _GOOGLE_AUTH_AVAILABLE:
        raise RuntimeError("google-auth library not available - required for GCP service-to-service calls")
    
    # Check cache
    cache_key = target_url
    cached = _token_cache.get(cache_key)
    if cached and time.time() < cached["expiry"] - _TOKEN_REFRESH_MARGIN:
        headers["Authorization"] = f"Bearer {cached['token']}"
        return headers
    
    try:
        auth_req = google.auth.transport.requests.Request()
        id_token = google.oauth2.id_token.fetch_id_token(auth_req, target_url)
        headers["Authorization"] = f"Bearer {id_token}"
        
        # Cache token with actual expiry from JWT
        _token_cache[cache_key] = {
            "token": id_token,
            "expiry": _get_token_expiry(id_token)
        }
        print(f"ID token obtained for {target_url[:50]}...")
    except Exception as e:
        raise RuntimeError(f"Failed to get ID token for {target_url}: {e}")
    
    return headers


# ==========================================
# Payload Envelope Builder
# ==========================================

def build_envelope(
    payload: Any,
    target_layer: str,
    message_type: str = "telemetry",
    source_cloud: str = "gcp"
) -> dict:
    """
    Build standardized inter-cloud payload envelope per technical_specs.md.
    
    All cross-cloud messages use this envelope format for consistency
    and traceability across cloud providers.
    
    Args:
        payload: The actual data to send (device telemetry, chunk data, etc.)
        target_layer: Destination layer (e.g., "L2", "L3", "L3_cold")
        message_type: Type of message (default: "telemetry")
        source_cloud: Originating cloud provider (default: "gcp")
    
    Returns:
        dict: Standardized envelope with metadata and payload
    """
    return {
        "source_cloud": source_cloud,
        "target_layer": target_layer,
        "message_type": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
        "trace_id": str(uuid.uuid4())
    }


# ==========================================
# HTTP POST with Retry
# ==========================================

def post_to_remote(
    url: str,
    token: str,
    payload: Any,
    target_layer: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES
) -> dict:
    """
    POST data to remote cloud endpoint with exponential backoff retry.
    
    This is the core function for all cross-cloud HTTP communication.
    It builds the envelope, adds authentication, and handles retries.
    
    Args:
        url: Target endpoint URL (Function URL or API Gateway)
        token: Inter-cloud authentication token (X-Inter-Cloud-Token)
        payload: Data to send (will be wrapped in envelope)
        target_layer: Destination layer for envelope metadata
        timeout: HTTP request timeout in seconds (default: 30)
        max_retries: Maximum retry attempts for server/network errors
    
    Returns:
        dict: Response with statusCode and body
    
    Raises:
        ValueError: If url or token is empty
        urllib.error.HTTPError: On client errors (4xx) or exhausted retries
        Exception: On network errors after exhausted retries
    """
    if not url:
        raise ValueError("Remote URL is required for inter-cloud POST")
    if not token:
        raise ValueError("Inter-cloud token is required for authentication")
    
    # Build envelope and encode
    envelope = build_envelope(payload, target_layer)
    data = json.dumps(envelope, default=str).encode('utf-8')
    
    headers = {
        'Content-Type': 'application/json',
        'X-Inter-Cloud-Token': token
    }
    
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    retry_delay = RETRY_BASE_DELAY
    
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return {
                    "statusCode": response.getcode(),
                    "body": response.read().decode('utf-8')
                }
        
        except urllib.error.HTTPError as e:
            # Read error body for better debugging
            error_body = ""
            try:
                error_body = e.read().decode('utf-8')
            except Exception:
                pass
            
            # Client error (4xx): Do not retry - fail fast
            if 400 <= e.code < 500:
                print(f"Client Error ({e.code}): {e.reason}. Body: {error_body}. Not retrying.")
                raise e
            
            # Server error (5xx): Retry with backoff
            if attempt < max_retries:
                print(f"Server Error ({e.code}): {e.reason}. Body: {error_body}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"Max retries exceeded. Last error: {e.code} {e.reason}. Body: {error_body}")
                raise e
        
        except urllib.error.URLError as e:
            # Network/connection error: Retry with backoff
            if attempt < max_retries:
                print(f"Network error (attempt {attempt + 1}): {e.reason}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"Max retries exceeded. Network error: {e.reason}")
                raise e
        
        except Exception as e:
            # Other errors: Retry with backoff
            if attempt < max_retries:
                print(f"Error (attempt {attempt + 1}): {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"Max retries exceeded. Error: {e}")
                raise e


def post_raw(
    url: str,
    token: str,
    payload: dict,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES
) -> dict:
    """
    POST raw payload to remote endpoint (no envelope wrapping).
    
    Used by movers that have specialized payload formats (chunked data)
    which don't fit the standard envelope structure.
    
    Args:
        url: Target endpoint URL
        token: Inter-cloud authentication token
        payload: Raw payload dict (already in final format)
        timeout: HTTP request timeout in seconds
        max_retries: Maximum retry attempts
    
    Returns:
        dict: Response with statusCode and body
    
    Raises:
        ValueError: If url or token is empty
        urllib.error.HTTPError: On client errors or exhausted retries
    """
    if not url:
        raise ValueError("Remote URL is required for inter-cloud POST")
    if not token:
        raise ValueError("Inter-cloud token is required for authentication")
    
    data = json.dumps(payload, default=str).encode('utf-8')
    
    headers = {
        'Content-Type': 'application/json',
        'X-Inter-Cloud-Token': token
    }
    
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    retry_delay = RETRY_BASE_DELAY
    
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return {
                    "statusCode": response.getcode(),
                    "body": response.read().decode('utf-8')
                }
        
        except urllib.error.HTTPError as e:
            # Read error body for better debugging
            error_body = ""
            try:
                error_body = e.read().decode('utf-8')
            except Exception:
                pass
            
            if 400 <= e.code < 500:
                print(f"Client Error ({e.code}): {e.reason}. Body: {error_body}. Not retrying.")
                raise e
            
            if attempt < max_retries:
                print(f"Server Error ({e.code}): {e.reason}. Body: {error_body}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"Max retries exceeded. Last error: {e.code} {e.reason}. Body: {error_body}")
                raise e
        
        except urllib.error.URLError as e:
            if attempt < max_retries:
                print(f"Network error (attempt {attempt + 1}): {e.reason}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"Max retries exceeded. Network error: {e.reason}")
                raise e
        
        except Exception as e:
            if attempt < max_retries:
                print(f"Error (attempt {attempt + 1}): {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print(f"Max retries exceeded. Error: {e}")
                raise e


def validate_token(request, expected_token: str) -> bool:
    """
    Validate X-Inter-Cloud-Token from incoming HTTP request.
    
    Used by receiver functions (Ingestion, Writers, Readers) to
    authenticate incoming cross-cloud requests.
    
    Args:
        request: Flask/functions_framework request object
        expected_token: The token this endpoint expects
    
    Returns:
        bool: True if token is valid, False otherwise
    """
    if not expected_token:
        print("WARNING: No expected token configured - rejecting all requests")
        return False
    
    # Get token from headers (Cloud Functions use Flask-style request)
    received_token = (
        request.headers.get("X-Inter-Cloud-Token") or
        request.headers.get("x-inter-cloud-token") or
        ""
    )
    
    if not received_token:
        print("No X-Inter-Cloud-Token header in request")
        return False
    
    if received_token != expected_token:
        print("Token mismatch - invalid authentication")
        return False
    
    return True


def build_auth_error_response():
    """Build standardized 401 response for authentication failures."""
    return (
        json.dumps({"error": "Unauthorized", "message": "Invalid or missing X-Inter-Cloud-Token"}),
        401,
        {"Content-Type": "application/json"}
    )
