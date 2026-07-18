# src/api/helpers/__init__.py
"""
Helper modules for Management API routes.

Provides extracted, reusable logic for:
- Credential validation (dual-service)
- Cloud Connection provider-state checks
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
    # Provider state
    "check_provider_configured",
    "get_configured_providers",
]
