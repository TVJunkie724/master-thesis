"""Cleanup old evt-test-* resource groups."""
import os
import sys
sys.path.insert(0, '/app/src')

from pathlib import Path
import json

# Load Azure credentials
creds_path = Path('/app/upload/template/config_credentials.json')
with open(creds_path) as f:
    all_creds = json.load(f)

azure = all_creds.get("azure", {})

from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient

credential = ClientSecretCredential(
    tenant_id=azure.get("azure_tenant_id"),
    client_id=azure.get("azure_client_id"),
    client_secret=azure.get("azure_client_secret")
)

resource_client = ResourceManagementClient(credential, azure.get("azure_subscription_id"))

print("="*60)
print("  CLEANUP OLD EVT-TEST RESOURCE GROUPS")
print("="*60)

# Find and delete evt-test-* resource groups
rgs_to_delete = []
for rg in resource_client.resource_groups.list():
    if rg.name.startswith("evt-test-"):
        rgs_to_delete.append(rg.name)
        print(f"  Found: {rg.name}")

if not rgs_to_delete:
    print("  No evt-test-* resource groups found.")
else:
    print(f"\n  Deleting {len(rgs_to_delete)} resource groups...")
    for rg_name in rgs_to_delete:
        try:
            poller = resource_client.resource_groups.begin_delete(rg_name)
            print(f"    Deleting {rg_name}... (async)")
        except Exception as e:
            print(f"    Failed to delete {rg_name}: {e}")

print("\n  Done! Resource groups are being deleted asynchronously.")
print("="*60)
