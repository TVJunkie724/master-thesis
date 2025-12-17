# Azure Function ZIP Deploy E2E Test

This E2E test validates that the `function_bundler.py` produces valid ZIP files that can
be deployed to Azure Functions and have their functions discovered correctly.

## What It Tests

1. **ZIP Structure**: Verifies the bundler creates a ZIP with correct structure:
   - `function_app.py` (main file with Blueprint registrations)
   - `requirements.txt`
   - `host.json`
   - `_shared/` directory
   - Function submodules (e.g., `persister/function_app.py`)

2. **Azure Deployment**: Deploys the ZIP to a real Azure Function App

3. **Function Discovery**: Verifies Azure detects all functions in the ZIP

## Prerequisites

1. Azure credentials configured in `upload/template/config_credentials.json`
2. Dependencies: `azure-identity`, `azure-mgmt-resource`, `azure-mgmt-storage`, `azure-mgmt-web`

## Usage

### Run from Docker container (recommended)

```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
    python -m pytest /app/tests/e2e/zip_deploy_test -v -m live
```

### Run locally

```bash
cd 3-cloud-deployer
python -m pytest tests/e2e/zip_deploy_test -v -m live
```

## Working Configuration

The following settings are **required** for successful deployment:

### App Settings
| Setting | Value | Notes |
|---------|-------|-------|
| `FUNCTIONS_WORKER_RUNTIME` | `python` | Required |
| `FUNCTIONS_EXTENSION_VERSION` | `~4` | v2 programming model |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` | Enables remote build |
| `ENABLE_ORYX_BUILD` | `true` | **Critical for pip install** |
| `AzureWebJobsFeatureFlags` | `EnableWorkerIndexing` | Enables v2 function discovery |

### Storage Settings (Consumption Plan)
| Setting | Description |
|---------|-------------|
| `AzureWebJobsStorage` | Storage account connection string |
| `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING` | Same connection string |
| `WEBSITE_CONTENTSHARE` | File share name (function app name) |

### Do NOT Use
- `WEBSITE_RUN_FROM_PACKAGE=1` - Conflicts with remote build

### Deployment Method
- Use async zip deploy: `/api/zipdeploy?isAsync=true`
- Wait ~180s for Oryx build to complete
- Enable SCM Basic Auth before deploying

## Estimated Duration & Cost

- **Duration**: 5-7 minutes
- **Cost**: ~$0.10 USD (resources are cleaned up automatically)

## Cleanup

Resources are automatically deleted after the test completes (even on failure).

If cleanup fails, manually delete the resource group `zipdeploy-e2e-rg` in the Azure Portal.

## Troubleshooting

1. **401 on zip deploy**: SCM Basic Auth not enabled - call `update_scm_allowed(allow=True)`

2. **Functions not discovered after 60s**: Oryx build takes ~180s - wait longer

3. **Missing packages at runtime**: Ensure `ENABLE_ORYX_BUILD=true` is set

4. **Zip structure wrong**: `function_app.py`, `host.json`, `requirements.txt` must be at ROOT
