"""
Function Registry - Single source of truth for all static serverless functions.

This module defines all static functions (L0-L4) with their metadata, replacing
the hardcoded function lists that were previously scattered across multiple files.

Usage:
    from src.function_registry import STATIC_FUNCTIONS, get_by_layer, get_l0_for_config
    
    # Get all L2 functions
    l2_funcs = get_by_layer(Layer.L2_PROCESSING)
    
    # Get L0 glue functions needed for a specific provider config
    glue_funcs = get_l0_for_config(providers_config, "azure")
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict
from pathlib import Path


class Layer(Enum):
    """Layer numbers in the 5-layer architecture."""
    L0_GLUE = 0
    L1_ACQUISITION = 1
    L2_PROCESSING = 2
    L3_STORAGE = 3
    L4_MANAGEMENT = 4
    L5_VISUALIZATION = 5


@dataclass
class FunctionDefinition:
    """
    Metadata for a static serverless function.
    
    Attributes:
        name: Unique identifier for the function (used in registry queries)
        layer: Which layer this function belongs to
        providers: List of cloud providers that support this function
        dir_name: Directory name if different from name (for filesystem lookup)
        is_optional: Whether this function is optional (won't error if missing)
        boundary: For L0 glue functions, the layer boundary that triggers deployment
        terraform_output_suffix: Suffix for Terraform output keys
    """
    name: str
    layer: Layer
    providers: List[str] = field(default_factory=lambda: ["aws", "azure", "gcp"])
    dir_name: Optional[str] = None
    is_optional: bool = False
    boundary: Optional[Tuple[str, str]] = None  # (source_layer_key, target_layer_key)
    terraform_output_suffix: str = "_function_name"
    
    @property
    def safe_name(self) -> str:
        """Python-safe name (hyphens converted to underscores)."""
        return self.name.replace("-", "_")
    
    @property
    def layer_provider_key(self) -> Optional[str]:
        """Get the provider config key for this function's layer."""
        return get_layer_provider_key(self.layer)
    
    def get_dir_name(self) -> str:
        """Get the directory name for filesystem lookup."""
        return self.dir_name or self.name


# Provider-specific path conventions
PROVIDER_PATHS = {
    "azure": {
        "base": "azure_functions",
        "handler": "function_app.py",
        "core_location": "src/providers/azure/azure_functions",
    },
    "aws": {
        "base": "lambda_functions",
        "handler": "lambda_function.py",
        "core_location": "src/providers/aws/lambda_functions",
    },
    "gcp": {
        "base": "cloud_functions",
        "handler": "main.py",
        "core_location": "src/providers/gcp/cloud_functions",
    },
}


# ============================================================================
# ALL STATIC FUNCTIONS DEFINED HERE
# ============================================================================

STATIC_FUNCTIONS: List[FunctionDefinition] = [
    # L0: Cross-cloud glue functions (only deployed when boundaries cross clouds)
    # Note: These use unique names to avoid conflicts with L3 storage functions
    FunctionDefinition(
        name="ingestion",
        layer=Layer.L0_GLUE,
        boundary=("layer_1_provider", "layer_2_provider"),
    ),
    FunctionDefinition(
        name="hot-writer",
        layer=Layer.L0_GLUE,
        boundary=("layer_2_provider", "layer_3_hot_provider"),
    ),
    FunctionDefinition(
        name="cold-writer",
        layer=Layer.L0_GLUE,
        boundary=("layer_2_provider", "layer_3_cold_provider"),
        is_optional=True,
    ),
    FunctionDefinition(
        name="archive-writer",
        layer=Layer.L0_GLUE,
        boundary=("layer_3_cold_provider", "layer_3_archive_provider"),
        is_optional=True,
    ),
    FunctionDefinition(
        name="adt-pusher",
        layer=Layer.L0_GLUE,
        providers=["azure"],
        boundary=("layer_3_hot_provider", "layer_4_provider"),
    ),
    FunctionDefinition(
        name="l0-hot-reader",
        layer=Layer.L0_GLUE,
        dir_name="hot-reader",
        boundary=("layer_3_hot_provider", "layer_5_provider"),
    ),
    FunctionDefinition(
        name="l0-hot-reader-last-entry",
        layer=Layer.L0_GLUE,
        dir_name="hot-reader-last-entry",
        boundary=("layer_3_hot_provider", "layer_5_provider"),
    ),
    
    # L1: Data Acquisition
    FunctionDefinition(
        name="dispatcher",
        layer=Layer.L1_ACQUISITION,
    ),
    FunctionDefinition(
        name="connector",
        layer=Layer.L1_ACQUISITION,
    ),
    
    # L2: Processing
    FunctionDefinition(
        name="persister",
        layer=Layer.L2_PROCESSING,
    ),
    FunctionDefinition(
        name="event-checker",
        layer=Layer.L2_PROCESSING,
        is_optional=True,
    ),
    FunctionDefinition(
        name="event-feedback",
        layer=Layer.L2_PROCESSING,
        is_optional=True,
        # NOTE: This user function is bundled WITH event_feedback_wrapper from /src.
        # The wrapper handles SDK boilerplate, user provides process.py.
        # Wrapper location: src/providers/{provider}/*/event_feedback_wrapper/
    ),
    FunctionDefinition(
        name="processor_wrapper",
        layer=Layer.L2_PROCESSING,
        dir_name="processor_wrapper",
        # NOTE: Static wrapper that routes to device-specific user processors.
        # Dispatcher → processor_wrapper → {twin}-{device_id}-processor
    ),
    
    # L3: Storage
    FunctionDefinition(
        name="hot-reader",
        layer=Layer.L3_STORAGE,
    ),
    FunctionDefinition(
        name="hot-reader-last-entry",
        layer=Layer.L3_STORAGE,
    ),
    FunctionDefinition(
        name="hot-to-cold-mover",
        layer=Layer.L3_STORAGE,
    ),
    FunctionDefinition(
        name="cold-to-archive-mover",
        layer=Layer.L3_STORAGE,
    ),
    
    # L4: Management
    FunctionDefinition(
        name="adt-updater",
        layer=Layer.L4_MANAGEMENT,
        providers=["azure"],
    ),
    FunctionDefinition(
        name="digital-twin-data-connector",
        layer=Layer.L4_MANAGEMENT,
        providers=["aws"],
    ),
    FunctionDefinition(
        name="digital-twin-data-connector-last-entry",
        layer=Layer.L4_MANAGEMENT,
        providers=["aws"],
    ),
]


# ============================================================================
# QUERY FUNCTIONS
# ============================================================================

def get_by_layer(layer: Layer) -> List[FunctionDefinition]:
    """Get all functions for a specific layer."""
    return [f for f in STATIC_FUNCTIONS if f.layer == layer]


def get_by_provider(provider: str) -> List[FunctionDefinition]:
    """Get all functions that support a specific provider."""
    return [f for f in STATIC_FUNCTIONS if provider in f.providers]


def get_function_by_name(name: str) -> Optional[FunctionDefinition]:
    """Get a function by name or dir_name."""
    for func in STATIC_FUNCTIONS:
        if func.name == name or func.get_dir_name() == name:
            return func
    return None


def get_layer_provider_key(layer: Layer) -> Optional[str]:
    """Map layer to provider config key."""
    mapping = {
        Layer.L0_GLUE: None,  # Determined by boundary
        Layer.L1_ACQUISITION: "layer_1_provider",
        Layer.L2_PROCESSING: "layer_2_provider",
        Layer.L3_STORAGE: "layer_3_hot_provider",
        Layer.L4_MANAGEMENT: "layer_4_provider",
        Layer.L5_VISUALIZATION: "layer_5_provider",
    }
    return mapping.get(layer)


def get_functions_for_provider_build(
    provider: str, 
    providers_config: dict,
    optimization_flags: dict = None
) -> List[str]:
    """
    Get function directory names to build for a provider.
    
    This replaces hardcoded lists in package_builder.py.
    Handles L0 boundary logic and layer-based selection.
    
    Args:
        provider: "aws", "azure", or "gcp" (use "google" internally)
        providers_config: Dict with layer_X_provider keys
        optimization_flags: Dict with feature flags like useEventChecking, returnFeedbackToDevice
    
    Returns:
        List of function directory names to build
    """
    # Terraform/Config uses "google", Registry uses "gcp"
    config_target = "google" if provider == "gcp" else provider
    registry_target = provider
    optimization_flags = optimization_flags or {}
    
    functions = []
    
    # L0 glue functions (boundary-based)
    functions.extend(get_l0_for_config(providers_config, config_target))
    
    # L1 functions
    if providers_config.get("layer_1_provider") == config_target:
        for f in get_by_layer(Layer.L1_ACQUISITION):
            if registry_target in f.providers:
                functions.append(f.get_dir_name())
    
    # L2 functions
    if providers_config.get("layer_2_provider") == config_target:
        for f in get_by_layer(Layer.L2_PROCESSING):
            if registry_target in f.providers:
                if f.is_optional:
                    # Include optional functions based on feature flags
                    if f.name == "event-checker" and optimization_flags.get("useEventChecking"):
                        functions.append(f.get_dir_name())
                    elif f.name == "event-feedback" and optimization_flags.get("returnFeedbackToDevice"):
                        functions.append(f.get_dir_name())
                else:
                    functions.append(f.get_dir_name())
    
    # L3 functions
    if providers_config.get("layer_3_hot_provider") == config_target:
        for f in get_by_layer(Layer.L3_STORAGE):
            if registry_target in f.providers:
                functions.append(f.get_dir_name())
    
    # L4 functions
    if providers_config.get("layer_4_provider") == config_target:
        for f in get_by_layer(Layer.L4_MANAGEMENT):
            if registry_target in f.providers:
                functions.append(f.get_dir_name())
    
    return list(set(functions))  # Deduplicate



def get_l0_for_config(providers_config: dict, target_provider: str) -> List[str]:
    """
    Get L0 glue function names needed for a specific provider configuration.
    
    L0 glue functions are only deployed when a boundary crosses clouds.
    For example, if L1 is AWS and L2 is Azure, the ingestion function
    is deployed on Azure to receive data from AWS.
    
    Args:
        providers_config: Dict with keys like "layer_1_provider", "layer_2_provider", etc.
        target_provider: The provider to get functions for (e.g., "azure")
    
    Returns:
        List of function directory names to include in the bundle
    """

    functions = []
    
    # Map config provider name ("google") to registry provider name ("gcp")
    registry_provider = "gcp" if target_provider == "google" else target_provider
    
    for func in get_by_layer(Layer.L0_GLUE):
        if func.boundary and registry_provider in func.providers:
            source_key, target_key = func.boundary
            source_provider = providers_config.get(source_key)
            target_provider_val = providers_config.get(target_key)
            
            # Only include if boundary crosses clouds and target matches
            if source_provider != target_provider_val and target_provider_val == target_provider:
                dir_name = func.get_dir_name()
                if dir_name not in functions:
                    functions.append(dir_name)
    
    return functions


def get_terraform_output_map(provider: str, layer: Optional[Layer] = None) -> Dict[str, str]:
    """
    Generate Terraform output key -> function directory name map.
    
    Args:
        provider: Cloud provider ("aws", "azure", "gcp")
        layer: Optional layer filter
    
    Returns:
        Dict mapping Terraform output keys to function directory names
    """
    result = {}
    funcs = get_by_provider(provider)
    if layer:
        funcs = [f for f in funcs if f.layer == layer]
    
    for func in funcs:
        # Format: {provider}_l{layer}_{safe_name}{suffix}
        # Example: aws_l1_dispatcher_function_name
        key = f"{provider}_l{func.layer.value}_{func.safe_name}{func.terraform_output_suffix}"
        result[key] = func.get_dir_name()
    
    return result


def get_function_path(func: FunctionDefinition, provider: str, is_core: bool = True) -> Path:
    """
    Get filesystem path to a function directory.
    
    Args:
        func: Function definition
        provider: Cloud provider
        is_core: If True, use core location; if False, use project location
    
    Returns:
        Path to the function directory
    """
    config = PROVIDER_PATHS[provider]
    base = config["core_location"] if is_core else config["base"]
    dir_name = func.get_dir_name()
    return Path(base) / dir_name


def get_wrapper_path(func_name: str, provider: str) -> Optional[Path]:
    """
    Get path to the static wrapper for a user function.
    
    User functions like 'event-feedback' and processors need static wrappers
    that handle SDK boilerplate. This returns the wrapper directory path.
    
    Args:
        func_name: User function name (e.g., 'event-feedback', 'processor')
        provider: Cloud provider ('aws', 'azure', 'gcp')
    
    Returns:
        Path to wrapper directory, or None if no wrapper exists
    """
    # Map user function names to wrapper directory names
    wrapper_map = {
        'event-feedback': 'event_feedback_wrapper',
        'processor': 'processor_wrapper',
    }
    
    wrapper_name = wrapper_map.get(func_name)
    if not wrapper_name:
        return None
    
    config = PROVIDER_PATHS.get(provider)
    if not config:
        return None
    
    return Path(config['core_location']) / wrapper_name
