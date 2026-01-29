#!/usr/bin/env python3
"""List and optionally delete role assignments for Azure Grafana."""
import os
import json
import sys

try:
    import requests
except ImportError:
    print("requests not available, using urllib")
    import urllib.request
    import urllib.parse
    
    class FakeRequests:
        def post(self, url, data=None, headers=None):
            data_bytes = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=data_bytes, headers=headers or {})
            with urllib.request.urlopen(req) as resp:
                return type('Response', (), {'json': lambda: json.loads(resp.read())})()
        
        def get(self, url, headers=None):
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req) as resp:
                return type('Response', (), {'json': lambda: json.loads(resp.read())})()
        
        def delete(self, url, headers=None):
            req = urllib.request.Request(url, headers=headers or {}, method='DELETE')
            try:
                with urllib.request.urlopen(req) as resp:
                    return type('Response', (), {'status_code': resp.status})()
            except urllib.error.HTTPError as e:
                return type('Response', (), {'status_code': e.code})()
    
    requests = FakeRequests()

# Read credentials from the credentials cache
cred_cache = '/app/.credentials_cache/azure.json'
if os.path.exists(cred_cache):
    with open(cred_cache) as f:
        azure_creds = json.load(f)
    print(f"Found cached credentials for {azure_creds.get('tenant_id')}")
else:
    print(f"ERROR: No credentials cache at {cred_cache}")
    sys.exit(1)

# Get access token
token_url = f"https://login.microsoftonline.com/{azure_creds['tenant_id']}/oauth2/v2.0/token"
token_data = {
    "grant_type": "client_credentials",
    "client_id": azure_creds['client_id'],
    "client_secret": azure_creds['client_secret'],
    "scope": "https://management.azure.com/.default"
}
resp = requests.post(token_url, data=token_data)
token = resp.json().get('access_token')

if not token:
    print(f"ERROR: Failed to get token: {resp.json()}")
    sys.exit(1)

print("Got access token")

# List role assignments
scope = "/subscriptions/f387903f-4e3d-451d-9bcf-c6b634e69001/resourceGroups/sc-aws-gcp-rg/providers/Microsoft.Dashboard/grafana/sc-aws-gcp-grafana"
url = f"https://management.azure.com{scope}/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01"
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(url, headers=headers)
data = resp.json()

print(f"\nFound {len(data.get('value', []))} role assignments on Grafana:")
target_uuid = "d76ce5fd-5a42-540e-83de-df2dd9560f46"
target_found = False

for ra in data.get('value', []):
    props = ra.get('properties', {})
    name = ra.get('name')
    print(f"  - UUID: {name}")
    print(f"    principal: {props.get('principalId')}")
    print(f"    role_def: {props.get('roleDefinitionId', '').split('/')[-1]}")
    print()
    
    if name == target_uuid:
        target_found = True
        print(f"  *** THIS IS THE CONFLICTING ASSIGNMENT ***")

# Check for delete flag
if len(sys.argv) > 1 and sys.argv[1] == '--delete' and target_found:
    delete_url = f"https://management.azure.com{scope}/providers/Microsoft.Authorization/roleAssignments/{target_uuid}?api-version=2022-04-01"
    print(f"\nDeleting role assignment {target_uuid}...")
    resp = requests.delete(delete_url, headers=headers)
    print(f"Delete response status: {resp.status_code}")
elif target_found:
    print(f"\nTo delete the conflicting assignment, run: python {__file__} --delete")
