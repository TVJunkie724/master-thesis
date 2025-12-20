#!/usr/bin/env python
"""Debug script to test GCP package building with detailed logging."""
import sys
import os
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(name)s - %(message)s'
)

print("=" * 60)
print("  GCP PACKAGE BUILD DEBUG")
print("=" * 60)

# Test building GCP packages
from src.providers.terraform.package_builder import build_all_packages

terraform_dir = "/app/src/terraform"
project_path = "/app/upload/template"
providers = {
    "layer_1_provider": "google",
    "layer_2_provider": "google",
    "layer_3_hot_provider": "google",
    "layer_3_cold_provider": "google",
    "layer_3_archive_provider": "google",
    "layer_4_provider": "google",
    "layer_5_provider": "google",
}

print(f"\nProject path: {project_path}")
print(f"Terraform dir: {terraform_dir}")
print(f"Providers: {providers}")

try:
    print("\n" + "=" * 60)
    print("  BUILDING PACKAGES")
    print("=" * 60)
    
    build_all_packages(terraform_dir, project_path, providers)
    
    print("\n" + "=" * 60)
    print("  BUILD SUCCESS")
    print("=" * 60)
    
    # Check what was built
    build_dir = Path(project_path) / ".build" / "gcp"
    if build_dir.exists():
        zips = list(build_dir.glob("*.zip"))
        print(f"\nBuilt {len(zips)} ZIP files:")
        for zip_file in sorted(zips):
            size = zip_file.stat().st_size
            print(f"  - {zip_file.name} ({size:,} bytes)")
    else:
        print(f"\nWARNING: .build/gcp directory not created!")
        
except Exception as e:
    print("\n" + "=" * 60)
    print("  BUILD FAILED")
    print("=" * 60)
    print(f"\nERROR: {type(e).__name__}: {e}")
    
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()
    
    sys.exit(1)
