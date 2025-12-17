#!/usr/bin/env python3
"""Quick test to list functions in the deployed function app."""
import sys
import json
from pathlib import Path

# Load credentials
creds_path = Path("/app/upload/template/config_credentials.json")
with open(creds_path) as f:
    creds = json.load(f)

print(f"Subscription: {creds['azure_subscription_id'][:8]}...")
print(f"Tenant: {creds['azure_tenant_id'][:8]}...")

from azure.identity import ClientSecretCredential
from azure.mgmt.web import WebSiteManagementClient

credential = ClientSecretCredential(
    tenant_id=creds["azure_tenant_id"],
    client_id=creds["azure_client_id"],
    client_secret=creds["azure_client_secret"]
)

web_client = WebSiteManagementClient(credential, creds["azure_subscription_id"])

# List all function apps in subscription
print("\n=== All Function Apps ===")
for app in web_client.web_apps.list():
    if "function" in app.name.lower() or "func" in app.name.lower():
        print(f"\nApp: {app.name}")
        print(f"  Resource Group: {app.resource_group}")
        print(f"  Location: {app.location}")
        
        try:
            functions = list(web_client.web_apps.list_functions(app.resource_group, app.name))
            print(f"  Functions ({len(functions)}):")
            for func in functions:
                func_name = func.name.split('/')[-1] if '/' in func.name else func.name
                print(f"    - {func_name}")
        except Exception as e:
            print(f"  Error listing functions: {e}")
