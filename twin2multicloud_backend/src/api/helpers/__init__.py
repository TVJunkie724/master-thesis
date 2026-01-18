# src/api/helpers/__init__.py
"""
Helper modules for Management API routes.

Provides extracted, reusable logic for:
- Credential validation (dual-service)
- Configuration building and masking
"""

from .credential_validator import (
    validate_with_optimizer,
    validate_with_deployer,
    perform_dual_validation,
    build_optimizer_credentials,
    build_deployer_credentials,
    get_required_fields,
)

from .config_builder import (
    mask_credentials,
    build_config_response,
    build_update_payload,
    check_provider_configured,
    get_configured_providers,
)

__all__ = [
    # Credential validation
    "validate_with_optimizer",
    "validate_with_deployer",
    "perform_dual_validation",
    "build_optimizer_credentials",
    "build_deployer_credentials",
    "get_required_fields",
    # Config building
    "mask_credentials",
    "build_config_response",
    "build_update_payload",
    "check_provider_configured",
    "get_configured_providers",
]
