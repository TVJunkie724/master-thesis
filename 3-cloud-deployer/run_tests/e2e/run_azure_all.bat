@echo off
REM =============================================================================
REM Run ALL Azure E2E Tests
REM =============================================================================
REM Usage: run_azure_all.bat
REM
REM This script runs ALL Azure E2E tests:
REM   1. Failure Cleanup Test (quick, ~1 min)
REM   2. Full Single-Cloud Test (long, ~30 min)
REM
REM REQUIREMENTS:
REM   - Valid Azure credentials in upload/template/config_credentials.json
REM   - Docker container running
REM
REM WARNING: This will deploy REAL Azure resources!
REM =============================================================================

echo ========================================
echo   Azure E2E Tests - ALL
echo ========================================
echo.

docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/e2e/azure/ -v -m live -s --tb=long

echo.
echo ========================================
echo   All Azure E2E Tests Complete
echo ========================================
pause
