#!/usr/bin/env python3
"""Helper script to rebuild the Azure user functions ZIP."""
import sys
sys.path.insert(0, '/app/src')
from pathlib import Path
from providers.terraform.package_builder import build_azure_user_bundle

project_path = Path("/app/e2e_persistence_temp/azure_terraform_e2e/azure_terraform_e2e0/tf-e2e-az")
providers_config = {"layer_2_provider": "azure"}

print("Rebuilding Azure user functions ZIP...")
result = build_azure_user_bundle(project_path, providers_config)
if result:
    print(f"SUCCESS: {result}")
else:
    print("FAILED: No ZIP created")
