@echo off
REM ===========================================
REM Azure E2E Test Runner
REM ===========================================

echo ==========================================
echo    AZURE E2E TEST - WARNING
echo ==========================================
echo.
echo This test will:
echo   * Deploy REAL Azure resources
echo   * Estimated duration: 20-40 minutes
echo   * Estimated cost: ~$0.50-2.00 USD
echo.
echo Resources deployed:
echo   * Resource Group, Managed Identity, Storage Account
echo   * IoT Hub (S1 tier)
echo   * Function Apps (Consumption plan)
echo   * Cosmos DB (Serverless)
echo   * Azure Digital Twins instance
echo   * Azure Managed Grafana workspace
echo.
echo All resources will be destroyed after the test.
echo If cleanup fails, you will be directed to Azure Portal
echo to manually remove any remaining resources.
echo.

set /p confirm="Do you want to proceed? (y/N): "

if /i not "%confirm%"=="y" (
    echo Test cancelled.
    exit /b 0
)

echo.
echo Starting E2E tests...
echo.

docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 ^
    python -m pytest tests/e2e/azure/ -v -m "live" --tb=short

set exit_code=%errorlevel%

echo.
echo ==========================================
if %exit_code%==0 (
    echo    E2E TEST COMPLETED SUCCESSFULLY
) else (
    echo    E2E TEST FAILED (exit code: %exit_code%)
)
echo ==========================================

exit /b %exit_code%
