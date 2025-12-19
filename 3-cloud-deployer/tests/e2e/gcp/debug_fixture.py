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
        print(f"  gcp_credentials_file: {gcp.get('gcp_credentials_file', 'MISSING')}")
