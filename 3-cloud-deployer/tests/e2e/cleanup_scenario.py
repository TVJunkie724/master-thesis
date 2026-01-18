"""
Cleanup a single scenario - works even when Terraform state is lost.

This script uses SDK calls to delete all resources matching the scenario prefix.
No Terraform state required.

Usage:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
        python tests/e2e/cleanup_scenario.py sc-aws-azure

    # Dry run (show what would be deleted):
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
        python tests/e2e/cleanup_scenario.py sc-aws-azure --dry-run
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# CRITICAL: Remove tests/e2e from sys.path to prevent the local 'azure' folder
# from shadowing the azure Python package
import os
sys.path = [p for p in sys.path if 'tests/e2e' not in p and 'tests\\e2e' not in p]

# Add src to path
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/src')


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
    if len(sys.argv) < 2:
        print("Usage: python cleanup_scenario.py <prefix> [--dry-run]")
        print()
        print("Examples:")
        print("  python cleanup_scenario.py sc-aws-azure")
        print("  python cleanup_scenario.py sc-gcp-aws --dry-run")
        print()
        print("Common prefixes:")
        print("  sc-aws-azure, sc-aws-gcp, sc-azure-aws,")
        print("  sc-azure-gcp, sc-gcp-aws, sc-gcp-azure")
        sys.exit(1)
    
    prefix = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    
    start_time = datetime.now()
    
    print("=" * 70)
    print(f"  SCENARIO CLEANUP: {prefix}")
    print("=" * 70)
    print(f"Started: {start_time.isoformat()}")
    print(f"Dry run: {dry_run}")
    print()
    
    creds = load_credentials()
    
    # Track cleanup results
    results = {"aws": None, "azure": None, "gcp": None}
    
    # AWS Cleanup
    print("-" * 70)
    print("[AWS] Starting cleanup...")
    print("-" * 70)
    try:
        from src.providers.aws.cleanup import cleanup_aws_resources
        cleanup_aws_resources(
            creds, prefix,
            cleanup_identity_user=False,
            platform_user_email="",
            dry_run=dry_run
        )
        results["aws"] = "✓ Complete"
    except ImportError as e:
        results["aws"] = f"✗ Import Error: {e}"
        print(f"[AWS] Import Error: {e}")
    except Exception as e:
        results["aws"] = f"✗ Error: {e}"
        print(f"[AWS] Error: {e}")
    
    print()
    
    # Azure Cleanup
    print("-" * 70)
    print("[Azure] Starting cleanup...")
    print("-" * 70)
    try:
        # Pre-import azure.identity to ensure it's available
        import azure.identity
        from src.providers.azure.cleanup import cleanup_azure_resources
        cleanup_azure_resources(
            creds, prefix,
            cleanup_entra_user=False,
            platform_user_email="",
            dry_run=dry_run
        )
        results["azure"] = "✓ Complete"
    except ImportError as e:
        import traceback
        results["azure"] = f"✗ Import Error: {e}"
        print(f"[Azure] Import Error: {e}")
        traceback.print_exc()
    except Exception as e:
        import traceback
        results["azure"] = f"✗ Error: {e}"
        print(f"[Azure] Error: {e}")
        traceback.print_exc()
    
    print()
    
    # GCP Cleanup
    print("-" * 70)
    print("[GCP] Starting cleanup...")
    print("-" * 70)
    try:
        from src.providers.gcp.cleanup import cleanup_gcp_resources
        cleanup_gcp_resources(creds, prefix, dry_run=dry_run)
        results["gcp"] = "✓ Complete"
    except ImportError as e:
        results["gcp"] = f"✗ Import Error: {e}"
        print(f"[GCP] Import Error: {e}")
    except Exception as e:
        results["gcp"] = f"✗ Error: {e}"
        print(f"[GCP] Error: {e}")
    
    print()
    
    # Clean up local state files
    print("-" * 70)
    print("[Local] Cleaning up state files...")
    print("-" * 70)
    state_dir = Path(f"/app/tests/e2e/multicloud/e2e_state/{prefix}")
    if state_dir.exists():
        if dry_run:
            print(f"  [DRY RUN] Would remove: {state_dir}")
        else:
            import shutil
            try:
                shutil.rmtree(state_dir)
                print(f"  ✓ Removed: {state_dir}")
            except Exception as e:
                print(f"  ✗ Error: {e}")
    else:
        print(f"  ✓ No state directory found (already clean)")
    
    print()
    
    # Summary
    duration = datetime.now() - start_time
    duration_str = str(duration).split('.')[0]
    
    print("=" * 70)
    print(f"  CLEANUP SUMMARY: {prefix}")
    print("=" * 70)
    print(f"Duration: {duration_str}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()
    print("Results:")
    for provider, status in results.items():
        print(f"  [{provider.upper()}] {status}")
    print()
    
    # Exit with error if any provider failed
    has_errors = any("✗" in str(s) for s in results.values() if s)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
