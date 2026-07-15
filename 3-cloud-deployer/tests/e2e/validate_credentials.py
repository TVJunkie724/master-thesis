"""
Quick credential validation for all cloud providers.

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
        python tests/e2e/validate_credentials.py
"""
import json
from pathlib import Path


def main():
    print("=" * 60)
    print("  CLOUD CREDENTIAL VALIDATION")
    print("=" * 60)
    
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
        return 1
    
    all_ok = True
    
    # AWS
    print("\n[AWS] Validating...")
    try:
        import boto3
        aws = creds.get("aws", {})
        session = boto3.Session(
            aws_access_key_id=aws["aws_access_key_id"],
            aws_secret_access_key=aws["aws_secret_access_key"],
            region_name=aws.get("aws_region", "eu-central-1")
        )
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        print(f"  Account: {identity['Account']}")
        print(f"  User ARN: {identity['Arn']}")
        print("  [OK] AWS credentials valid")
    except Exception as e:
        print(f"  [FAIL] AWS: {e}")
        all_ok = False
    
    # Azure
    print("\n[Azure] Validating...")
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resource.resources import ResourceManagementClient
        azure = creds.get("azure", {})
        credential = ClientSecretCredential(
            tenant_id=azure["azure_tenant_id"],
            client_id=azure["azure_client_id"],
            client_secret=azure["azure_client_secret"]
        )
        client = ResourceManagementClient(credential, azure["azure_subscription_id"])
        rgs = list(client.resource_groups.list())
        print(f"  Subscription: {azure['azure_subscription_id']}")
        print(f"  Resource groups: {len(rgs)} accessible")
        print("  [OK] Azure credentials valid")
    except ImportError:
        print("  [SKIP] Azure SDK not installed")
    except Exception as e:
        print(f"  [FAIL] Azure: {e}")
        all_ok = False
    
    # GCP
    print("\n[GCP] Validating...")
    try:
        from google.oauth2 import service_account
        from google.cloud import storage
        gcp = creds.get("gcp", {})
        creds_file = gcp.get("gcp_credentials_file", "gcp_credentials.json")
        creds_path = Path("/app/upload/template") / creds_file
        if not creds_path.exists():
            creds_path = Path("/app") / creds_file
        
        credentials = service_account.Credentials.from_service_account_file(str(creds_path))
        storage_client = storage.Client(project=gcp["gcp_project_id"], credentials=credentials)
        buckets = list(storage_client.list_buckets())
        print(f"  Project: {gcp['gcp_project_id']}")
        print(f"  Storage buckets: {len(buckets)} accessible")
        print("  [OK] GCP credentials valid")
    except ImportError:
        print("  [SKIP] GCP SDK not installed")
    except Exception as e:
        print(f"  [FAIL] GCP: {e}")
        all_ok = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("  ALL CREDENTIALS VALID - Ready for E2E test")
    else:
        print("  CREDENTIAL ISSUES DETECTED - Fix before running E2E")
    print("=" * 60)
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    exit(main())
