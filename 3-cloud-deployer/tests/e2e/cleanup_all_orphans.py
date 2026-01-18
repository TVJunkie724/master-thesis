"""
Clean up orphaned TwinMaker workspaces and other resources.

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
        python tests/e2e/cleanup_all_orphans.py
"""
import json
import logging
import sys
from pathlib import Path

# Configure logging to output to stdout so we can see cleanup progress
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


# All known scenario prefixes that should be cleaned
PREFIXES = [
    "sc-aws-azure", "sc-aws-gcp", 
    "sc-azure-aws", "sc-azure-gcp",
    "sc-gcp-aws", "sc-gcp-azure",
    "mc-e2e", "tf-e2e",
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


def main():
    print("=" * 70)
    print("  CLEANUP ALL ORPHANED RESOURCES")
    print("=" * 70)
    
    creds = load_credentials()
    
    for prefix in PREFIXES:
        print()
        print(f"--- Cleaning: {prefix} ---")
        
        # AWS Cleanup
        print(f"  [AWS] Cleaning...")
        try:
            from src.providers.aws.cleanup import cleanup_aws_resources
            cleanup_aws_resources(
                creds, prefix, 
                cleanup_identity_user=False, 
                platform_user_email="", 
                dry_run=False
            )
            print(f"  [AWS] Done")
        except ImportError as e:
            print(f"  [AWS] Import Error: {e}")
            print(f"        Install missing package and retry")
        except Exception as e:
            print(f"  [AWS] Error: {e}")
        
        # Azure Cleanup
        print(f"  [Azure] Cleaning...")
        try:
            from src.providers.azure.cleanup import cleanup_azure_resources
            cleanup_azure_resources(
                creds, prefix, 
                cleanup_entra_user=False, 
                platform_user_email="", 
                dry_run=False
            )
            print(f"  [Azure] Done")
        except ImportError as e:
            print(f"  [Azure] Import Error: {e}")
            print(f"          Install missing package and retry")
        except Exception as e:
            print(f"  [Azure] Error: {e}")
        
        # GCP Cleanup
        print(f"  [GCP] Cleaning...")
        try:
            from src.providers.gcp.cleanup import cleanup_gcp_resources
            cleanup_gcp_resources(creds, prefix, dry_run=False)
            print(f"  [GCP] Done")
        except ImportError as e:
            print(f"  [GCP] Import Error: {e}")
            print(f"        Install missing package and retry")
        except Exception as e:
            print(f"  [GCP] Error: {e}")
    
    print()
    print("=" * 70)
    print("  CLEANUP COMPLETE")
    print("=" * 70)
    print()
    print("Run verify_all_scenarios.py to confirm all resources are deleted.")


if __name__ == "__main__":
    main()
