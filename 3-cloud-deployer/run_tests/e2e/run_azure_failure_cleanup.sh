#!/bin/bash
# =============================================================================
# Run E2E Tests - Azure Failure Cleanup (Invalid IoT Hub Region)
# =============================================================================
# Usage: ./run_azure_failure_cleanup.sh
#
# This script tests the cleanup/destroy functionality by intentionally
# triggering a deployment failure:
#   1. Deploys Setup Layer (succeeds)
#   2. Attempts L1 deployment with invalid IoT Hub region (fails)
#   3. Runs cleanup to destroy all resources
#   4. Verifies all resources are destroyed
#
# REQUIREMENTS:
#   - Valid Azure credentials in upload/template/config_credentials.json
#   - Docker container running
#
# INFO: This test deploys only Setup Layer resources (~$0.01, ~1 minute)
# =============================================================================

echo "========================================"
echo "  Azure E2E Test - Failure Cleanup"
echo "========================================"
echo ""
echo "This test verifies cleanup works when deployment fails."
echo "   - Uses invalid IoT Hub region to trigger failure"
echo "   - Estimated cost: ~\$0.01 USD"
echo "   - Estimated time: ~1 minute"
echo ""

docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
    python -m pytest tests/e2e/azure/test_azure_failure_cleanup_e2e.py \
    -v -m live -s --tb=long

echo ""
echo "========================================"
echo "  Azure Failure Cleanup Test Complete"
echo "========================================"
