"""Debug script to test the GCP E2E fixture setup."""
import os
import sys
sys.path.insert(0, '/app/src')

from pathlib import Path
import shutil
import json

# Simulate what the fixture does
template_path = Path('/app/upload/template')
test_id = 'tf-e2e-gcp'

print(f"Template exists: {template_path.exists()}")
print(f"Template contents: {list(template_path.iterdir())}")

# Check config_providers.json
providers_file = template_path / 'config_providers.json'
print(f"\nconfig_providers.json exists: {providers_file.exists()}")
if providers_file.exists():
    with open(providers_file) as f:
        providers = json.load(f)
    print(f"Current providers: {providers}")

# Check config_credentials.json
creds_file = template_path / 'config_credentials.json'
print(f"\nconfig_credentials.json exists: {creds_file.exists()}")
if creds_file.exists():
    with open(creds_file) as f:
        creds = json.load(f)
    print(f"Has GCP section: {'gcp' in creds}")
    if 'gcp' in creds:
        gcp = creds['gcp']
        print(f"  gcp_region: {gcp.get('gcp_region', 'MISSING')}")
        print(f"  gcp_billing_account: {gcp.get('gcp_billing_account', 'MISSING')}")
        gcp_creds_file = gcp.get('gcp_credentials_file', 'MISSING')
        print(f"  gcp_credentials_file: {gcp_creds_file}")
        if gcp_creds_file and gcp_creds_file != 'MISSING':
            creds_path = Path(gcp_creds_file)
            print(f"    -> File exists: {creds_path.exists()}")
            # Try relative path from template
            alt_path = template_path / 'gcp_credentials.json'
            print(f"    -> Alt path {alt_path} exists: {alt_path.exists()}")

# Check gcp_credentials.json directly
gcp_creds_direct = template_path / 'gcp_credentials.json'
print(f"\ngcp_credentials.json (direct) exists: {gcp_creds_direct.exists()}")
if gcp_creds_direct.exists():
    with open(gcp_creds_direct) as f:
        gcp_creds_content = json.load(f)
    print(f"  Has project_id: {'project_id' in gcp_creds_content}")
    print(f"  Has private_key: {'private_key' in gcp_creds_content}")

# Test config loading with google L4/L5
print("\n[TEST] Testing config loading with google L4/L5...")
import tempfile
test_dir = Path(tempfile.mkdtemp())
print(f"  Created temp dir: {test_dir}")

# Copy template
import shutil
for item in template_path.iterdir():
    if item.is_file():
        shutil.copy2(item, test_dir / item.name)
    elif item.is_dir():
        shutil.copytree(item, test_dir / item.name)

# Modify config_providers.json for GCP L4/L5
providers = {
    "layer_1_provider": "google",
    "layer_2_provider": "google",
    "layer_3_hot_provider": "google",
    "layer_3_cold_provider": "google",
    "layer_3_archive_provider": "google",
    "layer_4_provider": "google",
    "layer_5_provider": "google"
}
with open(test_dir / "config_providers.json", "w") as f:
    json.dump(providers, f, indent=2)

print(f"  Modified providers: {providers}")

# Now try to load
try:
    from core.config_loader import load_project_config
    config = load_project_config(test_dir)
    print(f"  ✓ Config loaded successfully!")
    print(f"  digital_twin_name: {config.digital_twin_name}")
    print(f"  hierarchy: {config.hierarchy}")
except Exception as e:
    print(f"  ✗ Config loading failed: {e}")
    import traceback
    traceback.print_exc()

