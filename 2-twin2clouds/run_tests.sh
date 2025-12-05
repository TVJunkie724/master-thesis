#!/bin/bash
# Test Runner Script for Twin2Clouds
# Runs pytest inside the Docker container

echo "=========================================="
echo " Twin2Clouds Test Runner"
echo "=========================================="
echo ""

# Ensure we are in the right directory (optional safety check)
if [ ! -d "/app/tests" ]; then
    echo "[ERROR] tests directory not found!"
    echo "Make sure you are running this script inside the Docker container at /app"
    exit 1
fi

echo "[INFO] Setting up environment..."
export PYTHONPATH=/app

echo "[INFO] Running tests..."
echo ""

# Run pytest with verbose output
python -m pytest /app/tests/ -v

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo " Tests Complete! All passed."
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo " Tests Failed!"
    echo "=========================================="
    exit 1
fi
