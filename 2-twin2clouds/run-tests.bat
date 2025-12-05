@echo off
REM Test Runner Script for Twin2Clouds
REM Runs pytest inside the Docker container

echo ==========================================
echo  Twin2Clouds Test Runner
echo ==========================================
echo.

REM Check if Docker container is running
docker ps | findstr master-thesis-2twin2clouds-1 >nul 2>&1
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
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest /app/tests/ -v

echo.
echo ==========================================
echo  Tests Complete!
echo ==========================================
pause
