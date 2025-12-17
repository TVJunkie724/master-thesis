# Azure Functions Python Blueprints Deployment Guide

This document outlines the requirements, structure, and configurations needed to successfully deploy Azure Functions with multiple Python functions using Blueprints via Terraform.

## Required Folder Structure (V2 Programming Model)

```
<project_root>/
├── function_app.py          # REQUIRED: Main entry point
├── blueprint_module1.py     # Blueprint files with @bp.* decorators
├── blueprint_module2.py
├── shared_code/             # Optional: Shared utilities
│   └── __init__.py          # REQUIRED if using shared_code folder
├── host.json                # REQUIRED: Global function app config
├── requirements.txt         # REQUIRED: Python dependencies
├── local.settings.json      # Local only, NOT deployed
└── .funcignore              # Optional: Files to exclude from deployment
```

## Code Requirements

### Blueprint File (e.g., `http_blueprint.py`)

```python
import azure.functions as func

bp = func.Blueprint()

@bp.route(route="my_route")
def my_function(req: func.HttpRequest) -> func.HttpResponse:
    # function logic
    return func.HttpResponse("OK")
```

### Main Entry Point (`function_app.py`)

```python
import azure.functions as func

# Import blueprints
from http_blueprint import bp as http_bp
from another_blueprint import bp as another_bp

app = func.FunctionApp()

# Register ALL blueprints
app.register_functions(http_bp)
app.register_functions(another_bp)
```

## Restrictions & Pitfalls

| Restriction | Description |
|------------|-------------|
| **`__init__.py` files** | Required in ANY subdirectory used as a Python package (e.g., `shared_code/`) |
| **Directory naming** | Do NOT name directories the same as Python built-in modules (e.g., `logging`, `json`) |
| **Import paths** | Use absolute imports; avoid deprecated `__app__` imports and top-level relative imports |
| **`host.json` location** | MUST be at the ZIP root for deployment to work |
| **`requirements.txt`** | List all external dependencies; Azure installs them during deployment |

## Terraform Configuration

### Essential App Settings for `azurerm_linux_function_app`

```hcl
resource "azurerm_linux_function_app" "example" {
  name                       = "your-function-app"
  resource_group_name        = azurerm_resource_group.example.name
  location                   = azurerm_resource_group.example.location
  service_plan_id            = azurerm_service_plan.example.id
  storage_account_name       = azurerm_storage_account.example.name
  storage_account_access_key = azurerm_storage_account.example.primary_access_key

  site_config {
    application_stack {
      python_version = "3.11"  # Supported: 3.7-3.13
    }
  }

  app_settings = {
    "FUNCTIONS_WORKER_RUNTIME" = "python"
    
    # Choose ONE deployment strategy:
    
    # OPTION A: Remote Build (recommended for Python)
    "ENABLE_ORYX_BUILD"             = "true"
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"
    
    # OPTION B: Run from pre-built ZIP package
    # "WEBSITE_RUN_FROM_PACKAGE" = "1"  # OR a SAS URL to blob storage
  }
}
```

## Deployment Strategy Options

| Strategy | App Settings | When to Use |
|----------|-------------|-------------|
| **Remote Build** | `ENABLE_ORYX_BUILD=true`, `SCM_DO_BUILD_DURING_DEPLOYMENT=true` | **Recommended** for Python on Linux. Azure installs dependencies from `requirements.txt`. |
| **Run from Package** | `WEBSITE_RUN_FROM_PACKAGE=1` or URL | Pre-built ZIP with all dependencies included. Faster cold start, read-only filesystem. |

> [!IMPORTANT]
> **Remote build and `WEBSITE_RUN_FROM_PACKAGE` are mutually exclusive!** If using remote build, do NOT set `WEBSITE_RUN_FROM_PACKAGE`.

## ZIP Package Requirements

When creating a deployment ZIP:

1. **`host.json` must be at the root** of the ZIP (not in a subfolder)
2. **`function_app.py` must be at the root**
3. **All blueprint files** must be at root or in properly structured packages with `__init__.py`
4. **Include `requirements.txt`** (Azure reads it during remote build)
5. **Exclude**: `.venv/`, `.vscode/`, `local.settings.json`, `tests/`

### Correct ZIP Structure

```
deployment.zip/
├── function_app.py          ← Entry point at root
├── http_blueprint.py        ← Blueprint at root
├── shared_code/
│   ├── __init__.py          ← Required!
│   └── helpers.py
├── host.json                ← Required at root!
└── requirements.txt
```

## Module-Level Environment Variable Checking

When using environment variables in Azure Functions, be aware of the implications of checking them at module level (import time) vs inside function handlers (runtime).

### The Problem with Module-Level Checks

```python
from _shared.env_utils import require_env

# This runs at IMPORT TIME - during function discovery
REMOTE_INGESTION_URL = require_env("REMOTE_INGESTION_URL")  # Throws here if missing!
```

If an environment variable is missing when the module is imported:
1. The module import **fails immediately**
2. The **function worker cannot load your code**
3. Azure **fails to discover any functions** in that file
4. The function app may show **0 functions discovered** in the portal

