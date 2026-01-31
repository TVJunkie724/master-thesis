"""
E2E Test Cleanup Script

Destroys all resources and removes state files for a specific E2E test.
Use this when E2E_SKIP_CLEANUP=true was used and you need to clean up manually.

Usage:
    python tests/e2e/cleanup_e2e_test.py aws
    python tests/e2e/cleanup_e2e_test.py deployer-gcp-aws
    python tests/e2e/cleanup_e2e_test.py azure --dry-run
    python tests/e2e/cleanup_e2e_test.py deployer-aws-azure --verify

Options:
    --dry-run    Show what would be deleted without actually deleting
    --force      Skip confirmation prompt (required for Docker/non-interactive)
    --verify     After cleanup, verify no orphaned resources remain
"""
import sys
import shutil
import time
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/src')


def main():
    if len(sys.argv) < 2:
        print("Usage: python cleanup_e2e_test.py <test> [--dry-run] [--force]")
        print("  Options:")
        print("    --dry-run  Show what would be deleted without deleting")
        print("    --force    Skip confirmation prompt")
        print()
        print("  Available tests:")
        for key in sorted(TEST_MAP.keys()):
            print(f"    - {key}")
        sys.exit(1)
    
    test_name = sys.argv[1].lower()
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    verify = "--verify" in sys.argv
    
    if test_name not in TEST_MAP:
        print(f"Unknown test: {test_name}")
        print(f"Available: {list(TEST_MAP.keys())}")
        sys.exit(1)
    
    project_name, state_base_dir = TEST_MAP[test_name]
    
    # Isolated tests use workspace directly (project_name is None)
    is_isolated_test = project_name is None
    if is_isolated_test:
        project_path = Path(state_base_dir)  # Workspace IS the project
        terraform_dir = project_path  # Terraform is in same folder
    else:
        project_path = Path(state_base_dir) / project_name
        terraform_dir = Path("/app/src/terraform")
    
    print(f"=" * 60)
    print(f"  E2E Cleanup - {test_name.upper()}")
    print(f"=" * 60)
    print(f"Project name: {project_name or '(isolated test)'}")
    print(f"Project path: {project_path}")
    print(f"Test type: {'isolated' if is_isolated_test else 'standard'}")
    print(f"Dry run: {dry_run}")
    print(f"Started: {datetime.now().isoformat()}")
    print()
    
    # Check if project exists
    if not project_path.exists():
        print(f"✓ Project path does not exist - nothing to clean up")
        print(f"  Path: {project_path}")
        sys.exit(0)
    
    # Confirmation prompt (unless --force or --dry-run)
    # NOTE: --force is required when running in Docker (non-interactive)
    if not force and not dry_run:
        try:
            print("⚠ WARNING: This will destroy all cloud resources and delete local state files!")
            response = input("Continue? [y/N]: ").strip().lower()
            if response != 'y':
                print("Aborted.")
                sys.exit(0)
        except EOFError:
            print("✗ Non-interactive mode detected. Use --force to skip confirmation.")
            sys.exit(1)
    
    # Step 1: Terraform destroy + SDK cleanup
    start_time = datetime.now()
    destroy_success = True
    
    if is_isolated_test:
        # Isolated tests: run terraform destroy directly in workspace
        print("\n[1/2] Running terraform destroy (isolated test)...")
        if dry_run:
            print("  [DRY RUN] Would run: terraform destroy")
        else:
            import subprocess
            tfvars_path = project_path / "test.tfvars.json"
            cmd = ["terraform", "destroy", "-auto-approve"]
            if tfvars_path.exists():
                cmd.extend([f"-var-file={tfvars_path}"])
            
            try:
                result = subprocess.run(
                    cmd, cwd=project_path, capture_output=True, text=True, timeout=600
                )
                print(result.stdout)
                if result.returncode == 0:
                    print("  ✓ Terraform destroy succeeded")
                else:
                    print(f"  ⚠ Terraform destroy had errors: {result.stderr}")
                    destroy_success = False
            except Exception as e:
                print(f"  ✗ Error during destroy: {e}")
                destroy_success = False
        
        # No SDK cleanup for isolated tests (they don't use SDK resources)
        strategy = None
        context = None
    else:
        # Standard tests: use TerraformDeployerStrategy
        try:
            from src.core.config_loader import load_project_config, load_credentials
            from src.core.context import DeploymentContext
            from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy
            
            config = load_project_config(project_path)
            credentials = load_credentials(project_path)
            
            strategy = TerraformDeployerStrategy(
                terraform_dir=str(terraform_dir),
                project_path=str(project_path)
            )
            
            context = DeploymentContext(
                project_name=config.digital_twin_name,
                project_path=project_path,
                config=config,
                credentials=credentials,
            )
            
        except Exception as e:
            print(f"✗ Error loading project config: {e}")
            print("  Falling back to state file cleanup only...")
            config = None
            context = None
            strategy = None
    
    if strategy and context:
        print("\n[1/2] Running terraform destroy + SDK cleanup...")
        if dry_run:
            print("  [DRY RUN] Would run: terraform destroy")
            print("  [DRY RUN] Would run: SDK fallback cleanup (AWS, Azure, GCP)")
        else:
            try:
                result = strategy.destroy_all(
                    context, 
                    sdk_fallback="always",  # Always run SDK cleanup
                    dry_run=dry_run
                )
                
                if result.terraform_success:
                    print("  ✓ Terraform destroy succeeded")
                    
                    # GCP Firestore cooldown: wait 5 minutes before allowing recreate
                    # This prevents "Database ID not available" errors on re-deploy
                    if test_name.startswith("deployer-"):
                        print("\n  Waiting 5 minutes for GCP Firestore cooldown...")
                        print("  (This prevents 'Database ID not available' errors on re-deploy)")
                        time.sleep(300)  # 5 minutes
                        print("  ✓ Cooldown complete")
                else:
                    print(f"  ⚠ Terraform destroy had errors: {result.terraform_error}")
                
                if result.sdk_fallback_ran:
                    print(f"  ✓ SDK fallback ran: {result.sdk_fallback_results}")
                    
            except Exception as e:
                print(f"  ✗ Error during destroy: {e}")
                destroy_success = False
    else:
        print("\n[1/2] Skipping terraform destroy (no valid config)")
        # Fallback: Run SDK cleanup directly when config loading failed
        print("  Running standalone SDK cleanup fallback...")
        try:
            from src.providers.azure.cleanup import cleanup_azure_resources
            import json
            creds_path = project_path / "config_credentials.json"
            if creds_path.exists():
                with open(creds_path) as f:
                    credentials = json.load(f)
                cleanup_azure_resources(credentials, test_name, dry_run=dry_run)
                print("  ✓ SDK cleanup complete")
            else:
                print(f"  ⚠ No credentials found at {creds_path}")
        except Exception as e:
            print(f"  ✗ SDK fallback error: {e}")
    
    # Step 2: Remove state files
    print("\n[2/2] Removing local state files...")
    terraform_state_dir = project_path / "terraform"
    
    if terraform_state_dir.exists():
        if dry_run:
            print(f"  [DRY RUN] Would remove: {terraform_state_dir}")
            for f in terraform_state_dir.iterdir():
                print(f"    - {f.name}")
        else:
            try:
                shutil.rmtree(terraform_state_dir)
                print(f"  ✓ Removed: {terraform_state_dir}")
            except Exception as e:
                print(f"  ✗ Error removing state files: {e}")
    else:
        print(f"  ✓ No state directory found (already clean)")
    
    # Calculate duration
    duration = datetime.now() - start_time
    duration_str = str(duration).split('.')[0]
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"  CLEANUP COMPLETE")
    print(f"{'=' * 60}")
    print(f"Duration: {duration_str}")
    print(f"Test: {test_name}")
    if dry_run:
        print(f"Mode: DRY RUN (no changes made)")
    else:
        print(f"Mode: LIVE (resources destroyed)")
    
    # Optional verification step
    verification_success = True
    if verify and not dry_run:
        print(f"\n{'=' * 60}")
        print(f"  POST-CLEANUP VERIFICATION")
        print(f"{'=' * 60}")
        try:
            from tests.e2e.verify_all_scenarios import check_aws, check_azure, check_gcp, load_credentials
            creds = load_credentials()
            
            print("\nChecking for remaining resources...")
            remaining = []
            
            # Check each provider
            aws_found = check_aws(creds)
            if aws_found:
                remaining.extend(aws_found)
            
            azure_found = check_azure(creds)
            if azure_found:
                remaining.extend(azure_found)
            
            gcp_found = check_gcp(creds)
            if gcp_found:
                remaining.extend(gcp_found)
            
            if remaining:
                print(f"\n⚠ VERIFICATION WARNING: {len(remaining)} resources still exist:")
                for category, name in remaining:
                    print(f"  [{category}] {name}")
                verification_success = False
            else:
                print("\n✓ VERIFICATION PASSED: No orphaned resources found")
        except ImportError as e:
            print(f"\n⚠ Verification skipped: {e}")
        except Exception as e:
            print(f"\n⚠ Verification error: {e}")
            verification_success = False
    
    # Exit with appropriate code
    sys.exit(0 if (destroy_success and verification_success) else 1)


