#!/usr/bin/env python
"""
One-time cleanup for orphaned Azure observability resources.

Run via Docker:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python /app/scripts/one_time_orphan_cleanup.py

Set DRY_RUN = True to preview what will be deleted.
"""
import json
from azure.identity import ClientSecretCredential
from azure.mgmt.loganalytics import LogAnalyticsManagementClient
from azure.mgmt.applicationinsights import ApplicationInsightsManagementClient
from azure.mgmt.digitaltwins import AzureDigitalTwinsManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.iothub import IotHubClient
from azure.mgmt.eventgrid import EventGridManagementClient
from azure.mgmt.cosmosdb import CosmosDBManagementClient
from azure.mgmt.logic import LogicManagementClient
from azure.mgmt.dashboard import DashboardManagementClient
import requests

PREFIX = "sc2-"
DRY_RUN = True  # Set to False to actually delete

with open('/app/upload/template/config_credentials.json') as f:
    creds = json.load(f).get('azure', {})

credential = ClientSecretCredential(
    tenant_id=creds['azure_tenant_id'],
    client_id=creds['azure_client_id'],
    client_secret=creds['azure_client_secret']
)
sub_id = creds['azure_subscription_id']

print(f"{'[DRY RUN] ' if DRY_RUN else ''}Cleaning orphans with prefix: {PREFIX}")

# 1. Log Analytics Workspaces
print("\n=== Log Analytics Workspaces ===")
try:
    la_client = LogAnalyticsManagementClient(credential, sub_id)
    for ws in la_client.workspaces.list():
        if ws.name.startswith(PREFIX):
            rg = ws.id.split('/')[4]
            print(f"  Found: {ws.name} (RG: {rg})")
            if not DRY_RUN:
                la_client.workspaces.begin_delete(rg, ws.name, force=True).result(timeout=300)
                print(f"    ✓ Deleted")
except Exception as e:
    print(f"  Error: {e}")

# 2. Application Insights
print("\n=== Application Insights ===")
try:
    ai_client = ApplicationInsightsManagementClient(credential, sub_id)
    for comp in ai_client.components.list():
        if comp.name.startswith(PREFIX):
            rg = comp.id.split('/')[4]
            print(f"  Found: {comp.name} (RG: {rg})")
            if not DRY_RUN:
                ai_client.components.delete(rg, comp.name)
                print(f"    ✓ Deleted")
except Exception as e:
    print(f"  Error: {e}")

# 3. Diagnostic Settings (scan ALL resource types)
print("\n=== Diagnostic Settings ===")
token = credential.get_token("https://management.azure.com/.default").token
headers = {"Authorization": f"Bearer {token}"}

def delete_diag_settings(resource_id, resource_name, resource_type):
    url = f"https://management.azure.com{resource_id}/providers/Microsoft.Insights/diagnosticSettings?api-version=2021-05-01-preview"
    try:
        resp = requests.get(url, headers=headers)
        if resp.ok:
            for s in resp.json().get("value", []):
                print(f"  {resource_type} {resource_name}: {s['name']}")
                if not DRY_RUN:
                    del_url = f"https://management.azure.com{resource_id}/providers/Microsoft.Insights/diagnosticSettings/{s['name']}?api-version=2021-05-01-preview"
                    requests.delete(del_url, headers=headers)
                    print(f"    ✓ Deleted")
    except Exception as e:
        print(f"  Error scanning {resource_type} {resource_name}: {e}")

# ADT
print("  Scanning ADT instances...")
try:
    for r in AzureDigitalTwinsManagementClient(credential, sub_id).digital_twins.list():
        if r.name.startswith(PREFIX):
            delete_diag_settings(r.id, r.name, "ADT")
except Exception as e:
    print(f"  ADT scan error: {e}")

# Storage + blobServices
print("  Scanning Storage accounts...")
try:
    for r in StorageManagementClient(credential, sub_id).storage_accounts.list():
        if r.name.startswith(PREFIX.replace("-", "")):
            delete_diag_settings(r.id, r.name, "Storage")
            delete_diag_settings(f"{r.id}/blobServices/default", r.name, "Storage/blob")
except Exception as e:
    print(f"  Storage scan error: {e}")

# IoT Hub
print("  Scanning IoT Hubs...")
try:
    for r in IotHubClient(credential, sub_id).iot_hub_resource.list_by_subscription():
        if r.name.startswith(PREFIX):
            delete_diag_settings(r.id, r.name, "IoTHub")
except Exception as e:
    print(f"  IoT Hub scan error: {e}")

# EventGrid
print("  Scanning EventGrid topics...")
try:
    for r in EventGridManagementClient(credential, sub_id).system_topics.list_by_subscription():
        if r.name.startswith(PREFIX):
            delete_diag_settings(r.id, r.name, "EventGrid")
except Exception as e:
    print(f"  EventGrid scan error: {e}")

# CosmosDB
print("  Scanning CosmosDB accounts...")
try:
    for r in CosmosDBManagementClient(credential, sub_id).database_accounts.list():
        if r.name.startswith(PREFIX):
            delete_diag_settings(r.id, r.name, "CosmosDB")
except Exception as e:
    print(f"  CosmosDB scan error: {e}")

# Logic Apps
print("  Scanning Logic Apps...")
try:
    for r in LogicManagementClient(credential, sub_id).workflows.list_by_subscription():
        if r.name.startswith(PREFIX):
            delete_diag_settings(r.id, r.name, "LogicApp")
except Exception as e:
    print(f"  Logic Apps scan error: {e}")

# Grafana
print("  Scanning Grafana workspaces...")
try:
    for r in DashboardManagementClient(credential, sub_id).grafana.list():
        if r.name.startswith(PREFIX):
            delete_diag_settings(r.id, r.name, "Grafana")
except Exception as e:
    print(f"  Grafana scan error: {e}")

print("\n✓ Cleanup complete")
