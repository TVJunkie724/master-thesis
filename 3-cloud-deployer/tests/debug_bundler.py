"""Debug script to check bundled output."""
import sys
sys.path.insert(0, '/app')

from src.providers.azure.layers.function_bundler import bundle_l2_functions, _clean_function_app_imports
import zipfile
import io

# Test the cleaner directly
sample_content = '''"""Persister function."""
import json
import os
import sys
import logging

import azure.functions as func

# Handle import path for shared module
try:
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env


bp = func.Blueprint()


@bp.function_name(name="persister")
def persister(req):
    return "OK"
'''

print("=== ORIGINAL ===")
print(sample_content[:500])
print("\n=== CLEANED ===")
cleaned = _clean_function_app_imports(sample_content)
print(cleaned[:500])
print("\n=== CHECKING IMPORTS ===")
print(f"'require_env' in cleaned: {'require_env' in cleaned}")
print(f"'from _shared' in cleaned: {'from _shared' in cleaned}")
print(f"'sys.path.insert' in cleaned: {'sys.path.insert' in cleaned}")
