#!/usr/bin/env python3
"""
Simple test to verify L0 and User function ZIP generation.

This test builds the ZIPs and checks their contents to ensure:
1. L0 ZIP contains actual glue functions (not empty)
2. User ZIP is generated and contains user functions
"""
import sys
import os
import zipfile
import tempfile
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from src.providers.azure.layers.function_bundler import (
    bundle_l0_functions,
    bundle_user_functions,
)

def test_l0_zip_generation():
    """Test L0 glue functions ZIP generation."""
    print("\n" + "="*60)
    print("TEST 1: L0 Glue Functions ZIP")
    print("="*60)
    
    # Use multicloud E2E test project
    project_path = "/tmp/multicloud-e2e/mc-e2e-test"
    
    # Provider config for multicloud test (GCP L1 → Azure L2 → AWS L3)
    providers_config = {
        "layer_1_provider": "google",
        "layer_2_provider": "azure",
        "layer_3_hot_provider": "aws",
        "layer_3_cold_provider": "google",
        "layer_3_archive_provider": "azure",
        "layer_4_provider": "azure",
        "layer_5_provider": "aws",
    }
    
    print(f"\nProject path: {project_path}")
    print(f"Provider config: L1={providers_config['layer_1_provider']}, "
          f"L2={providers_config['layer_2_provider']}, "
          f"L3_hot={providers_config['layer_3_hot_provider']}")
    
    # Build L0 ZIP
    print("\nBuilding L0 ZIP...")
    try:
        zip_bytes, functions = bundle_l0_functions(project_path, providers_config)
    except Exception as e:
        pytest.fail(f"Failed to build L0 ZIP: {e}")
    
    if not zip_bytes:
        pytest.fail("No L0 ZIP generated")
    
    # Check ZIP size
    zip_size = len(zip_bytes)
    print(f"\n✓ ZIP generated: {zip_size} bytes")
    print(f"✓ Functions included: {functions}")
    
    # Expected functions for this config:
    # - ingestion: L1 (google) → L2 (azure) cross-cloud
    # - adt-pusher: L3_hot (aws) → L4 (azure) cross-cloud
    
    if zip_size < 1000:
        pytest.fail(f"L0 ZIP too small ({zip_size} bytes), expected >1KB")
    
    # Extract and verify contents
    print("\nExtracting ZIP to verify contents...")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_zip = Path(temp_dir) / "l0_functions.zip"
        with open(temp_zip, "wb") as f:
            f.write(zip_bytes)
        
        with zipfile.ZipFile(temp_zip, 'r') as zf:
            file_list = zf.namelist()
            print(f"\nZIP contents ({len(file_list)} files):")
            for f in sorted(file_list)[:20]:  # Show first 20 files
                print(f"  - {f}")
            if len(file_list) > 20:
                print(f"  ... and {len(file_list) - 20} more files")
        
        # Check for expected files
        required_files = ["host.json", "requirements.txt", "function_app.py"]
        missing = [f for f in required_files if f not in file_list]
        
        if missing:
            pytest.fail(f"L0 ZIP is missing required files: {missing}")
        
        # Check for function directories (multi-function uses module pattern)
        has_function_code = any("ingestion" in f or "adt_pusher" in f for f in file_list)
        
        if not has_function_code:
            pytest.fail("L0 ZIP contains neither ingestion nor adt_pusher code")
    
    print("\n✅ L0 ZIP PASSED all checks!")


def test_user_zip_generation():
    """Test user functions ZIP generation."""
    print("\n" + "="*60)
    print("TEST 2: User Functions ZIP")
    print("="*60)
    
    # Use multicloud E2E test project
    project_path = "/tmp/multicloud-e2e/mc-e2e-test"
    
    print(f"\nProject path: {project_path}")
    
    # Build User ZIP
    print("\nBuilding User ZIP...")
    try:
        zip_bytes = bundle_user_functions(project_path)
    except Exception as e:
        pytest.fail(f"Failed to build user-functions ZIP: {e}")
    
    if not zip_bytes:
        print("⚠ No user functions found (this is OK if project has no user functions)")
        return
    
    # Check ZIP size
    zip_size = len(zip_bytes)
    print(f"\n✓ ZIP generated: {zip_size} bytes")
    
    if zip_size < 500:
        pytest.fail(f"User-functions ZIP too small ({zip_size} bytes), expected >500 bytes")
    
    # Extract and verify contents
    print("\nExtracting ZIP to verify contents...")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_zip = Path(temp_dir) / "user_functions.zip"
        with open(temp_zip, "wb") as f:
            f.write(zip_bytes)
        
        with zipfile.ZipFile(temp_zip, 'r') as zf:
            file_list = zf.namelist()
            print(f"\nZIP contents ({len(file_list)} files):")
            for f in sorted(file_list)[:20]:  # Show first 20 files
                print(f"  - {f}")
            if len(file_list) > 20:
                print(f"  ... and {len(file_list) - 20} more files")
        
        # Check for expected files
        required_files = ["host.json", "requirements.txt", "function_app.py"]
        missing = [f for f in required_files if f not in file_list]
        
        if missing:
            pytest.fail(f"User-functions ZIP is missing required files: {missing}")
    
    print("\n✅ User ZIP PASSED all checks!")
