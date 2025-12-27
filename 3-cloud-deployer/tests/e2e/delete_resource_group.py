#!/usr/bin/env python3
"""
Delete Azure Resource Group Helper Script.

Usage: python delete_resource_group.py <resource_group_name>

Requires Azure credentials via environment variables or DefaultAzureCredential.
"""
import sys
import os

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient


def delete_resource_group(resource_group_name: str, subscription_id: str):
    """Delete an Azure resource group."""
    print(f"Deleting resource group: {resource_group_name}")
    
    credential = DefaultAzureCredential()
    client = ResourceManagementClient(credential, subscription_id)
    
    # Check if resource group exists
    try:
        rg = client.resource_groups.get(resource_group_name)
        print(f"Found resource group: {rg.name} in {rg.location}")
    except Exception as e:
        print(f"Resource group '{resource_group_name}' not found: {e}")
        return False
    
    # Delete resource group (asynchronous operation)
    print("Starting deletion (this may take several minutes)...")
    poller = client.resource_groups.begin_delete(resource_group_name)
    
    # Wait for completion
    result = poller.result()
    print(f"Resource group '{resource_group_name}' deleted successfully!")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python delete_resource_group.py <resource_group_name>")
        sys.exit(1)
    
    rg_name = sys.argv[1]
    
    # Get subscription ID from environment or credentials file
    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription_id:
        # Try to load from config_credentials.json
        import json
        config_path = "/app/upload/template/config_credentials.json"
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
                subscription_id = config.get("azure", {}).get("subscription_id")
    
    if not subscription_id:
        print("Error: AZURE_SUBSCRIPTION_ID not found")
        sys.exit(1)
    
    print(f"Using subscription: {subscription_id}")
    success = delete_resource_group(rg_name, subscription_id)
    sys.exit(0 if success else 1)
