@echo off
REM =============================================================================
REM Run E2E Tests - Azure Single Cloud (Full Deployment)
REM =============================================================================
REM Usage: run_azure_full.bat
REM
REM This script runs the Azure single-cloud E2E test which deploys:
REM   - Setup Layer (Resource Group, Managed Identity, Storage)
REM   - L1 (IoT Hub, Dispatcher)
REM   - L2 (Persister, Processors)
REM   - L3 Hot (Cosmos DB, Hot Reader)
REM   - L4 (Azure Digital Twins)
REM   - L5 (Grafana)
REM
REM REQUIREMENTS:
REM   - Valid Azure credentials in upload/template/config_credentials.json
REM   - Docker container running
REM
REM WARNING: This test deploys REAL Azure resources and incurs costs.
REM          Estimated: $0.50-2.00 USD, 20-40 minutes
REM =============================================================================

echo ========================================
echo   Azure E2E Test - Single Cloud
echo ========================================
echo.
echo WARNING: This test deploys REAL Azure resources!
echo    Estimated cost: $0.50-2.00 USD
echo    Estimated time: 20-40 minutes
echo.
echo Press Ctrl+C to cancel, or any key to continue...
pause >nul
echo.

docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/e2e/azure/test_azure_single_cloud_e2e.py -v -m live -s --tb=long

echo.
echo ========================================
echo   Azure E2E Test Complete
echo ========================================
pause
