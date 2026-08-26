"""Dark architecture-profile resolution contracts for the Optimizer."""

from .capability_resolver import CapabilityReport, resolve_provider_capabilities
from .five_layer_strategy import FiveLayerCompletePathStrategy
from .registry import ArchitectureProfileRegistry
from .six_layer_strategy import (
    SixLayerEventingV1CandidateStrategy,
    validate_six_layer_strategy_readiness,
)
from .strategy import (
    ArchitectureOptimizationStrategy,
    ArchitectureProfileRef,
    ArchitectureResolutionContext,
    ExtensionBindingRef,
    OptimizationBundleRef,
    build_resolution_context,
)

__all__ = [
    "ArchitectureOptimizationStrategy",
    "ArchitectureProfileRef",
    "ArchitectureProfileRegistry",
    "ArchitectureResolutionContext",
    "CapabilityReport",
    "ExtensionBindingRef",
    "FiveLayerCompletePathStrategy",
    "OptimizationBundleRef",
    "SixLayerEventingV1CandidateStrategy",
    "build_resolution_context",
    "resolve_provider_capabilities",
    "validate_six_layer_strategy_readiness",
]
