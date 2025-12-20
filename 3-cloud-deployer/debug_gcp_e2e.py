#!/usr/bin/env python
"""Debug script to test GCP E2E fixture setup."""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# Test the tfvars generator with GCP
from tfvars_generator import _build_gcp_user_function_vars

project_path = Path("/app/upload/template")
providers = {"layer_2_provider": "google"}

print("Testing _build_gcp_user_function_vars...")
print(f"Project path: {project_path}")
print(f"Providers: {providers}")

try:
    result = _build_gcp_user_function_vars(project_path, providers)
    print(f"\nResult:")
    print(f"  gcp_processors: {result['gcp_processors']}")
    print(f"  gcp_event_actions: {result['gcp_event_actions']}")
    print(f"  gcp_event_feedback_enabled: {result['gcp_event_feedback_enabled']}")
    
    # Check if ZIPs exist
    build_dir = project_path / ".build" / "gcp"
    print(f"\nChecking .build/gcp directory: {build_dir}")
    if build_dir.exists():
        print(f"  Directory exists: {list(build_dir.glob('*.zip'))}")
    else:
        print(f"  Directory does NOT exist!")
        
except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
