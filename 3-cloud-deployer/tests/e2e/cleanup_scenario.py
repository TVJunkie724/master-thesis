"""
Cleanup E2E test scenarios - works even when Terraform state is lost.

Runs AWS, Azure, and GCP cleanup in PARALLEL to speed up the process.
No Terraform state required.

Usage:
    # Clean a specific scenario:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
        python tests/e2e/cleanup_scenario.py sc2-azure-aws

    # Clean ALL known scenarios:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
        python tests/e2e/cleanup_scenario.py --all

    # Dry run (show what would be deleted):
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
        python tests/e2e/cleanup_scenario.py sc2-azure-aws --dry-run

    # Dry run for all:
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
        python tests/e2e/cleanup_scenario.py --all --dry-run
"""
import sys
import json
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
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
sys.path = [p for p in sys.path if 'tests/e2e' not in p and 'tests\\e2e' not in p]

# Add src to path
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/src')

# Pre-import cleanup modules to avoid ThreadPoolExecutor deadlock
# Python import locks can cause deadlock when multiple threads import simultaneously
from src.providers.aws.cleanup import cleanup_aws_resources as _aws_cleanup
from src.providers.azure.cleanup import cleanup_azure_resources as _azure_cleanup
from src.providers.gcp.cleanup import cleanup_gcp_resources as _gcp_cleanup

# All known scenario prefixes
ALL_PREFIXES = [
    "sc2-aws-azure", "sc2-aws-gcp", 
    "sc2-azure-aws", "sc2-azure-gcp",
    "sc2-gcp-aws", "sc2-gcp-azure",
    "mc-e2e", "tf-e2e",
]

# E2E state directory
E2E_STATE_DIR = Path("/app/tests/e2e/multicloud/e2e_state")


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


def cleanup_aws(creds: dict, prefix: str, dry_run: bool) -> str:
    """Clean up AWS resources for a prefix. Returns status message."""
    try:
        _aws_cleanup(
            creds, prefix,
            cleanup_identity_user=False,
            platform_user_email="",
            dry_run=dry_run
        )
        return "✓ Complete"
    except Exception as e:
        return f"✗ Error: {e}"


def cleanup_azure(creds: dict, prefix: str, dry_run: bool) -> str:
    """Clean up Azure resources for a prefix. Returns status message."""
    try:
        _azure_cleanup(
            creds, prefix,
            cleanup_entra_user=False,
            platform_user_email="",
            dry_run=dry_run
        )
        return "✓ Complete"
    except Exception as e:
        return f"✗ Error: {e}"


def cleanup_gcp(creds: dict, prefix: str, dry_run: bool) -> str:
    """Clean up GCP resources for a prefix. Returns status message."""
    try:
        _gcp_cleanup(creds, prefix, dry_run=dry_run)
        return "✓ Complete"
    except Exception as e:
        return f"✗ Error: {e}"


def cleanup_local_state(prefix: str, dry_run: bool) -> str:
    """Clean up local state files for a prefix. Returns status message."""
    state_dir = E2E_STATE_DIR / prefix
    if not state_dir.exists():
        return "✓ Already clean"
    
    if dry_run:
        return f"[DRY RUN] Would remove: {state_dir}"
    
    try:
        shutil.rmtree(state_dir)
        return f"✓ Removed: {state_dir}"
    except Exception as e:
        return f"✗ Error: {e}"


def cleanup_single_prefix(creds: dict, prefix: str, dry_run: bool) -> dict:
    """
    Clean up a single prefix with AWS, Azure, GCP running in parallel.
    Returns dict with results for each provider.
    """
    results = {}
    
    # Run cloud provider cleanups in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(cleanup_aws, creds, prefix, dry_run): "AWS",
            executor.submit(cleanup_azure, creds, prefix, dry_run): "Azure",
            executor.submit(cleanup_gcp, creds, prefix, dry_run): "GCP",
        }
        
        for future in as_completed(futures):
            provider = futures[future]
            try:
                results[provider] = future.result()
            except Exception as e:
                results[provider] = f"✗ Unexpected Error: {e}"
    
    # Clean up local state (after cloud cleanup)
    results["Local"] = cleanup_local_state(prefix, dry_run)
    
    return results


def print_usage():
    """Print usage information."""
    print("Usage: python cleanup_scenario.py <prefix|--all> [--dry-run]")
    print()
    print("Examples:")
    print("  python cleanup_scenario.py sc2-aws-azure")
    print("  python cleanup_scenario.py sc2-azure-aws --dry-run")
    print("  python cleanup_scenario.py --all")
    print("  python cleanup_scenario.py --all --dry-run")
    print()
    print("Available prefixes:")
    for prefix in ALL_PREFIXES:
        print(f"  {prefix}")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    # Parse arguments
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    clean_all = "--all" in args
    
    # Determine prefixes to clean
    if clean_all:
        prefixes = ALL_PREFIXES
    else:
        prefix = [a for a in args if not a.startswith("--")]
        if not prefix:
            print("Error: No prefix specified")
            print_usage()
            sys.exit(1)
        prefixes = [prefix[0]]
    
    start_time = datetime.now()
    
    print("=" * 70)
    if clean_all:
        print("  CLEANUP ALL SCENARIOS (PARALLEL)")
    else:
        print(f"  SCENARIO CLEANUP: {prefixes[0]} (PARALLEL)")
    print("=" * 70)
    print(f"Started: {start_time.isoformat()}")
    print(f"Dry run: {dry_run}")
    print(f"Prefixes: {len(prefixes)}")
    print()
    
    creds = load_credentials()
    all_results = {}
    
    for prefix in prefixes:
        print("-" * 70)
        print(f"[{prefix}] Starting parallel cleanup (AWS/Azure/GCP)...")
        print("-" * 70)
        
        results = cleanup_single_prefix(creds, prefix, dry_run)
        all_results[prefix] = results
        
        for provider, status in sorted(results.items()):
            print(f"  [{provider}] {status}")
        print()
    
    # Summary
    duration = datetime.now() - start_time
    duration_str = str(duration).split('.')[0]
    
    print("=" * 70)
    print("  CLEANUP SUMMARY")
    print("=" * 70)
    print(f"Duration: {duration_str}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()
    
    print("Results:")
    for prefix, results in all_results.items():
        has_errors = any("✗" in str(s) for s in results.values())
        status = "❌ ERRORS" if has_errors else "✅ OK"
        print(f"  {prefix}: {status}")
    
    print()
    
    # Exit with error if any provider failed
    total_errors = sum(
        1 for results in all_results.values() 
        for s in results.values() if "✗" in str(s)
    )
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
