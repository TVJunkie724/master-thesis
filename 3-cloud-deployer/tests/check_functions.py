#!/usr/bin/env python3
"""Check if functions are detected in the deployed function app."""
import json
import time

# Load credentials
with open("/app/upload/template/config_credentials.json") as f:
    all_creds = json.load(f)
    creds = all_creds["azure"]

from azure.identity import ClientSecretCredential
from azure.mgmt.web import WebSiteManagementClient

credential = ClientSecretCredential(
    tenant_id=creds["azure_tenant_id"],
    client_id=creds["azure_client_id"],
    client_secret=creds["azure_client_secret"]
)

web_client = WebSiteManagementClient(credential, creds["azure_subscription_id"])

func_app_name = "zipdeploy-test-func"
resource_group = "zipdeploy-test-rg"

print(f"Checking functions in {func_app_name}...")
print()

# Retry loop
for attempt in range(1, 7):
    print(f"Attempt {attempt}/6:")
    try:
        functions = list(web_client.web_apps.list_functions(resource_group, func_app_name))
        print(f"  Found {len(functions)} functions:")
        for func in functions:
            func_name = func.name.split('/')[-1] if '/' in func.name else func.name
            print(f"    - {func_name}")
        
        if len(functions) >= 2:
            print("\nSUCCESS: Functions detected!")
            break
        else:
            if attempt < 6:
                print("  Waiting 30s...")
                time.sleep(30)
    except Exception as e:
        print(f"  Error: {e}")
        if attempt < 6:
            print("  Waiting 30s...")
            time.sleep(30)
else:
    print("\nFAILED: Functions not detected after 6 attempts")
