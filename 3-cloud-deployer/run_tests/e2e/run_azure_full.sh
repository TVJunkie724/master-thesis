#!/bin/bash
# =============================================================================
# Run E2E Tests - Azure Single Cloud (Full Deployment)
# =============================================================================
# Usage: ./run_e2e_azure.sh
#
# This script runs the Azure single-cloud E2E test which deploys:
#   - Setup Layer (Resource Group, Managed Identity, Storage)
#   - L1 (IoT Hub, Dispatcher)
#   - L2 (Persister, Processors)
#   - L3 Hot (Cosmos DB, Hot Reader)
#   - L4 (Azure Digital Twins)
#   - L5 (Grafana)
#
# REQUIREMENTS:
#   - Valid Azure credentials in upload/template/config_credentials.json
#   - Docker container running
#
# WARNING: This test deploys REAL Azure resources and incurs costs.
#          Estimated: $0.50-2.00 USD, 20-40 minutes
# =============================================================================

echo "========================================"
echo "  Azure E2E Test - Single Cloud"
echo "========================================"
echo ""
echo "⚠️  WARNING: This test deploys REAL Azure resources!"
echo "   Estimated cost: \$0.50-2.00 USD"
echo "   Estimated time: 20-40 minutes"
echo ""
echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
sleep 5
echo ""

docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
    python -m pytest tests/e2e/azure/test_azure_single_cloud_e2e.py \
    -v -m live -s --tb=long

echo ""
echo "========================================"
echo "  Azure E2E Test Complete"
echo "========================================"
