"""
Inter-Cloud HTTP Communication Module for Azure Functions.

Centralized HTTP POST logic for all multi-cloud sender functions.
This module is used by: Connector, Persister, Hot-to-Cold Mover,
Cold-to-Archive Mover, and Digital Twin Data Connector.

Source: src/providers/azure/azure_functions/_shared/inter_cloud.py
Editable: Yes - This is shared runtime code packaged with Azure Functions
"""
import json
import time
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Optional


# ==========================================
# Constants
# ==========================================

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # seconds
DEFAULT_TIMEOUT = 30  # seconds


# ==========================================
# Payload Envelope Builder
# ==========================================

def build_envelope(
    payload: Any,
    target_layer: str,
    message_type: str = "telemetry",
    source_cloud: str = "azure"
) -> dict:
    """
    Build standardized inter-cloud payload envelope per technical_specs.md.
    
    All cross-cloud messages use this envelope format for consistency
    and traceability across cloud providers.
    
    Args:
        payload: The actual data to send (device telemetry, chunk data, etc.)
        target_layer: Destination layer (e.g., "L2", "L3", "L3_cold")
        message_type: Type of message (default: "telemetry")
        source_cloud: Originating cloud provider (default: "azure")
    
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


def validate_token(headers: dict, expected_token: str) -> bool:
    """
    Validate X-Inter-Cloud-Token from incoming HTTP request headers.
    
    Used by receiver functions (Ingestion, Writers, Readers) to
    authenticate incoming cross-cloud requests.
    
    Note: Azure Functions provides headers directly, unlike Lambda's event format.
    
    Args:
        headers: Request headers dict from Azure HttpRequest
        expected_token: The token this endpoint expects
    
    Returns:
        bool: True if token is valid, False otherwise
    """
    if not expected_token:
        print("WARNING: No expected token configured - rejecting all requests")
        return False
    
    # Headers may be lowercase or mixed case
    received_token = (
        headers.get("x-inter-cloud-token") or 
        headers.get("X-Inter-Cloud-Token") or
        ""
    )
    
    if not received_token:
        print("No X-Inter-Cloud-Token header in request")
        return False
    
    if received_token != expected_token:
        print("Token mismatch - invalid authentication")
        return False
    
    return True


def build_auth_error_response() -> dict:
    """Build standardized 401 response for authentication failures."""
    return {
        "statusCode": 401,
        "body": json.dumps({"error": "Unauthorized", "message": "Invalid or missing X-Inter-Cloud-Token"})
    }
