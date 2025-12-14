#!/bin/bash
# =============================================================================
# Run ALL Azure E2E Tests
# =============================================================================
# Usage: ./run_azure_all.sh
#
# This script runs ALL Azure E2E tests:
#   1. Failure Cleanup Test (quick, ~1 min)
#   2. Full Single-Cloud Test (long, ~30 min)
#
# REQUIREMENTS:
#   - Valid Azure credentials in upload/template/config_credentials.json
#   - Docker container running
#
# WARNING: This will deploy REAL Azure resources!
# =============================================================================

echo "========================================"
echo "  Azure E2E Tests - ALL"
echo "========================================"
echo ""

docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
    python -m pytest tests/e2e/azure/ \
    -v -m live -s --tb=long

echo ""
echo "========================================"
echo "  All Azure E2E Tests Complete"
echo "========================================"
