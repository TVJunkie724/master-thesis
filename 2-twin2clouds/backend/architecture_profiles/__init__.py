"""Dark architecture-profile resolution contracts for the Optimizer."""

from .capability_resolver import CapabilityReport, resolve_provider_capabilities
from .registry import ArchitectureProfileRegistry
from .strategy import (
    ArchitectureOptimizationStrategy,
    ArchitectureProfileRef,
    ArchitectureResolutionContext,
    ArchitectureStrategyRegistry,
    ExtensionBindingRef,
    OptimizationBundleRef,
    build_resolution_context,
)

__all__ = [
    "ArchitectureOptimizationStrategy",
    "ArchitectureProfileRegistry",
    "ArchitectureProfileRef",
    "ArchitectureResolutionContext",
    "ArchitectureStrategyRegistry",
    "CapabilityReport",
    "ExtensionBindingRef",
    "OptimizationBundleRef",
    "build_resolution_context",
    "resolve_provider_capabilities",
]
