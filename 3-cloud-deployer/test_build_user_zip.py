#!/usr/bin/env python3
"""
Test script to build COMBINED Azure user functions ZIP bundle.

Usage:
    python test_build_user_zip.py [project_path]

This uses build_azure_user_bundle() from package_builder.py
to create the combined user_functions.zip for Azure deployment.
"""
import sys
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from providers.terraform.package_builder import build_azure_user_bundle, build_all_packages
from core.config_loader import load_optimization_flags


def main():
    """Build Azure user functions ZIP and show results."""
    # Default to template project
    if len(sys.argv) > 1:
        project_path = Path(sys.argv[1])
    else:
        project_path = Path(__file__).parent / "upload" / "template"
    
    print(f"[BUILD] Project path: {project_path}")
    
    if not project_path.exists():
        print(f"[ERROR] Project path not found: {project_path}")
        sys.exit(1)
    
    # Load providers config
    providers_path = project_path / "config_providers.json"
    if not providers_path.exists():
        print(f"[ERROR] config_providers.json not found")
        sys.exit(1)
    
    with open(providers_path) as f:
        providers_config = json.load(f)
    
    print(f"[BUILD] L2 Provider: {providers_config.get('layer_2_provider')}")
    
    # Load optimization flags
    optimization_flags = load_optimization_flags(project_path)
    print(f"[BUILD] Optimization flags: {optimization_flags}")
    
    # Build combined Azure user bundle
    print("\n[BUILD] Building Azure user bundle (combined ZIP)...")
    try:
        user_zip_path = build_azure_user_bundle(project_path, providers_config, optimization_flags)
        
        if user_zip_path and user_zip_path.exists():
            print(f"\n[BUILD] ✓ Azure user_functions.zip created!")
            print(f"  Path: {user_zip_path}")
            print(f"  Size: {user_zip_path.stat().st_size} bytes")
            
            # List contents
            import zipfile
            with zipfile.ZipFile(user_zip_path, 'r') as zf:
                print(f"\n[BUILD] ZIP Contents:")
                for name in sorted(zf.namelist())[:30]:
                    info = zf.getinfo(name)
                    print(f"  - {name} ({info.file_size} bytes)")
                if len(zf.namelist()) > 30:
                    print(f"  ... and {len(zf.namelist()) - 30} more files")
        else:
            print(f"\n[BUILD] ⚠ No user_functions.zip created")
            print(f"  Returned: {user_zip_path}")
            
            # Check azure_functions directory
            azure_funcs = project_path / "azure_functions"
            if azure_funcs.exists():
                print(f"\n[BUILD] azure_functions directory contents:")
                for item in azure_funcs.iterdir():
                    print(f"  - {item.name}/ ({sum(1 for _ in item.rglob('*') if _.is_file())} files)" if item.is_dir() else f"  - {item.name}")
            else:
                print(f"\n[BUILD] ⚠ No azure_functions directory at: {azure_funcs}")
                
    except Exception as e:
        print(f"[ERROR] build_azure_user_bundle failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n[BUILD] Done!")


if __name__ == "__main__":
    main()
