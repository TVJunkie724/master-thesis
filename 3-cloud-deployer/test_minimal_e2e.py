#!/usr/bin/env python
"""Minimal test to isolate GCP E2E fixture failure."""
import sys
import os
from pathlib import Path

sys.path.insert(0, "/app/src")

# Simulate what the E2E test does
print("=" * 60)
print("  MINIMAL GCP E2E TEST")
print("=" * 60)

# Step 1: Create temp project (like fixture does)
import tempfile
import shutil
import json

template_path = Path("/app/upload/template")
temp_dir = Path(tempfile.mkdtemp(prefix="gcp_test_"))
project_path = temp_dir / "tf-e2e-gcp"

print(f"\n[1] Copying template to: {project_path}")
shutil.copytree(template_path, project_path)

# Modify config
config_path = project_path / "config.json"
with open(config_path, "r") as f:
    config = json.load(f)
config["digital_twin_name"] = "tf-e2e-gcp"
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

# Set all providers to GCP
providers_path = project_path / "config_providers.json"
providers = {
    "layer_1_provider": "google",
    "layer_2_provider": "google",
    "layer_3_hot_provider": "google",
    "layer_3_cold_provider": "google",
    "layer_3_archive_provider": "google",
    "layer_4_provider": "google",
    "layer_5_provider": "google"
}
with open(providers_path, "w") as f:
    json.dump(providers, f, indent=2)

print("  ✓ Test project created")

# Step 2: Initialize Terraform strategy
print("\n[2] Initializing Terraform strategy...")
from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy

terraform_dir = "/app/src/terraform"
strategy = TerraformDeployerStrategy(
    terraform_dir=terraform_dir,
    project_path=str(project_path)
)
print("  ✓ Strategy initialized")

# Step 3: Try to build packages
print("\n[3] Building packages...")
try:
    strategy._build_packages()
    print("  ✓ Packages built successfully")
    
    # Check what was built
    build_dir = project_path / ".build" / "gcp"
    if build_dir.exists():
        zips = list(build_dir.glob("*.zip"))
        print(f"  Built {len(zips)} ZIPs:")
        for z in sorted(zips):
            print(f"    - {z.name}")
    else:
        print("  ⚠ .build/gcp directory not created!")
        
except Exception as e:
    print(f"  ✗ Build failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Generate tfvars
print("\n[4] Generating tfvars...")
try:
    strategy._generate_tfvars()
    print("  ✓ tfvars generated")
    
    # Check tfvars content
    tfvars_path = project_path / "tfvars.json"
    if tfvars_path.exists():
        with open(tfvars_path) as f:
            tfvars = json.load(f)
        print(f"  gcp_processors: {tfvars.get('gcp_processors', [])}")
    else:
        print("  ⚠ tfvars.json not created!")
        
except Exception as e:
    print(f"  ✗ tfvars generation failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("  SUCCESS - All steps passed")
print("=" * 60)