# Map test names to (project_name, state_base_directory)
# Project names verified from conftest.py fixture definitions
# For isolated tests, project_name is the Terraform workspace folder name
TEST_MAP = {
    # Single cloud tests (project names from conftest.py)
    "aws": ("tf-e2e-aws", "/app/tests/e2e/aws/e2e_state"),
    "aws-twinmaker-full": ("tf-e2e-tm", "/app/tests/e2e/aws/e2e_state"),
    "azure": ("tf-e2e-az", "/app/tests/e2e/azure_tests/e2e_state"),
    "azure-adt-full": ("tf-e2e-adt", "/app/tests/e2e/azure_tests/e2e_state"),
    "gcp": ("tf-e2e-gcp", "/app/tests/e2e/gcp/e2e_state"),
    
    # Isolated component tests (use own Terraform workspaces, not e2e_state)
    # These tests store state directly in their workspace folder
    "aws-stepfunctions": (None, "/app/tests/e2e/aws_stepfunctions_test"),
    "aws-grafana": (None, "/app/tests/e2e/aws_grafana_test"),
    "azure-logicapp-isolated": (None, "/app/tests/e2e/azure_logicapp_isolated_test"),
    "azure-grafana": (None, "/app/tests/e2e/azure_grafana_test"),
    
    # Multicloud tests
    "multicloud": ("mc-e2e-test", "/app/tests/e2e/multicloud/e2e_state"),
    
    # Deployer scenario tests (project names from _base_scenario.py ScenarioConfig)
    "deployer-gcp-azure": ("sc2-gcp-azure", "/app/tests/e2e/multicloud/e2e_state"),
    "deployer-gcp-aws": ("sc2-gcp-aws", "/app/tests/e2e/multicloud/e2e_state"),
    "deployer-aws-azure": ("sc2-aws-azure", "/app/tests/e2e/multicloud/e2e_state"),
    "deployer-aws-gcp": ("sc2-aws-gcp", "/app/tests/e2e/multicloud/e2e_state"),
    "deployer-azure-aws": ("sc2-azure-aws", "/app/tests/e2e/multicloud/e2e_state"),
    "deployer-azure-gcp": ("sc2-azure-gcp", "/app/tests/e2e/multicloud/e2e_state"),
}


if __name__ == "__main__":
    main()

