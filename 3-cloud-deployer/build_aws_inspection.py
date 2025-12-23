
import shutil
import os
from pathlib import Path
from src.providers.terraform.package_builder import (
    build_aws_lambda_packages,
    build_user_packages,
)

# Setup paths
repo_root = Path("/app")
source_path = repo_root / "upload/template"
output_dir = repo_root / "manual_inspection_aws_v2"
temp_project_path = repo_root / "temp_build_project"
terraform_dir = repo_root / "src/terraform" # We need real terraform dir for core functions?
# correct: build_aws_lambda_packages takes terraform_dir to find core functions in src/providers/...
# actually it builds TO terraform_dir/.build usually.
# Let's verify package_builder.py arguments.
# build_aws_lambda_packages(terraform_dir, project_path, providers_config)

# Clean previous runs
if output_dir.exists():
    shutil.rmtree(output_dir)
output_dir.mkdir(parents=True)

if temp_project_path.exists():
    shutil.rmtree(temp_project_path)
shutil.copytree(source_path, temp_project_path)

# AWS Config (all layers)
aws_config = {
    "layer_1_provider": "aws",
    "layer_2_provider": "aws",
    "layer_3_hot_provider": "aws",
    "layer_3_cold_provider": "aws",
    "layer_3_archive_provider": "aws",
    "layer_4_provider": "aws",
    "layer_5_provider": "aws",
}

print("Building AWS Core Packages...")
# We use a temp terraform dir to avoid messing up the real one if needed, 
# but package_builder uses it to find relative paths. 
# actually package_builder uses __file__ to find src/providers. 
# The 'terraform_dir' arg is used as output base for core functions?
# Let's check: build_dir = terraform_dir / ".build"
# So yes, we should use a temp directory for that too.
temp_terraform_dir = repo_root / "temp_terraform_build"
if temp_terraform_dir.exists():
    shutil.rmtree(temp_terraform_dir)
temp_terraform_dir.mkdir()

core_packages = build_aws_lambda_packages(temp_terraform_dir, temp_project_path, aws_config)

print("Building AWS User Packages...")
user_packages = build_user_packages(temp_project_path, aws_config)

print(f"\nCopying ZIPs to {output_dir}...")

# Copy Core Packages
for name, path in core_packages.items():
    print(f"  - {name} -> {path}")
    shutil.copy2(path, output_dir / f"CORE_{name}.zip")

# Copy User Packages
import zipfile
for name, path in user_packages.items():
    print(f"  - {name} -> {path}")
    shutil.copy2(path, output_dir / f"USER_{name}.zip")
    
    # Verify no zipped.zip in event-feedback
    if name == "event-feedback":
        with zipfile.ZipFile(path, 'r') as zf:
            files = zf.namelist()
            if "zipped.zip" in files:
                print("❌ FAILED: zipped.zip found in event-feedback.zip!")
                exit(1)
            else:
                print("✅ VERIFIED: zipped.zip excluded from event-feedback.zip")

# Cleanup temps
shutil.rmtree(temp_project_path)
shutil.rmtree(temp_terraform_dir)

print(f"\nDone! AWS ZIPs are available in: {output_dir}")
print(f"Total ZIPs: {len(core_packages) + len(user_packages)}")
