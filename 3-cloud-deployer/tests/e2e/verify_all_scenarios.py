"""
Verify cleanup of ALL cloud resources across ALL scenarios.

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
        python tests/e2e/verify_all_scenarios.py
"""
import json
from pathlib import Path


# All known scenario prefixes
PREFIXES = [
    "sc-aws-azure", "sc-aws-gcp", 
    "sc-azure-aws", "sc-azure-gcp",
    "sc-gcp-aws", "sc-gcp-azure",
    "mc-e2e", "tf-e2e",
    "iso-stepfunc", "iso-grafana", "iso-logicapp"
]


def load_credentials():
    """Load credentials from config_credentials.json."""
    creds_paths = [
        Path("/app/upload/template/config_credentials.json"),
        Path("/app/config_credentials.json"),
    ]
    for path in creds_paths:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    raise FileNotFoundError("config_credentials.json not found")


def matches_prefix(name: str) -> bool:
    """Check if name matches any known prefix."""
    name_normalized = name.lower().replace("_", "-")
    for prefix in PREFIXES:
        if prefix in name_normalized:
            return True
    return False


def check_aws(creds: dict) -> list:
    """Check all AWS resources."""
    import boto3
    
    aws = creds.get("aws", {})
    region = aws.get("aws_region", "eu-central-1")
    session = boto3.Session(
        aws_access_key_id=aws["aws_access_key_id"],
        aws_secret_access_key=aws["aws_secret_access_key"],
        region_name=region
    )
    
    found = []
    
    # Lambda functions
    try:
        client = session.client("lambda")
        response = client.list_functions()
        for f in response.get("Functions", []):
            if matches_prefix(f["FunctionName"]):
                found.append(("Lambda", f["FunctionName"]))
    except Exception as e:
        found.append(("Lambda Error", str(e)))
    
    # Grafana workspaces
    try:
        client = session.client("grafana")
        response = client.list_workspaces()
        for w in response.get("workspaces", []):
            name = w.get("name", "")
            if matches_prefix(name):
                found.append(("Grafana", f"{name} (id: {w['id']})"))
    except Exception as e:
        found.append(("Grafana Error", str(e)))
    
    # S3 buckets
    try:
        client = session.client("s3")
        response = client.list_buckets()
        for b in response.get("Buckets", []):
            if matches_prefix(b["Name"]):
                found.append(("S3", b["Name"]))
    except Exception as e:
        found.append(("S3 Error", str(e)))
    
    # IAM roles
    try:
        client = session.client("iam")
        response = client.list_roles()
        for r in response.get("Roles", []):
            if matches_prefix(r["RoleName"]):
                found.append(("IAM Role", r["RoleName"]))
    except Exception as e:
        found.append(("IAM Error", str(e)))
    
    # Resource Groups
    try:
        client = session.client("resource-groups")
        response = client.list_groups()
        for g in response.get("GroupIdentifiers", []):
            if matches_prefix(g["GroupName"]):
                found.append(("Resource Group", g["GroupName"]))
    except Exception as e:
        found.append(("Resource Groups Error", str(e)))
    
    # IoT Rules
    try:
        client = session.client("iot")
        response = client.list_topic_rules()
        for r in response.get("rules", []):
            if matches_prefix(r["ruleName"]):
                found.append(("IoT Rule", r["ruleName"]))
    except Exception as e:
        found.append(("IoT Error", str(e)))
    
    # Step Functions
    try:
        client = session.client("stepfunctions")
        response = client.list_state_machines()
        for sm in response.get("stateMachines", []):
            if matches_prefix(sm["name"]):
                found.append(("Step Functions", sm["name"]))
    except Exception as e:
        found.append(("Step Functions Error", str(e)))
    
    # TwinMaker workspaces
    try:
        client = session.client("iottwinmaker")
        response = client.list_workspaces()
        for ws in response.get("workspaceSummaries", []):
            if matches_prefix(ws["workspaceId"]):
                found.append(("TwinMaker", ws["workspaceId"]))
    except Exception as e:
        found.append(("TwinMaker Error", str(e)))
    
    return found