### When This Pattern Works Fine

- Environment variables are **always set before deployment** (via Terraform `app_settings`)
- You're intentionally enforcing fail-fast for missing configuration

### When This Causes Issues

| Scenario | Result |
|----------|--------|
| Env vars not yet set when function app provisions | Functions never discovered |
| Deployment race condition (code deploys before app settings applied) | Import error, 0 functions |
| Local testing without `.env` configured | Module import crash |

### Solution: Lazy Initialization (Recommended)

Lazy loading solves the import-time failure problem while preserving fail-fast behavior at runtime:

```python
_REMOTE_INGESTION_URL = None

def get_remote_ingestion_url() -> str:
    global _REMOTE_INGESTION_URL
    if _REMOTE_INGESTION_URL is None:
        _REMOTE_INGESTION_URL = require_env("REMOTE_INGESTION_URL")
    return _REMOTE_INGESTION_URL
```

**Benefits of lazy loading:**
- ✅ **Function discovery works** - Module imports successfully, Azure sees your functions
- ✅ **Still fails fast** - Error occurs at first invocation, not silently ignored
- ✅ **Caches the value** - Only reads env var once, reuses for warm invocations
- ✅ **Clear error messages** - Same `EnvironmentError` if env var is missing

### Alternative Approaches

**Option 1: Check Inside Function Handler**
```python
@bp.event_grid_trigger(...)
def my_function(event):
    url = require_env("REMOTE_INGESTION_URL")  # Fail at runtime, not import
    # ...
```

**Option 2: Keep Module-Level (Only if deployment order is guaranteed)**

Module-level checks are valid **if you ensure** Terraform sets app settings before deployment completes.

> [!WARNING]
> If using module-level checks, ensure your Terraform deployment order is correct: app settings must be configured **before or during** function code deployment.

## Troubleshooting Checklist

| Issue | Solution |
|-------|----------|
| **Functions not discovered** | Ensure `app.register_functions(bp)` is called for each blueprint in `function_app.py` |
| **Import errors** | Add `__init__.py` to all package directories; use absolute imports |
| **Module not found** | Verify dependency is in `requirements.txt`; check Python version matches |
| **Deployment fails** | Ensure `host.json` is at ZIP root; check app settings are correct |
| **Functions work locally but not in Azure** | Dependencies may be OS-specific; use remote build instead of local build on Windows |

## Bundling Multiple Functions (Blueprint Pattern)

When bundling multiple functions into a single Function App ZIP using Blueprints, special care is needed for import paths.

### Expected Bundle Structure

```
deployment.zip/
├── function_app.py           ← Main entry point (auto-generated)
├── persister/
│   ├── __init__.py           ← Required!
│   └── function_app.py       ← Contains Blueprint (bp = func.Blueprint())
├── event_checker/
│   ├── __init__.py           ← Required!
│   └── function_app.py       ← Contains Blueprint
├── _shared/
│   ├── __init__.py           ← Required!
│   └── env_utils.py
├── host.json
└── requirements.txt
```

### Main `function_app.py` (Auto-Generated)

```python
import azure.functions as func

from persister.function_app import bp as persister_bp
from event_checker.function_app import bp as event_checker_bp

app = func.FunctionApp()
app.register_functions(persister_bp)
app.register_functions(event_checker_bp)
```

### Common Import Path Issues

> [!CAUTION]
> **DO NOT use `sys.path` manipulation in bundled submodules!** This causes import failures in Azure.

**Problem Code (in `persister/function_app.py`):**
```python
# ❌ THIS BREAKS BUNDLED FUNCTIONS
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _func_dir)  # WRONG PATH after bundling!
    from _shared.env_utils import require_env
```

**Correct Code:**
```python
# ✅ SIMPLE IMPORT - _shared is at ZIP root, Python finds it automatically
from _shared.env_utils import require_env
```

### Why Bundled Functions Fail to Discover

1. **`sys.path` manipulation** - Breaks when `__file__` path changes after bundling
2. **Missing `__init__.py`** - Each subfolder must be a Python package
3. **Import-time exceptions** - Any error during module import prevents function discovery
4. **Wrong folder structure** - `host.json` and main `function_app.py` must be at ZIP root

## Minimal `host.json` Configuration

```json
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true
      }
    }
  }
}
```

## Key Takeaways

1. **Use the V2 programming model** with `function_app.py` as the single entry point
2. **Register all blueprints** explicitly using `app.register_functions(blueprint)`
3. **Include `__init__.py`** in every directory used as a Python package
4. **Use remote build** (`ENABLE_ORYX_BUILD=true`) for Python on Linux—it handles dependencies better
5. **Keep `host.json` and `function_app.py` at the ZIP root**
6. **Do not mix** `WEBSITE_RUN_FROM_PACKAGE` with remote build settings

## References

- [Azure Functions Python Developer Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Terraform azurerm_linux_function_app](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/linux_function_app)
- [Azure Functions Deployment Technologies](https://learn.microsoft.com/en-us/azure/azure-functions/functions-deployment-technologies)
