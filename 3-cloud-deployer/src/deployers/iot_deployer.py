"""
IoT Deployer - Device-specific Infrastructure Deployment.

This module provides backward-compatible entry points that delegate to
the new providers-based deployment system (src/providers/iot_deployer.py).

DEPRECATION NOTICE:
    This module is deprecated. Use src/providers/iot_deployer.py directly with
    a properly constructed DeploymentContext for new code.
"""

import warnings

# Issue deprecation warning on import
warnings.warn(
    "deployers.iot_deployer is deprecated. Use src/providers/iot_deployer.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import the new deployer that uses providers pattern
import providers.iot_deployer as new_iot_deployer
import providers.deployer as core_deployer


def _get_context():
    """Get a deployment context from globals for backward compatibility."""
    return core_deployer._create_legacy_context()


# ==========================================
# Layer 1 - IoT Devices
# ==========================================

def deploy_l1(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_iot_deployer.deploy_l1(context, provider)


def destroy_l1(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_iot_deployer.destroy_l1(context, provider)


# ==========================================
# Layer 2 - Device Processors
# ==========================================

def deploy_l2(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_iot_deployer.deploy_l2(context, provider)


def destroy_l2(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_iot_deployer.destroy_l2(context, provider)


# ==========================================
# Layer 4 - TwinMaker Component Types
# ==========================================

def deploy_l4(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_iot_deployer.deploy_l4(context, provider)


def destroy_l4(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_iot_deployer.destroy_l4(context, provider)


# ==========================================
# Full Deployment
# ==========================================

def deploy(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_iot_deployer.deploy(context, provider)


def destroy(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_iot_deployer.destroy(context, provider)
