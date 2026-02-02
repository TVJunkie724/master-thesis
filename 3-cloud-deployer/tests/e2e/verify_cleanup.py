"""
Verify cleanup of cloud resources for a given prefix.

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/verify_cleanup.py sc2-aws-azure
"""
import sys
import json
from pathlib import Path


def verify_aws(creds: dict, prefix: str) -> list:
    """Check for remaining AWS resources."""
    import boto3
    
    aws = creds.get("aws", {})
    region = aws.get("aws_region", "eu-central-1")
    session = boto3.Session(
        aws_access_key_id=aws["aws_access_key_id"],
        aws_secret_access_key=aws["aws_secret_access_key"],
        region_name=region
    )
    
    remaining = []
    
    # Check Lambda functions
    try:
        lam = session.client("lambda")
        functions = lam.list_functions()
        for f in functions.get("Functions", []):
            if prefix in f["FunctionName"]:
                remaining.append(f"AWS Lambda: {f['FunctionName']}")
    except Exception as e:
        remaining.append(f"AWS Lambda check failed: {e}")
    
    # Check Grafana workspaces
    try:
        grafana = session.client("grafana")
        workspaces = grafana.list_workspaces()
        for w in workspaces.get("workspaces", []):
            if prefix in w.get("name", ""):
                remaining.append(f"AWS Grafana: {w['name']} (id: {w['id']})")
    except Exception as e:
        remaining.append(f"AWS Grafana check failed: {e}")
    
    # Check S3 buckets
    try:
        s3 = session.client("s3")
        buckets = s3.list_buckets()
        for b in buckets.get("Buckets", []):
            if prefix in b["Name"]:
                remaining.append(f"AWS S3: {b['Name']}")
    except Exception as e:
        remaining.append(f"AWS S3 check failed: {e}")
    
    # Check IAM roles
    try:
        iam = session.client("iam")
        roles = iam.list_roles()
        for r in roles.get("Roles", []):
            if prefix in r["RoleName"]:
                remaining.append(f"AWS IAM Role: {r['RoleName']}")
    except Exception as e:
        remaining.append(f"AWS IAM check failed: {e}")
    
    # Check IoT Rules
    try:
        iot = session.client("iot")
        rules = iot.list_topic_rules()
        for r in rules.get("rules", []):
            if prefix.replace("-", "_") in r["ruleName"]:
                remaining.append(f"AWS IoT Rule: {r['ruleName']}")
    except Exception as e:
        remaining.append(f"AWS IoT check failed: {e}")
    
    # Check Resource Groups
    try:
        rg = session.client("resource-groups")
        groups = rg.list_groups()
        for g in groups.get("GroupIdentifiers", []):
            if prefix in g["GroupName"]:
                remaining.append(f"AWS Resource Group: {g['GroupName']}")
    except Exception as e:
        remaining.append(f"AWS Resource Groups check failed: {e}")
    
    return remaining


def verify_azure(creds: dict, prefix: str) -> list:
    """Check for remaining Azure resources."""
    remaining = []
    
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resource import ResourceManagementClient
        
        azure = creds.get("azure", {})
        credential = ClientSecretCredential(
            tenant_id=azure["azure_tenant_id"],
            client_id=azure["azure_client_id"],
            client_secret=azure["azure_client_secret"]
        )
        
        resource_client = ResourceManagementClient(
            credential, azure["azure_subscription_id"]
        )
        
        # Check resource groups
        rg_name = f"{prefix}-rg"
        try:
            rg = resource_client.resource_groups.get(rg_name)
            remaining.append(f"Azure Resource Group: {rg_name}")
            
            # List resources in the group
            resources = resource_client.resources.list_by_resource_group(rg_name)
            for r in resources:
                remaining.append(f"  - {r.type}: {r.name}")
        except Exception:
            pass  # Resource group doesn't exist, which is good
            
    except ImportError:
        remaining.append("Azure SDK not available for verification")
    except Exception as e:
        remaining.append(f"Azure check failed: {e}")
    
    return remaining


