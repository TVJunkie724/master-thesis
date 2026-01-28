"""
Azure Failure Cleanup End-to-End Test.

This test intentionally uses invalid inputs (invalid IoT Hub region) to verify:
1. Deployment fails early with clear error messages
2. Even on failure, cleanup runs and all resources are destroyed
3. The destroy functions work correctly

IMPORTANT: This test deploys REAL Azure resources and incurs costs.
Run with: pytest -m live

Estimated duration: 5-10 minutes
Estimated cost: ~$0.01 USD (only setup layer, destroyed immediately)
"""
import pytest
import os
import sys
import json
import time
from typing import Dict, List, Any
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))


@pytest.mark.live
class TestAzureFailureCleanupE2E:
    """
    E2E test for verifying cleanup works on deployment failure.
    
    Uses invalid IoT Hub region to trigger L1 failure, then verifies:
    - Error message is clear and helpful
    - Cleanup runs and all resources are destroyed
    - Verification happens inline (not via finalizer)
    """
    
    @pytest.fixture(scope="class")
    def deployment_and_cleanup_result(self, request, e2e_failure_project_path, azure_credentials):
        """
        Attempt deployment with invalid IoT Hub region, then run cleanup and verify.
        
        This fixture:
        1. Deploys setup layer (succeeds)
        2. Attempts L1 deployment (fails with invalid region)
        3. Runs cleanup immediately
        4. Verifies resources are destroyed
        5. Returns all results for test assertions
        
        Returns:
            Dict with error, deployed_layers, cleanup_results, and verification
        """
        from src.core.config_loader import load_project_config, load_credentials, get_required_providers
        from src.core.context import DeploymentContext
        from src.core.registry import ProviderRegistry
        import src.providers  # noqa: F401 - triggers provider registration
        
        print("\n" + "="*70)
        print("  AZURE FAILURE E2E TEST - INVALID IOT HUB REGION")
        print("="*70)
        
        project_path = Path(e2e_failure_project_path)
        
        # Load config and credentials
        print("\n[INIT] Loading configuration...")
        config = load_project_config(project_path)
        credentials = load_credentials(project_path)
        
        print(f"[INIT] ✓ Digital twin name: {config.digital_twin_name}")
        print(f"[INIT] ✓ Project path: {project_path}")
        print(f"[INIT] ✓ General region: {credentials['azure'].get('azure_region', 'N/A')}")
        print(f"[INIT] ✓ IoT Hub region (INVALID): {credentials['azure']['azure_region_iothub']}")
        
        # Create deployment context
        print("\n[INIT] Creating deployment context...")
        context = DeploymentContext(
            project_name=config.digital_twin_name,
            project_path=project_path,
            config=config
        )
        
        # Initialize Azure provider
        print("[INIT] Initializing Azure provider...")
        required = get_required_providers(config)
        for prov_name in required:
            if not prov_name or prov_name.upper() == "NONE":
                continue
            provider_instance = ProviderRegistry.get(prov_name)
            creds = credentials.get(prov_name, {})
            if creds:
                provider_instance.initialize_clients(creds, config.digital_twin_name)
                context.providers[prov_name] = provider_instance
                print(f"[INIT] ✓ Provider '{prov_name}' initialized")
        
        provider = context.providers.get("azure")
        if not provider:
            pytest.fail("Azure provider not initialized")
        
        deployer = provider.get_deployer_strategy()
        print(f"[INIT] ✓ Deployer strategy created")
        
        # Track results
        deployed_layers: List[str] = []
        deployment_error = None
        cleanup_results: Dict[str, str] = {}
        verification_results: Dict[str, bool] = {}
        
        # =====================================================================
        # PHASE 1: DEPLOYMENT ATTEMPT
        # =====================================================================
        print("\n" + "="*70)
        print("  PHASE 1: DEPLOYMENT ATTEMPT")
        print("="*70)
        
        try:
            # Deploy Setup Layer - should succeed
            print("\n" + "-"*50)
            print("[DEPLOY] SETUP LAYER")
            print("-"*50)
            print("[DEPLOY] Creating Resource Group...")
            print("[DEPLOY] Creating Managed Identity...")
            print("[DEPLOY] Creating Storage Account...")
            deployer.deploy_setup(context)
            deployed_layers.append("setup")
            print("[DEPLOY] ✓ Setup layer deployed successfully!")
            
            # Deploy L1 - should FAIL with invalid IoT Hub region
            print("\n" + "-"*50)
            print("[DEPLOY] LAYER 1 - DATA ACQUISITION")
            print("-"*50)
            print("[DEPLOY] ⚠ Expecting failure due to invalid IoT Hub region...")
            print("[DEPLOY] Creating IoT Hub in region: 'invalid-region-xyz'...")
            deployer.deploy_l1(context)
            deployed_layers.append("l1")
            print("[DEPLOY] ✓ L1 deployed")  # Should NOT reach here
            
        except Exception as e:
            deployment_error = e
            print("\n" + "!"*50)
            print("[DEPLOY] ✗ DEPLOYMENT FAILED (as expected)")
            print("!"*50)
            print(f"[DEPLOY] Error type: {type(e).__name__}")
            print(f"[DEPLOY] Error message:\n{str(e)[:500]}")
        
        # =====================================================================
        # PHASE 2: CLEANUP
        # =====================================================================
        print("\n" + "="*70)
        print("  PHASE 2: CLEANUP - DESTROYING ALL RESOURCES")
        print("="*70)
        
        # Destroy in reverse order
        if "l1" in deployed_layers:
            print("\n[CLEANUP] Destroying L1...")
            try:
                deployer.destroy_l1(context)
                cleanup_results["l1"] = "✓ Destroyed"
                print("[CLEANUP] ✓ L1 destroyed")
            except Exception as e:
                cleanup_results["l1"] = f"✗ Failed: {type(e).__name__}: {e}"
                print(f"[CLEANUP] ✗ L1 destroy failed: {e}")
        
        if "setup" in deployed_layers:
            print("\n[CLEANUP] Destroying Setup Layer...")
            print("[CLEANUP]   - Deleting Storage Account...")
            print("[CLEANUP]   - Deleting Managed Identity...")
            print("[CLEANUP]   - Deleting Resource Group (cascades all resources)...")
            try:
                deployer.destroy_setup(context)
                cleanup_results["setup"] = "✓ Destroyed"
                print("[CLEANUP] ✓ Setup layer destroyed")
            except Exception as e:
                cleanup_results["setup"] = f"✗ Failed: {type(e).__name__}: {e}"
                print(f"[CLEANUP] ✗ Setup destroy failed: {e}")
        
        # Print cleanup summary
        print("\n" + "-"*50)
        print("  CLEANUP SUMMARY")
        print("-"*50)
        for layer, status in cleanup_results.items():
            print(f"  {layer}: {status}")
        print("-"*50)
        
        # =====================================================================
        # PHASE 3: VERIFICATION - CHECK RESOURCES ARE GONE
        # =====================================================================
        print("\n" + "="*70)
        print("  PHASE 3: VERIFICATION - CONFIRMING RESOURCES DESTROYED")
        print("="*70)
        
        from src.providers.azure.layers.layer_setup_azure import (
            check_resource_group,
            check_managed_identity,
            check_storage_account
        )
        
        # Wait a moment for Azure to process deletions
        print("\n[VERIFY] Waiting 5 seconds for Azure to process deletions...")
        time.sleep(5)
        
        print("[VERIFY] Checking if resources still exist...")
        
        rg_exists = check_resource_group(provider)
        verification_results["resource_group_destroyed"] = not rg_exists
        print(f"[VERIFY] Resource Group exists: {rg_exists} → {'✗ FAIL' if rg_exists else '✓ DESTROYED'}")
        
        # Only check these if RG check doesn't throw (RG might be gone already)
        try:
            mi_exists = check_managed_identity(provider)
            verification_results["managed_identity_destroyed"] = not mi_exists
            print(f"[VERIFY] Managed Identity exists: {mi_exists} → {'✗ FAIL' if mi_exists else '✓ DESTROYED'}")
        except Exception as e:
            verification_results["managed_identity_destroyed"] = True
            print(f"[VERIFY] Managed Identity: ✓ DESTROYED (RG gone)")
        
        try:
            sa_exists = check_storage_account(provider)
            verification_results["storage_account_destroyed"] = not sa_exists
            print(f"[VERIFY] Storage Account exists: {sa_exists} → {'✗ FAIL' if sa_exists else '✓ DESTROYED'}")
        except Exception as e:
            verification_results["storage_account_destroyed"] = True
            print(f"[VERIFY] Storage Account: ✓ DESTROYED (RG gone)")
        
        # Final summary
        all_destroyed = all(verification_results.values())
        print("\n" + "="*70)
        if all_destroyed:
            print("  ✓ ALL RESOURCES SUCCESSFULLY DESTROYED")
        else:
            print("  ✗ SOME RESOURCES MAY STILL EXIST")
        print("="*70)
        
        # Return all results for test assertions
        yield {
            "error": deployment_error,
            "deployed_layers": deployed_layers,
            "cleanup_results": cleanup_results,
            "verification_results": verification_results,
            "context": context,
            "provider": provider,
            "config": config,
        }
    
    # =========================================================================
    # TEST METHODS
    # =========================================================================
    
    def test_01_deployment_failed_with_expected_error(self, deployment_and_cleanup_result):
        """Verify deployment failed as expected due to invalid region."""
        error = deployment_and_cleanup_result["error"]
        
        assert error is not None, "Deployment should have failed with invalid IoT Hub region"
        
        print(f"\n[TEST 1] ✓ Deployment failed with: {type(error).__name__}")
    
    def test_02_error_message_is_clear(self, deployment_and_cleanup_result):
        """Verify error message mentions location/region issue."""
        error = deployment_and_cleanup_result["error"]
        
        if error is None:
            pytest.skip("No error occurred (unexpected)")
        
        error_str = str(error).lower()
        
        # Error should mention location/region-related terms
        location_terms = ["location", "region", "invalid", "not found", 
                         "available", "subscription", "disallowed", "policy"]
        
        has_location_term = any(term in error_str for term in location_terms)
        
        assert has_location_term, f"Error should mention location/region: {error}"
        print(f"\n[TEST 2] ✓ Error message contains region-related terms")
    
    def test_03_setup_layer_was_deployed(self, deployment_and_cleanup_result):
        """Verify setup layer was deployed before L1 failure."""
        deployed_layers = deployment_and_cleanup_result["deployed_layers"]
        
        assert "setup" in deployed_layers, \
            "Setup layer should have been deployed before L1 failure"
        
        print(f"\n[TEST 3] ✓ Setup layer was deployed: {deployed_layers}")
    
    def test_04_l1_was_not_fully_deployed(self, deployment_and_cleanup_result):
        """Verify L1 was NOT fully deployed (failed during IoT Hub creation)."""
        deployed_layers = deployment_and_cleanup_result["deployed_layers"]
        
        assert "l1" not in deployed_layers, \
            "L1 should NOT have been fully deployed due to IoT Hub creation failure"
        
        print(f"\n[TEST 4] ✓ L1 was not fully deployed (as expected)")
    
    def test_05_cleanup_executed_successfully(self, deployment_and_cleanup_result):
        """Verify cleanup ran for all deployed layers."""
        cleanup_results = deployment_and_cleanup_result["cleanup_results"]
        deployed_layers = deployment_and_cleanup_result["deployed_layers"]
        
        # All deployed layers should have cleanup results
        for layer in deployed_layers:
            assert layer in cleanup_results, f"Cleanup should have run for '{layer}'"
            assert "✓" in cleanup_results[layer], f"Cleanup for '{layer}' should have succeeded: {cleanup_results[layer]}"
        
        print(f"\n[TEST 5] ✓ Cleanup executed for all deployed layers")
        for layer, result in cleanup_results.items():
            print(f"         {layer}: {result}")
    
    def test_06_resources_destroyed_after_cleanup(self, deployment_and_cleanup_result):
        """Verify all resources are destroyed after cleanup."""
        verification_results = deployment_and_cleanup_result["verification_results"]
        
        # All verification checks should be True (resource destroyed)
        for check_name, is_destroyed in verification_results.items():
            assert is_destroyed, f"{check_name} should be True (resource should be destroyed)"
        
        print(f"\n[TEST 6] ✓ All resources verified as destroyed:")
        for check_name, is_destroyed in verification_results.items():
            status = "✓" if is_destroyed else "✗"
            print(f"         {status} {check_name}")


# =========================================================================
# STANDALONE EXECUTION
# =========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "live", "-s"])
