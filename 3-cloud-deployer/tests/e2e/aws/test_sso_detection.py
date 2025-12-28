"""
AWS SSO Detection Test

Quick Python SDK test to verify IAM Identity Center (SSO) is detectable
in the specified region. Run this BEFORE the full Terraform E2E test
to validate your aws_sso_region configuration.

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/aws/test_sso_detection.py

    # Or with explicit region:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \\
        python tests/e2e/aws/test_sso_detection.py --sso-region us-east-1
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional


def load_credentials(project_path: Optional[str] = None) -> dict:
    """Load AWS credentials from config_credentials.json."""
    if project_path:
        creds_path = Path(project_path) / "config_credentials.json"
    else:
        # Try common locations
        possible_paths = [
            Path("/app/upload/template/config_credentials.json"),
            Path("/app/config_credentials.json"),
            Path("config_credentials.json"),
        ]
        creds_path = None
        for p in possible_paths:
            if p.exists():
                creds_path = p
                break
        
        if not creds_path:
            raise FileNotFoundError(
                "config_credentials.json not found. "
                "Provide --project-path or ensure file exists."
            )
    
    with open(creds_path) as f:
        creds = json.load(f)
    
    aws = creds.get("aws", {})
    return {
        "access_key_id": aws.get("aws_access_key_id"),
        "secret_access_key": aws.get("aws_secret_access_key"),
        "region": aws.get("aws_region", "eu-central-1"),
        "sso_region": aws.get("aws_sso_region", ""),
    }


def test_sso_detection(
    access_key_id: str,
    secret_access_key: str,
    sso_region: str,
) -> dict:
    """
    Test if IAM Identity Center (SSO) is detectable in the specified region.
    
    Returns:
        Dict with:
        - sso_available: bool
        - identity_store_id: str or None
        - instance_arn: str or None
        - error: str or None
    """
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        return {
            "sso_available": False,
            "identity_store_id": None,
            "instance_arn": None,
            "error": "boto3 not installed. Run: pip install boto3",
        }
    
    result = {
        "sso_available": False,
        "identity_store_id": None,
        "instance_arn": None,
        "error": None,
    }
    
    try:
        # Create SSO Admin client for the specified region
        sso_admin = boto3.client(
            'sso-admin',
            region_name=sso_region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        
        # List SSO instances
        response = sso_admin.list_instances()
        instances = response.get('Instances', [])
        
        if instances:
            instance = instances[0]
            result["sso_available"] = True
            result["identity_store_id"] = instance.get("IdentityStoreId")
            result["instance_arn"] = instance.get("InstanceArn")
        else:
            result["error"] = (
                f"No IAM Identity Center instance found in region '{sso_region}'. "
                f"Either SSO is not enabled, or it's in a different region."
            )
    
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDeniedException":
            result["error"] = (
                f"Access denied to sso-admin:ListInstances in region '{sso_region}'. "
                "Check IAM permissions."
            )
        else:
            result["error"] = f"AWS API error: {error_code} - {e.response['Error']['Message']}"
    
    except NoCredentialsError:
        result["error"] = "No AWS credentials provided."
    
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Test AWS IAM Identity Center (SSO) detection"
    )
    parser.add_argument(
        "--sso-region",
        help="AWS region to check for SSO (overrides config file)",
    )
    parser.add_argument(
        "--project-path",
        help="Path to project with config_credentials.json",
    )
    parser.add_argument(
        "--access-key",
        help="AWS Access Key ID (overrides config file)",
    )
    parser.add_argument(
        "--secret-key",
        help="AWS Secret Access Key (overrides config file)",
    )
    
    args = parser.parse_args()
    
    # Load credentials
    try:
        creds = load_credentials(args.project_path)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Override with CLI args if provided
    access_key = args.access_key or creds["access_key_id"]
    secret_key = args.secret_key or creds["secret_access_key"]
    sso_region = args.sso_region or creds["sso_region"] or creds["region"]
    
    if not access_key or not secret_key:
        print("❌ AWS credentials not configured. Check config_credentials.json")
        sys.exit(1)
    
    print(f"\n🔍 Testing SSO detection in region: {sso_region}")
    print("-" * 50)
    
    result = test_sso_detection(access_key, secret_key, sso_region)
    
    if result["sso_available"]:
        print(f"✅ SSO DETECTED in region '{sso_region}'")
        print(f"   Identity Store ID: {result['identity_store_id']}")
        print(f"   Instance ARN: {result['instance_arn']}")
        print("\n📋 Terraform will be able to create Grafana admin users!")
        sys.exit(0)
    else:
        print(f"❌ SSO NOT DETECTED in region '{sso_region}'")
        print(f"   Error: {result['error']}")
        print("\n⚠️  Recommendations:")
        print("   1. Check if IAM Identity Center is enabled")
        print("   2. Verify the SSO region is correct (aws_sso_region)")
        print("   3. Ensure IAM permissions include sso-admin:ListInstances")
        sys.exit(1)


if __name__ == "__main__":
    main()
