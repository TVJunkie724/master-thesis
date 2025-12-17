#!/usr/bin/env python3
"""Test if the merged function_app.py can be imported without errors."""
import zipfile
import io
import importlib.util
import sys
import tempfile
import os

# Add project root to path
sys.path.insert(0, '/app/src/providers/azure/layers')

from function_bundler import bundle_l2_functions

# Create L2 bundle
print("Creating L2 bundle...")
zip_bytes = bundle_l2_functions('/app')
zf = zipfile.ZipFile(io.BytesIO(zip_bytes))

# Extract to temp dir and try to import
with tempfile.TemporaryDirectory() as tmpdir:
    zf.extractall(tmpdir)
    
    # Add to path
    sys.path.insert(0, tmpdir)
    
    print("Testing if function_app.py can be imported...")
    print("(This will fail if there are any undefined names at module load time)")
    print()
    
    try:
        # Set required env vars to avoid fail-fast errors
        os.environ['DIGITAL_TWIN_INFO'] = '{"config_providers": {}, "config": {"digital_twin_name": "test"}}'
        
        spec = importlib.util.spec_from_file_location('function_app', f'{tmpdir}/function_app.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        print("SUCCESS: Module imported without errors!")
        print(f"  app = {module.app}")
        
        # Check what functions are registered
        if hasattr(module.app, '_functions'):
            print(f"  Registered functions: {list(module.app._functions.keys())}")
        
    except NameError as e:
        print(f"FAILURE: NameError - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"FAILURE: {type(e).__name__} - {e}")
        sys.exit(1)
