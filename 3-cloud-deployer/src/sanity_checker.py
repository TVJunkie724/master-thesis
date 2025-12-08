"""
Sanity Checker - Pre-deployment Validation.

This module provides pre-deployment sanity checks to validate configuration
before deploying resources.

All functions now REQUIRE the config parameter. Legacy globals fallback removed.
"""

import re
from typing import Union
from core.context import ProjectConfig


def check_digital_twin_name(config: Union[dict, ProjectConfig]) -> None:
    """Validate the digital twin name meets requirements.
    
    Args:
        config: Configuration dict or ProjectConfig (REQUIRED)
        
    Raises:
        ValueError: If name is too long or contains invalid characters
    """
    if config is None:
        raise ValueError("config is required - globals fallback has been removed")
    
    # Handle both dict and ProjectConfig
    if hasattr(config, 'digital_twin_name'):
        dt_name = config.digital_twin_name
    else:
        dt_name = config.get("digital_twin_name", "")
    
    max_length = 10
    dt_name_len = len(dt_name)

    if dt_name_len > max_length:
        raise ValueError(f"Digital Twin Name too long: {dt_name_len} > {max_length}")

    valid_pattern = r"[A-Za-z0-9_-]+"
    if not bool(re.fullmatch(valid_pattern, dt_name)):
        raise ValueError(f"Digital Twin Name does not satisfy this regex: {valid_pattern}")


def check(provider: str = None, config: Union[dict, ProjectConfig] = None) -> None:
    """Run all sanity checks.
    
    Args:
        provider: Optional provider name (currently unused)
        config: Configuration dict or ProjectConfig (REQUIRED)
    """
    check_digital_twin_name(config)
