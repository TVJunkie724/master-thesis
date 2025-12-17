#!/usr/bin/env python3
"""Check Azure Function App logs for errors."""
import json

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

print(f"Checking logs for {func_app_name}...")
print()

# Get site config
try:
    config = web_client.web_apps.get_configuration(resource_group, func_app_name)
    print("Site Configuration:")
    print(f"  Python version: {config.linux_fx_version}")
    print(f"  App command line: {config.app_command_line}")
    print()
except Exception as e:
    print(f"Error getting config: {e}")

# Get app settings
try:
    settings = web_client.web_apps.list_application_settings(resource_group, func_app_name)
    print("App Settings:")
    for key, value in sorted(settings.properties.items()):
        if 'SECRET' in key.upper() or 'KEY' in key.upper() or 'PASSWORD' in key.upper():
            print(f"  {key}: ***")
        else:
            print(f"  {key}: {value}")
    print()
except Exception as e:
    print(f"Error getting settings: {e}")

# Try to get deployment status
try:
    deployments = list(web_client.web_apps.list_deployments(resource_group, func_app_name))
    print(f"Deployments ({len(deployments)}):")
    for d in deployments[:5]:
        print(f"  - {d.name}: status={d.status}, active={d.active}")
except Exception as e:
    print(f"Error getting deployments: {e}")
