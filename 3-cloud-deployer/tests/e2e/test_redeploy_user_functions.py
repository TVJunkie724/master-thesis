#!/usr/bin/env python3
"""
Redeploy user functions ZIP to existing Azure Function App.
Uses the already-deployed tf-e2e-az infrastructure.
"""
import sys
import os
import json
import time
import requests
from pathlib import Path
from requests.auth import HTTPBasicAuth

# Add src to path
sys.path.insert(0, '/app/src')

# Azure SDK
from azure.identity import ClientSecretCredential
from azure.mgmt.web import WebSiteManagementClient

# Configuration
RG_NAME = "tf-e2e-az-rg"
USER_APP_NAME = "tf-e2e-az-user-functions"
ZIP_PATH = Path("/app/e2e_persistence_temp/azure_terraform_e2e/azure_terraform_e2e0/tf-e2e-az/.build/azure/user_functions_combined.zip")

# Load credentials from environment or config
CREDS_PATH = Path("/app/upload/template/config_credentials.json")
if not CREDS_PATH.exists():
    print("ERROR: config_credentials.json not found")
    sys.exit(1)

with open(CREDS_PATH) as f:
    creds = json.load(f)
azure_creds = creds.get("azure", {})

subscription_id = azure_creds["azure_subscription_id"]
credential = ClientSecretCredential(
    tenant_id=azure_creds["azure_tenant_id"],
    client_id=azure_creds["azure_client_id"],
    client_secret=azure_creds["azure_client_secret"]
)

web_client = WebSiteManagementClient(credential, subscription_id)

print("=" * 60)
print("  USER FUNCTIONS ZIP REDEPLOY TEST")
print("=" * 60)
print(f"  Resource Group: {RG_NAME}")
print(f"  User App: {USER_APP_NAME}")
print(f"  ZIP Path: {ZIP_PATH}")
print(f"  ZIP Size: {ZIP_PATH.stat().st_size} bytes")
print("=" * 60)

# 1. List ZIP contents
print("\n1️⃣ ZIP Contents:")
import zipfile
with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
    folders = set()
    for name in zf.namelist():
        parts = name.split('/')
        if len(parts) > 1 and parts[0] not in folders:
            folders.add(parts[0])
            print(f"   - {parts[0]}/")

# 2. Get publishing credentials and deploy
print("\n2️⃣ Deploying ZIP via Kudu...")
try:
    publish_creds = web_client.web_apps.begin_list_publishing_credentials(RG_NAME, USER_APP_NAME).result()
    kudu_url = f"https://{USER_APP_NAME}.scm.azurewebsites.net/api/zipdeploy?isAsync=true"
    
    with open(ZIP_PATH, 'rb') as f:
        response = requests.post(
            kudu_url,
            data=f,
            auth=HTTPBasicAuth(
                publish_creds.publishing_user_name,
                publish_creds.publishing_password
            ),
            headers={"Content-Type": "application/zip"},
            timeout=300
        )
    
    if response.status_code in [200, 202]:
        print(f"   ✓ ZIP uploaded successfully (status: {response.status_code})")
    else:
        print(f"   ✗ Upload failed (status: {response.status_code})")
        print(f"   Response: {response.text}")
        sys.exit(1)
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

# 3. Wait for Oryx build
print("\n3️⃣ Waiting 180s for Oryx build to complete...")
time.sleep(180)

# 4. List functions
print("\n4️⃣ Checking deployed functions...")
try:
    functions = list(web_client.web_apps.list_functions(RG_NAME, USER_APP_NAME))
    func_names = [f.name.split('/')[-1] for f in functions]
    
    print(f"   Found {len(func_names)} functions:")
    for func_name in func_names:
        print(f"   - {func_name}")
    
    # Check for expected processor functions
    expected = ["pressure-sensor-1-processor", "temperature-sensor-1-processor", "temperature-sensor-2-processor"]
    found = 0
    for exp in expected:
        if exp in func_names:
            print(f"   ✓ Found: {exp}")
            found += 1
        else:
            print(f"   ✗ Missing: {exp}")
    
    if found == len(expected):
        print("\n✅ ALL EXPECTED FUNCTIONS DEPLOYED SUCCESSFULLY!")
    else:
        print(f"\n⚠️ Only {found}/{len(expected)} expected functions found")
        
except Exception as e:
    print(f"   ✗ Error listing functions: {e}")
    sys.exit(1)

print("\nDone!")
