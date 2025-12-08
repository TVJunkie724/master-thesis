"""
Core Deployer - Multi-Cloud Deployment Orchestration.

This module provides backward-compatible entry points that delegate to
the new providers-based deployment system (src/providers/deployer.py).

DEPRECATION NOTICE:
    This module is deprecated. Use src/providers/deployer.py directly with
    a properly constructed DeploymentContext for new code.
"""

import warnings
from typing import Literal

# Issue deprecation warning on import
warnings.warn(
    "deployers.core_deployer is deprecated. Use src/providers/deployer.py instead.",
    DeprecationWarning,
    stacklevel=2
)

from logger import logger

# Import the new deployer that uses providers pattern
import providers.deployer as new_deployer

Provider = Literal["aws", "azure", "google"]


def _get_context():
    """Get a deployment context from globals for backward compatibility."""
    return new_deployer._create_legacy_context()


# ==========================================
# Layer 1 - Data Acquisition
# ==========================================

def deploy_l1(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.deploy_l1(context, provider)


def destroy_l1(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.destroy_l1(context, provider)


# ==========================================
# Layer 2 - Data Processing  
# ==========================================

def deploy_l2(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.deploy_l2(context, provider)


def destroy_l2(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.destroy_l2(context, provider)


def redeploy_l2_event_checker(provider: str | None = None) -> None:
    """Redeploy just the event checker Lambda function."""
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    # This is a specialized operation - call AWS-specific code for now
    if provider == "aws":
        import aws.core_deployer_aws as core_aws
        core_aws.redeploy_event_checker_lambda_function()
    else:
        raise NotImplementedError(f"{provider} redeployment not implemented yet.")


# ==========================================
# Layer 3 - Data Storage
# ==========================================

def deploy_l3_hot(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.deploy_l3_hot(context, provider)


def destroy_l3_hot(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.destroy_l3_hot(context, provider)


def deploy_l3_cold(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.deploy_l3_cold(context, provider)


def destroy_l3_cold(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.destroy_l3_cold(context, provider)


def deploy_l3_archive(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.deploy_l3_archive(context, provider)


def destroy_l3_archive(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.destroy_l3_archive(context, provider)


def deploy_l3(provider: str | None = None) -> None:
    """Deploy all L3 services (hot, cold, archive)."""
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.deploy_l3(context, provider)


def destroy_l3(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.destroy_l3(context, provider)


# ==========================================
# Layer 4 - Digital Twin
# ==========================================

def deploy_l4(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.deploy_l4(context, provider)


def destroy_l4(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.destroy_l4(context, provider)


# ==========================================
# Layer 5 - Visualization
# ==========================================

def deploy_l5(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.deploy_l5(context, provider)


def destroy_l5(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.destroy_l5(context, provider)


# ==========================================
# Full Deployment
# ==========================================

def deploy(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.deploy_all(context, provider)


def destroy(provider: str | None = None) -> None:
    if provider is None:
        raise ValueError("Provider must be specified for deployment.")
    context = _get_context()
    new_deployer.destroy_all(context, provider)