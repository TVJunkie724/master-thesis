"""
Manual cleanup script for orphaned cloud resources.
Deletes AWS Resource Group and Azure Resource Group by name.

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/manual_cleanup_orphans.py sc2-aws-azure
"""
import sys
import json
import time
from pathlib import Path


def load_credentials():
    """Load credentials from config_credentials.json."""
    creds_paths = [
        Path("/app/config_credentials.json"),
        Path("/app/upload/template/config_credentials.json"),
    ]
    for path in creds_paths:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    raise FileNotFoundError("config_credentials.json not found")


def list_aws_resources(aws_creds: dict, rg_name: str):
    """List AWS Grafana workspaces and Lambda functions in a resource group."""
    import boto3
    
    region = aws_creds.get("aws_region", "eu-central-1")
    session = boto3.Session(
        aws_access_key_id=aws_creds["aws_access_key_id"],
        aws_secret_access_key=aws_creds["aws_secret_access_key"],
        region_name=region
    )
    
    print(f"\n=== AWS Resources (region: {region}) ===")
    
    # Check Grafana workspaces
    try:
        grafana = session.client("grafana")
        workspaces = grafana.list_workspaces()
        for ws in workspaces.get("workspaces", []):
            name = ws.get("name", "")
            ws_id = ws.get("id", "")
            if rg_name in name:
                print(f"  [Grafana] {name} (id: {ws_id})")
    except Exception as e:
        print(f"  [Grafana] Error: {e}")
    
    # Check Resource Groups (tag-based)
    try:
        rg_client = session.client("resource-groups")
        groups = rg_client.list_groups()
        for group in groups.get("GroupIdentifiers", []):
            name = group.get("GroupName", "")
            if rg_name in name:
                print(f"  [ResourceGroup] {name}")
    except Exception as e:
        print(f"  [ResourceGroup] Error: {e}")
    
    # Check Lambda functions
    try:
        lambda_client = session.client("lambda")
        functions = lambda_client.list_functions()
        for fn in functions.get("Functions", []):
            name = fn.get("FunctionName", "")
            if rg_name in name:
                print(f"  [Lambda] {name}")
    except Exception as e:
        print(f"  [Lambda] Error: {e}")
    
    # Check IoT Rules
    try:
        iot_client = session.client("iot")
        rules = iot_client.list_topic_rules()
        for rule in rules.get("rules", []):
            name = rule.get("ruleName", "")
            if rg_name.replace("-", "_") in name:
                print(f"  [IoT Rule] {name}")
    except Exception as e:
        print(f"  [IoT Rule] Error: {e}")