def verify_gcp(creds: dict, prefix: str) -> list:
    """Check for remaining GCP resources."""
    remaining = []
    
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
        from googleapiclient import discovery
        
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
            remaining.append("GCP credentials file not found")
            return remaining
        
        prefix_underscore = prefix.replace("-", "_")
        
        # Check Storage buckets
        try:
            storage_client = storage.Client(project=project_id, credentials=credentials)
            for bucket in storage_client.list_buckets():
                if prefix in bucket.name or prefix_underscore in bucket.name:
                    remaining.append(f"GCP Storage: {bucket.name}")
        except Exception as e:
            remaining.append(f"GCP Storage check failed: {e}")
        
        # Check Pub/Sub topics
        try:
            pubsub = discovery.build('pubsub', 'v1', credentials=credentials)
            topics = pubsub.projects().topics().list(project=f'projects/{project_id}').execute()
            for t in topics.get('topics', []):
                if prefix in t['name'] or prefix_underscore in t['name']:
                    topic_name = t['name'].split('/')[-1]
                    remaining.append(f"GCP Pub/Sub Topic: {topic_name}")
        except Exception as e:
            remaining.append(f"GCP Pub/Sub check failed: {e}")
        
        # Check Cloud Functions (v2)
        try:
            functions = discovery.build('cloudfunctions', 'v2', credentials=credentials)
            parent = f'projects/{project_id}/locations/-'
            result = functions.projects().locations().functions().list(parent=parent).execute()
            for f in result.get('functions', []):
                if prefix in f['name'] or prefix_underscore in f['name']:
                    func_name = f['name'].split('/')[-1]
                    remaining.append(f"GCP Cloud Function: {func_name}")
        except Exception as e:
            # Ignore "no functions" errors
            if "404" not in str(e) and "NOT_FOUND" not in str(e):
                remaining.append(f"GCP Functions check failed: {e}")
        
        # Check Service Accounts
        try:
            iam = discovery.build('iam', 'v1', credentials=credentials)
            sa_list = iam.projects().serviceAccounts().list(name=f'projects/{project_id}').execute()
            for sa in sa_list.get('accounts', []):
                if prefix in sa['email'] or prefix_underscore in sa['email']:
                    remaining.append(f"GCP Service Account: {sa['email']}")
        except Exception as e:
            remaining.append(f"GCP Service Account check failed: {e}")
        
    except ImportError:
        remaining.append("GCP SDK not fully available for verification")
    except Exception as e:
        remaining.append(f"GCP check failed: {e}")
    
    return remaining


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_cleanup.py <prefix>")
        sys.exit(1)
    
    prefix = sys.argv[1]
    
    # Load credentials
    creds_paths = [
        Path("/app/upload/template/config_credentials.json"),
        Path("/app/config_credentials.json"),
    ]
    
    creds = None
    for path in creds_paths:
        if path.exists():
            with open(path) as f:
                creds = json.load(f)
            break
    
    if not creds:
        print("ERROR: config_credentials.json not found")
        sys.exit(1)
    
    print("=" * 60)
    print(f"  Verifying Cleanup: {prefix}")
    print("=" * 60)
    
    all_remaining = []
    
    # AWS
    print("\n[AWS] Checking...")
    aws_remaining = verify_aws(creds, prefix)
    if aws_remaining:
        for r in aws_remaining:
            print(f"  FOUND: {r}")
        all_remaining.extend(aws_remaining)
    else:
        print("  All clean")
    
    # Azure
    print("\n[Azure] Checking...")
    azure_remaining = verify_azure(creds, prefix)
    if azure_remaining:
        for r in azure_remaining:
            print(f"  FOUND: {r}")
        all_remaining.extend(azure_remaining)
    else:
        print("  All clean")
    
    # GCP
    print("\n[GCP] Checking...")
    gcp_remaining = verify_gcp(creds, prefix)
    if gcp_remaining:
        for r in gcp_remaining:
            print(f"  FOUND: {r}")
        all_remaining.extend(gcp_remaining)
    else:
        print("  All clean")
    
    # Summary
    print("\n" + "=" * 60)
    if all_remaining:
        print(f"  CLEANUP INCOMPLETE - {len(all_remaining)} items remaining")
        sys.exit(1)
    else:
        print("  CLEANUP VERIFIED - All resources deleted")
        sys.exit(0)


if __name__ == "__main__":
    main()
