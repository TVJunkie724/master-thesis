"""
Sanity Checker - Pre-deployment Validation.

This module provides pre-deployment sanity checks to validate configuration
before deploying resources.

Migration Status:
    - Functions accept optional config parameter for new pattern.
    - Falls back to globals.config for backward compatibility.
"""

import re
from typing import Optional


def check_digital_twin_name(config: Optional[dict] = None) -> None:
    """Validate the digital twin name meets requirements.
    
    Args:
        config: Optional configuration dict. If None, uses globals.config
        
    Raises:
        ValueError: If name is too long or contains invalid characters
    """
    if config is None:
        import globals
        config = globals.config
    
    dt_name = config.get("digital_twin_name", "")
    max_length = 10
    dt_name_len = len(dt_name)

    if dt_name_len > max_length:
        raise ValueError(f"Digital Twin Name too long: {dt_name_len} > {max_length}")

    valid_pattern = r"[A-Za-z0-9_-]+"
    if not bool(re.fullmatch(valid_pattern, dt_name)):
        raise ValueError(f"Digital Twin Name does not satisfy this regex: {valid_pattern}")


def check(provider: Optional[str] = None, config: Optional[dict] = None) -> None:
    """Run all sanity checks.
    
    Args:
        provider: Optional provider name (currently unused)
        config: Optional configuration dict. If None, uses globals.config
    """
    check_digital_twin_name(config)