def delete_aws_resources(aws_creds: dict, rg_name: str):
    """Delete AWS resources matching the resource group name."""
    import boto3
    
    region = aws_creds.get("aws_region", "eu-central-1")
    session = boto3.Session(
        aws_access_key_id=aws_creds["aws_access_key_id"],
        aws_secret_access_key=aws_creds["aws_secret_access_key"],
        region_name=region
    )
    
    print(f"\n=== Deleting AWS Resources ===")
    
    # Delete Grafana workspaces FIRST (they depend on roles)
    try:
        grafana = session.client("grafana")
        workspaces = grafana.list_workspaces()
        for ws in workspaces.get("workspaces", []):
            name = ws.get("name", "")
            ws_id = ws.get("id", "")
            if rg_name in name:
                print(f"  Deleting Grafana workspace: {name}...")
                grafana.delete_workspace(workspaceId=ws_id)
                print(f"    ✓ Deleted {name}")
    except Exception as e:
        print(f"  [Grafana] Error: {e}")
    
    # Delete IoT Rules (they reference lambdas)
    try:
        iot_client = session.client("iot")
        rules = iot_client.list_topic_rules()
        for rule in rules.get("rules", []):
            name = rule.get("ruleName", "")
            if rg_name.replace("-", "_") in name:
                print(f"  Deleting IoT Rule: {name}...")
                iot_client.delete_topic_rule(ruleName=name)
                print(f"    ✓ Deleted {name}")
    except Exception as e:
        print(f"  [IoT Rule] Error: {e}")
    
    # Delete Lambda functions
    try:
        lambda_client = session.client("lambda")
        functions = lambda_client.list_functions()
        for fn in functions.get("Functions", []):
            name = fn.get("FunctionName", "")
            if rg_name in name:
                print(f"  Deleting Lambda: {name}...")
                lambda_client.delete_function(FunctionName=name)
                print(f"    ✓ Deleted {name}")
    except Exception as e:
        print(f"  [Lambda] Error: {e}")
    
    # Delete S3 buckets
    try:
        s3 = session.client("s3")
        buckets = s3.list_buckets()
        for bucket in buckets.get("Buckets", []):
            name = bucket.get("Name", "")
            if rg_name in name:
                print(f"  Deleting S3 bucket: {name}...")
                # Empty bucket first
                s3_resource = session.resource("s3")
                bucket_obj = s3_resource.Bucket(name)
                bucket_obj.objects.all().delete()
                bucket_obj.delete()
                print(f"    ✓ Deleted {name}")
    except Exception as e:
        print(f"  [S3] Error: {e}")
    
    # Delete IAM roles (after lambdas)
    try:
        iam = session.client("iam")
        roles = iam.list_roles()
        for role in roles.get("Roles", []):
            name = role.get("RoleName", "")
            if rg_name in name:
                print(f"  Deleting IAM role: {name}...")
                # Detach policies first
                attached = iam.list_attached_role_policies(RoleName=name)
                for policy in attached.get("AttachedPolicies", []):
                    iam.detach_role_policy(RoleName=name, PolicyArn=policy["PolicyArn"])
                # Delete inline policies
                inline = iam.list_role_policies(RoleName=name)
                for policy_name in inline.get("PolicyNames", []):
                    iam.delete_role_policy(RoleName=name, PolicyName=policy_name)
                # Now delete role
                iam.delete_role(RoleName=name)
                print(f"    ✓ Deleted {name}")
    except Exception as e:
        print(f"  [IAM] Error: {e}")
    
    # Delete Resource Group
    try:
        rg_client = session.client("resource-groups")
        groups = rg_client.list_groups()
        for group in groups.get("GroupIdentifiers", []):
            name = group.get("GroupName", "")
            if rg_name in name:
                print(f"  Deleting Resource Group: {name}...")
                rg_client.delete_group(GroupName=name)
                print(f"    ✓ Deleted {name}")
    except Exception as e:
        print(f"  [ResourceGroup] Error: {e}")


def list_azure_resources(azure_creds: dict, rg_name: str):
    """List Azure resources in the resource group."""
    from azure.identity import ClientSecretCredential
    from azure.mgmt.resource.resources import ResourceManagementClient
    
    credential = ClientSecretCredential(
        tenant_id=azure_creds["azure_tenant_id"],
        client_id=azure_creds["azure_client_id"],
        client_secret=azure_creds["azure_client_secret"]
    )
    
    resource_client = ResourceManagementClient(
        credential, azure_creds["azure_subscription_id"]
    )
    
    print(f"\n=== Azure Resources ===")
    
    # Check if resource group exists
    full_name = f"{rg_name}-rg"
    try:
        rg = resource_client.resource_groups.get(full_name)
        print(f"  [ResourceGroup] {full_name} (location: {rg.location})")
        
        # List resources in the group
        resources = resource_client.resources.list_by_resource_group(full_name)
        for r in resources:
            print(f"    - {r.type}: {r.name}")
    except Exception as e:
        if "ResourceGroupNotFound" in str(e):
            print(f"  [ResourceGroup] {full_name} does not exist")
        else:
            print(f"  [ResourceGroup] Error: {e}")


def delete_azure_resources(azure_creds: dict, rg_name: str):
    """Delete Azure resource group and all its resources."""
    from azure.identity import ClientSecretCredential
    from azure.mgmt.resource.resources import ResourceManagementClient
    
    credential = ClientSecretCredential(
        tenant_id=azure_creds["azure_tenant_id"],
        client_id=azure_creds["azure_client_id"],
        client_secret=azure_creds["azure_client_secret"]
    )
    
    resource_client = ResourceManagementClient(
        credential, azure_creds["azure_subscription_id"]
    )
    
    print(f"\n=== Deleting Azure Resources ===")
    
    full_name = f"{rg_name}-rg"
    try:
        print(f"  Deleting resource group: {full_name}...")
        poller = resource_client.resource_groups.begin_delete(full_name)
        print(f"  Waiting for deletion to complete (this may take several minutes)...")
        poller.result()
        print(f"    ✓ Deleted {full_name}")
    except Exception as e:
        if "ResourceGroupNotFound" in str(e):
            print(f"    ✓ Resource group {full_name} already deleted")
        else:
            print(f"  [Error] {e}")


