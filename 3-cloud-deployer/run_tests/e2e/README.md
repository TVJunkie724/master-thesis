# E2E Test Run Scripts

This folder contains scripts for running E2E (end-to-end) tests.

## ⚠️ Important

E2E tests deploy **REAL cloud resources** and incur costs. Make sure you have:
1. Valid credentials in `upload/template/config_credentials.json`
2. Docker container running (`docker-compose up -d`)

## Scripts

| Script | Description | Cost | Time |
|--------|-------------|------|------|
| `run_azure_full` | Full Azure single-cloud deployment | ~$0.50-2.00 | ~30 min |
| `run_azure_failure_cleanup` | Tests cleanup on deployment failure | ~$0.01 | ~1 min |
| `run_azure_all` | Runs all Azure E2E tests | Varies | Varies |

Both `.sh` (Linux/Mac) and `.bat` (Windows) versions are available.

## Usage

**Windows:**
```cmd
run_tests\e2e\run_azure_failure_cleanup.bat
```

**Linux/Mac:**
```bash
./run_tests/e2e/run_azure_failure_cleanup.sh
```

## Adding New Failure Scenarios

To add new failure scenarios, create test methods in:
`tests/e2e/azure/test_azure_failure_cleanup_e2e.py`

Then create corresponding run scripts if needed.

