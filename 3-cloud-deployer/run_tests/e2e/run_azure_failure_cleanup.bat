@echo off
REM =============================================================================
REM Run E2E Tests - Azure Failure Cleanup (Invalid IoT Hub Region)
REM =============================================================================
REM Usage: run_azure_failure_cleanup.bat
REM
REM This script tests the cleanup/destroy functionality by intentionally
REM triggering a deployment failure:
REM   1. Deploys Setup Layer (succeeds)
REM   2. Attempts L1 deployment with invalid IoT Hub region (fails)
REM   3. Runs cleanup to destroy all resources
REM   4. Verifies all resources are destroyed
REM
REM REQUIREMENTS:
REM   - Valid Azure credentials in upload/template/config_credentials.json
REM   - Docker container running
REM
REM INFO: This test deploys only Setup Layer resources (~$0.01, ~1 minute)
REM =============================================================================

echo ========================================
echo   Azure E2E Test - Failure Cleanup
echo ========================================
echo.
echo This test verifies cleanup works when deployment fails.
echo    - Uses invalid IoT Hub region to trigger failure
echo    - Estimated cost: ~$0.01 USD
echo    - Estimated time: ~1 minute
echo.

docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/e2e/azure/test_azure_failure_cleanup_e2e.py -v -m live -s --tb=long

echo.
echo ========================================
echo   Azure Failure Cleanup Test Complete
echo ========================================
pause