def list_gcp_resources(gcp_creds: dict, rg_name: str):
    """List GCP resources matching the naming pattern."""
    from google.cloud import firestore
    from google.cloud import storage
    from google.cloud import functions_v2
    from google.oauth2 import service_account
    
    project_id = gcp_creds.get("gcp_project_id")
    creds_file = gcp_creds.get("gcp_credentials_file", "gcp_credentials.json")
    
    # Try to find credentials file
    creds_paths = [
        Path(f"/app/{creds_file}"),
        Path(f"/app/upload/template/{creds_file}"),
    ]
    
    credentials = None
    for path in creds_paths:
        if path.exists():
            credentials = service_account.Credentials.from_service_account_file(str(path))
            break
    
    if not credentials:
        print(f"\n=== GCP Resources ===")
        print(f"  [Warning] GCP credentials file not found: {creds_file}")
        return
    
    print(f"\n=== GCP Resources (project: {project_id}) ===")
    
    # Check Cloud Storage buckets
    try:
        storage_client = storage.Client(project=project_id, credentials=credentials)
        for bucket in storage_client.list_buckets():
            if rg_name in bucket.name:
                print(f"  [Storage] {bucket.name}")
    except Exception as e:
        print(f"  [Storage] Error: {e}")
    
    # Check Firestore databases
    try:
        # Note: Listing databases requires special permissions
        print(f"  [Firestore] Check manually for database: {rg_name}")
    except Exception as e:
        print(f"  [Firestore] Error: {e}")


def delete_gcp_resources(gcp_creds: dict, rg_name: str):
    """Delete GCP resources matching the naming pattern."""
    from google.cloud import storage
    from google.cloud import firestore_admin_v1
    from google.oauth2 import service_account
    
    project_id = gcp_creds.get("gcp_project_id")
    creds_file = gcp_creds.get("gcp_credentials_file", "gcp_credentials.json")
    
    # Try to find credentials file
    creds_paths = [
        Path(f"/app/{creds_file}"),
        Path(f"/app/upload/template/{creds_file}"),
    ]
    
    credentials = None
    for path in creds_paths:
        if path.exists():
            credentials = service_account.Credentials.from_service_account_file(str(path))
            break
    
    if not credentials:
        print(f"\n=== GCP Cleanup ===")
        print(f"  [Warning] GCP credentials file not found: {creds_file}")
        return
    
    print(f"\n=== Deleting GCP Resources ===")
    
    # Delete Cloud Storage buckets
    try:
        storage_client = storage.Client(project=project_id, credentials=credentials)
        for bucket in storage_client.list_buckets():
            if rg_name in bucket.name:
                print(f"  Deleting bucket: {bucket.name}...")
                # Delete all objects first
                blobs = bucket.list_blobs()
                for blob in blobs:
                    blob.delete()
                bucket.delete()
                print(f"    ✓ Deleted {bucket.name}")
    except Exception as e:
        print(f"  [Storage] Error: {e}")
    
    # Note: Firestore database deletion has a delay before recreation is possible
    print(f"  [Note] Firestore database '{rg_name}' may need manual deletion via Console")


def main():
    if len(sys.argv) < 2:
        print("Usage: python manual_cleanup_orphans.py <resource-group-name> [--list|--delete]")
        print("  --list    Only list resources (default)")
        print("  --delete  Actually delete the resources")
        sys.exit(1)
    
    rg_name = sys.argv[1]
    delete_mode = "--delete" in sys.argv
    
    print("=" * 60)
    print(f"  Orphan Resource Cleanup: {rg_name}")
    print("=" * 60)
    print(f"Mode: {'DELETE' if delete_mode else 'LIST ONLY'}")
    
    creds = load_credentials()
    
    if delete_mode:
        # Delete in order: AWS -> Azure -> GCP
        delete_aws_resources(creds["aws"], rg_name)
        delete_azure_resources(creds["azure"], rg_name)
        delete_gcp_resources(creds.get("gcp", {}), rg_name)
    else:
        # Just list
        list_aws_resources(creds["aws"], rg_name)
        list_azure_resources(creds["azure"], rg_name)
        list_gcp_resources(creds.get("gcp", {}), rg_name)
    
    print("\n" + "=" * 60)
    print("  COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
