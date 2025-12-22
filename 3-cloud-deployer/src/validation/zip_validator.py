"""
Zip Validator - Project archive validation.

This module is a thin adapter that delegates to src.validation.core.
All validation logic is centralized in core.py for reuse across ZIP and directory sources.
"""

import io
import os
import zipfile
from typing import Union

from src.validation.core import run_all_checks
from src.validation.accessors import ZipFileAccessor


def validate_project_zip(zip_source: Union[str, bytes, io.BytesIO]) -> None:
    """
    Validates a project zip file for upload.
    
    Performs comprehensive validation including file presence, security,
    schema validation, and cross-config consistency checks.
    
    Args:
        zip_source: Path to zip file, raw bytes, or BytesIO object
        
    Raises:
        ValueError: For any validation failure with descriptive message
    """
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)

    with zipfile.ZipFile(zip_source, 'r') as zf:
        # ZIP-specific security check (not applicable to directories)
        _check_zip_slip(zf)
        
        # Delegate to shared core
        accessor = ZipFileAccessor(zf)
        run_all_checks(accessor)


def _check_zip_slip(zf: zipfile.ZipFile) -> None:
    """
    Prevent Zip Slip attacks (path traversal).
    
    ZIP-only security check that rejects paths containing '..' or absolute paths.
    """
    for member in zf.infolist():
        if member.is_dir():
            continue
        if ".." in member.filename or os.path.isabs(member.filename):
            raise ValueError("Malicious file path detected in zip (Zip Slip Prevention).")
