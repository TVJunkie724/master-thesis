#!/bin/bash
# Test Runner Script for Cloud Deployer
# Runs pytest inside the Docker container

echo "=========================================="
echo " Cloud Deployer Test Runner"
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

# E2E is excluded by pyproject.toml and the collection guard unless explicitly enabled.
python -m pytest -q -W error \
    && ruff check src rest_api.py app.py tests --exclude tests/e2e \
    && python -m bandit -q -r src \
    && python -m compileall -q src rest_api.py app.py \
    && python -m pip check

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
