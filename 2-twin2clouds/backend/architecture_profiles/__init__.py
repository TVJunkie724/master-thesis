"""Dark-read architecture-profile contracts for the Optimizer."""

from .capability_resolver import CapabilityReport, resolve_provider_capabilities
from .registry import ArchitectureProfileRegistry

__all__ = [
    "ArchitectureProfileRegistry",
    "CapabilityReport",
    "resolve_provider_capabilities",
]