def check_azure(creds: dict) -> list:
    """Check all Azure resources."""
    found = []
    
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resource import ResourceManagementClient
        
        azure = creds.get("azure", {})
        credential = ClientSecretCredential(
            tenant_id=azure["azure_tenant_id"],
            client_id=azure["azure_client_id"],
            client_secret=azure["azure_client_secret"]
        )
        
        client = ResourceManagementClient(credential, azure["azure_subscription_id"])
        
        # List all resource groups
        for rg in client.resource_groups.list():
            if matches_prefix(rg.name):
                found.append(("Resource Group", rg.name))
                # Count resources in each matching group
                try:
                    resources = list(client.resources.list_by_resource_group(rg.name))
                    if resources:
                        found.append(("  Resources", f"{len(resources)} resources in {rg.name}"))
                except Exception:
                    pass
                    
    except ImportError:
        found.append(("SDK Error", "azure.identity not installed"))
    except Exception as e:
        found.append(("Error", str(e)))
    
    return found


def check_gcp(creds: dict) -> list:
    """Check all GCP resources."""
    found = []
    
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
        
        gcp = creds.get("gcp", {})
        project_id = gcp.get("gcp_project_id")
        creds_file = gcp.get("gcp_credentials_file", "gcp_credentials.json")
        
        # Find credentials file
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
            found.append(("Credentials", "GCP credentials file not found"))
            return found
        
        # Check Storage buckets
        try:
            storage_client = storage.Client(project=project_id, credentials=credentials)
            for bucket in storage_client.list_buckets():
                if matches_prefix(bucket.name):
                    found.append(("Storage", bucket.name))
        except Exception as e:
            found.append(("Storage Error", str(e)))
        
        # Check Firestore databases (via REST API)
        try:
            from google.cloud import firestore_admin_v1
            admin_client = firestore_admin_v1.FirestoreAdminClient(credentials=credentials)
            parent = f"projects/{project_id}"
            databases = admin_client.list_databases(parent=parent)
            for db in databases:
                db_name = db.name.split("/")[-1]
                if matches_prefix(db_name):
                    found.append(("Firestore", db_name))
        except Exception as e:
            found.append(("Firestore", f"Manual check needed (API error: {type(e).__name__})"))
        
        # Check Cloud Functions (Gen 2)
        try:
            from google.cloud import functions_v2
            client = functions_v2.FunctionServiceClient(credentials=credentials)
            parent = f"projects/{project_id}/locations/-"
            for fn in client.list_functions(parent=parent):
                fn_name = fn.name.split("/")[-1]
                if matches_prefix(fn_name):
                    found.append(("Cloud Function", fn_name))
        except Exception as e:
            found.append(("Cloud Functions", f"Manual check needed (API error: {type(e).__name__})"))
            
    except ImportError as e:
        found.append(("SDK Error", f"GCP SDK not fully installed: {e}"))
    except Exception as e:
        found.append(("Error", str(e)))
    
    return found


def main():
    print("=" * 70)
    print("  COMPREHENSIVE CLOUD RESOURCE VERIFICATION")
    print("=" * 70)
    print(f"Checking prefixes: {', '.join(PREFIXES)}")
    print()
    
    creds = load_credentials()
    total_found = 0
    
    # AWS
    print("=" * 70)
    print("  AWS")
    print("=" * 70)
    aws_found = check_aws(creds)
    if aws_found:
        for category, name in aws_found:
            print(f"  [{category}] {name}")
        total_found += len([f for f in aws_found if "Error" not in f[0]])
    else:
        print("  All clean - no resources found")
    
    # Azure
    print()
    print("=" * 70)
    print("  AZURE")
    print("=" * 70)
    azure_found = check_azure(creds)
    if azure_found:
        for category, name in azure_found:
            print(f"  [{category}] {name}")
        total_found += len([f for f in azure_found if "Error" not in f[0]])
    else:
        print("  All clean - no resources found")
    
    # GCP
    print()
    print("=" * 70)
    print("  GCP")
    print("=" * 70)
    gcp_found = check_gcp(creds)
    if gcp_found:
        for category, name in gcp_found:
            print(f"  [{category}] {name}")
        total_found += len([f for f in gcp_found if "Error" not in f[0] and "Manual check" not in f[1]])
    else:
        print("  All clean - no resources found")
    
    # Summary
    print()
    print("=" * 70)
    if total_found > 0:
        print(f"  RESULT: {total_found} RESOURCES FOUND - cleanup may be needed")
    else:
        print("  RESULT: ALL CLEAN - no orphaned resources detected")
    print("=" * 70)


if __name__ == "__main__":
    main()
