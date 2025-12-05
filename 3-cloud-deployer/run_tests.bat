@echo off
REM Test Runner Script for Cloud Deployer
REM Runs pytest inside the Docker container

echo ==========================================
echo  Cloud Deployer Test Runner
echo ==========================================
echo.

REM Check if Docker container is running
docker ps | findstr master-thesis-3cloud-deployer-1 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker container is not running!
    echo Please start the container first:
    echo    docker-compose up -d
    echo.
    pause
    exit /b 1
)

echo [INFO] Running tests in Docker container...
echo.

REM Run pytest with verbose output
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest /app/tests/ -v

echo.
echo ==========================================
echo  Tests Complete!
echo ==========================================
pause
