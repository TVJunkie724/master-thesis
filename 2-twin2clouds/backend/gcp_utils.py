"""
GCP Service Account Utilities

Shared utility for parsing GCP Service Account credentials from either:
- File path (for CLI/legacy usage)
- Raw JSON content (for API/UI uploads)

This module is duplicated identically in both:
- 2-twin2clouds/backend/gcp_utils.py (Optimizer)
- 3-cloud-deployer/src/utils/gcp_utils.py (Deployer)

Any changes should be synchronized between both copies.
"""
import json
import os
from pathlib import Path
from typing import Tuple, Dict, Any

from google.oauth2 import service_account


def parse_gcp_service_account(credentials_input: str) -> Tuple[Dict[str, Any], Dict[str, str], service_account.Credentials]:
    """
    Parse GCP Service Account from file path OR raw JSON content.
    
    Detects input type automatically:
    - If starts with '{': treats as raw JSON content
    - Otherwise: treats as file path
    
    Args:
        credentials_input: Either a file path to the SA JSON file,
                          OR the raw JSON content string
        
    Returns:
        Tuple of:
        - sa_info: Full parsed SA dict (for SDK or storage)
        - display_info: Safe-to-log dict with masked private_key_id
        - credentials: google.oauth2.service_account.Credentials object
        
    Raises:
        ValueError: If input is invalid, file not found, or missing required fields
        
    Example:
        >>> sa_info, display_info, creds = parse_gcp_service_account('{"type": "service_account", ...}')
        >>> print(display_info['project_id'])
        'my-project'
        >>> print(display_info['private_key_id'])
        'abc12345...'
    """
    if not credentials_input or not credentials_input.strip():
        raise ValueError("No GCP credentials provided")
    
    credentials_input_stripped = credentials_input.strip()
    
    # Detect if input is JSON content (starts with '{') or a file path
    if credentials_input_stripped.startswith('{'):
        # Input is raw JSON content
        try:
            sa_info = json.loads(credentials_input_stripped)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in credentials: {e}")
    else:
        # Input is a file path
        path = Path(credentials_input_stripped)
        
        if not path.exists():
            raise ValueError(f"Service account file not found: {credentials_input_stripped}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                sa_info = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in service account file: {e}")
    
    # Validate required fields
    required_fields = ["type", "project_id", "client_email"]
    missing = [f for f in required_fields if f not in sa_info]
    
    if missing:
        raise ValueError(f"Service account JSON missing required fields: {missing}")
    
    if sa_info.get("type") != "service_account":
        raise ValueError(f"Invalid credential type: {sa_info.get('type')}. Expected 'service_account'.")
    
    # Create safe-to-log display info with masked private key ID
    private_key_id = sa_info.get("private_key_id", "")
    display_info = {
        "project_id": sa_info["project_id"],
        "client_email": sa_info["client_email"],
        "private_key_id": (private_key_id[:8] + "...") if len(private_key_id) > 8 else private_key_id,
    }
    
    # Create credentials object for SDK usage
    try:
        credentials = service_account.Credentials.from_service_account_info(sa_info)
    except Exception as e:
        raise ValueError(f"Failed to create credentials from service account: {e}")
    
    return sa_info, display_info, credentials
