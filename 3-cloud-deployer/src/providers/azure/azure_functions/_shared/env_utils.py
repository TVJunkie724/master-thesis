"""
Environment Variable Utilities.

Provides fail-fast environment variable validation for serverless functions.
This module is used by all Azure Functions that require environment variables.

Source: src/providers/azure/azure_functions/_shared/env_utils.py
Editable: Yes - This is shared runtime code packaged with Azure Functions
"""
import os


def require_env(name: str) -> str:
    """
    Get required environment variable or raise error at module load time.
    
    This provides fail-fast behavior for missing configuration.
    Call at module level to ensure the function fails immediately
    during cold start if required configuration is missing.
    
    Args:
        name: The environment variable name
        
    Returns:
        The stripped environment variable value
        
    Raises:
        EnvironmentError: If the variable is missing or empty
        
    Example:
        from _shared.env_utils import require_env
        
        DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(
            f"CRITICAL: Required environment variable '{name}' is missing or empty"
        )
    return value
