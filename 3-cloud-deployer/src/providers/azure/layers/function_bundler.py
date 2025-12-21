"""
Azure Function Bundler - Compatibility layer.

This module re-exports bundling functions from the new azure_bundler.py
to maintain compatibility with existing code.

For new code, import directly from:
    from src.providers.azure.azure_bundler import bundle_l1_functions
"""
from src.providers.azure.azure_bundler import (
    bundle_l0_functions,
    bundle_l1_functions,
    bundle_l2_functions,
    bundle_l3_functions,
    bundle_l4_functions,
    bundle_user_functions,
    BundleError,
    _clean_function_app_imports,
    _convert_functionapp_to_blueprint,
    _convert_require_env_to_lazy,
    _merge_function_files,
)

__all__ = [
    "bundle_l0_functions",
    "bundle_l1_functions",
    "bundle_l2_functions",
    "bundle_l3_functions",
    "bundle_l4_functions",
    "bundle_user_functions",
    "BundleError",
    "_clean_function_app_imports",
    "_convert_functionapp_to_blueprint",
    "_convert_require_env_to_lazy",
    "_merge_function_files",
]
