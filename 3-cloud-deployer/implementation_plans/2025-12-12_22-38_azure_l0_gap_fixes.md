# Azure L0 Gap Fixes

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Complete Gap Analysis](#2-complete-gap-analysis)
3. [Proposed Changes](#3-proposed-changes)
4. [Implementation Phases](#4-implementation-phases)
5. [Verification Checklist](#5-verification-checklist)

---

## 1. Executive Summary

### The Problem
Meticulous analysis of Azure Setup Layer + L0 reveals **15 issues** across 4 files:
- 3 critical bugs (will cause deployment failure)
- 6 silent fallbacks/errors
- 6 empty/incomplete implementations

### The Solution
Fix all issues to achieve full functional parity with AWS. Consumption plan (Y1 SKU) confirmed via cost optimizer.

### Impact
- Azure deployments will actually work
- No silent failures or misconfigurations
- Full multi-cloud interoperability

---

## 2. Complete Gap Analysis

### 2.1 CRITICAL BUGS (Will Cause Deployment Failure)

| # | File | Line | Issue | Fix |
|---|------|------|-------|-----|
| C1 | `layer_0_glue.py` | 103 | `serverFarmId: None` - Azure SDK **REQUIRES** App Service Plan ID | Create Y1 consumption plan first |
| C2 | `layer_0_glue.py` | 108-113 | Silent fallback to SystemAssigned identity | Fail-fast if identity_id is None |
| C3 | `layer_setup_azure.py` | 238 | `except Exception: return None` catches ALL errors | Only catch `ResourceNotFoundError` |

### 2.2 SILENT FALLBACKS (No Error But Wrong Behavior)

| # | File | Line | Issue | Fix |
|---|------|------|-------|-----|
| S1 | `layer_setup_azure.py` | 35 | Default `location="westeurope"` param | Use `provider.location`, remove default |
| S2 | `layer_0_glue.py` | 587 | `if current.properties else {}` silently creates empty dict | Raise if None |
| S3 | `l_setup_adapter.py` | 64 | `getattr(provider, 'location', 'westeurope')` fallback | Remove fallback, provider always has location |

### 2.3 STRING-BASED EXCEPTION HANDLING (Fragile)

| # | File | Line | Pattern | Fix |
|---|------|------|---------|-----|
| E1 | `layer_setup_azure.py` | 89 | `if "ResourceGroupNotFound" in str(e)` | Use `ResourceNotFoundError` exception |
| E2 | `layer_setup_azure.py` | 112 | Same pattern | Same fix |
| E3 | `layer_setup_azure.py` | 184 | Same pattern | Same fix |
| E4 | `layer_setup_azure.py` | 211 | Same pattern | Same fix |
| E5 | `layer_setup_azure.py` | 310 | Same pattern | Same fix |
| E6 | `layer_setup_azure.py` | 337 | Same pattern | Same fix |
| E7 | `layer_0_glue.py` | 189 | Same pattern | Same fix |
| E8 | `layer_0_glue.py` | 216 | Same pattern | Same fix |

### 2.4 EMPTY/INCOMPLETE IMPLEMENTATIONS

| # | File | Line | Issue | Fix |
|---|------|------|-------|-----|
| I1 | `layer_0_glue.py` | 273 | `destroy_ingestion_function()` is `pass` | Remove app settings |
| I2 | `layer_0_glue.py` | 334 | `destroy_hot_writer_function()` is `pass` | Remove app settings |
| I3 | `layer_0_glue.py` | 394 | `destroy_cold_writer_function()` is `pass` | Remove app settings |
| I4 | `layer_0_glue.py` | 454 | `destroy_archive_writer_function()` is `pass` | Remove app settings |
| I5 | `layer_0_glue.py` | 531 | `destroy_hot_reader_endpoint()` is `pass` | Remove app settings |
| I6 | `layer_0_glue.py` | 537 | `destroy_hot_reader_last_entry_endpoint()` is `pass` | Remove app settings |

### 2.5 MISSING IMPLEMENTATIONS

| # | Component | Description | Required For |
|---|-----------|-------------|--------------|
| M1 | App Service Plan | Y1 Consumption plan creation | Function App to work |
| M2 | Function deployment | ZIP upload of function code | Functions to execute |
| M3 | `naming.glue_app_service_plan()` | Naming method for plan | M1 |

---

## 3. Proposed Changes

### Component: `layer_setup_azure.py`

#### [MODIFY] Fix exception handling + remove default location
```python
# Line 22: Add import
from azure.core.exceptions import ResourceNotFoundError

# Line 35: Remove default
def create_resource_group(provider: 'AzureProvider') -> str:
    location = provider.location  # Use provider's location

# Lines 89, 112, 184, 211, 310, 337: Replace string check
except ResourceNotFoundError:
    logger.info(f"Resource not found...")

# Line 238: Fix catch-all
except ResourceNotFoundError:
    return None
```

---

### Component: `layer_0_glue.py`

#### [MODIFY] Fix identity fallback + add App Service Plan
```python
# Line 88-113: Fail-fast for missing identity
identity_id = get_managed_identity_id(provider)
if not identity_id:
    raise ValueError(
        "Managed Identity not found. Run Setup Layer first (deploy_setup)."
    )

# NEW: Add before create_glue_function_app()
def create_consumption_app_service_plan(provider: 'AzureProvider') -> str:
    """Create Y1 Consumption App Service Plan for serverless functions."""
    rg_name = provider.naming.resource_group()
    plan_name = provider.naming.glue_app_service_plan()
    location = provider.location
    
    poller = provider.clients["web"].app_service_plans.begin_create_or_update(
        resource_group_name=rg_name,
        name=plan_name,
        app_service_plan={
            "location": location,
            "kind": "functionapp",
            "sku": {"name": "Y1", "tier": "Dynamic"},
            "properties": {"reserved": True}  # Linux
        }
    )
    poller.result()
    return f"/subscriptions/{provider.subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.Web/serverfarms/{plan_name}"

# Line 103: Use actual plan ID
"serverFarmId": create_consumption_app_service_plan(provider),
```

#### [MODIFY] Implement destroy functions
```python
def destroy_ingestion_function(provider: 'AzureProvider') -> None:
    """Remove Ingestion function settings."""
    _remove_function_app_setting(provider, "INTER_CLOUD_TOKEN")
    logger.info("✓ Ingestion function configuration removed")

# Add helper
def _remove_function_app_setting(provider: 'AzureProvider', key: str) -> None:
    """Remove a single app setting."""
    rg_name = provider.naming.resource_group()
    app_name = provider.naming.glue_function_app()
    
    current = provider.clients["web"].web_apps.list_application_settings(
        resource_group_name=rg_name, name=app_name
    )
    settings = dict(current.properties) if current.properties else {}
    if key in settings:
        del settings[key]
        provider.clients["web"].web_apps.update_application_settings(
            resource_group_name=rg_name, name=app_name,
            app_settings={"properties": settings}
        )
```

---

### Component: `naming.py`

#### [MODIFY] Add App Service Plan naming
```python
def glue_app_service_plan(self) -> str:
    """App Service Plan name for L0 glue Function App."""
    return f"{self._twin_name}-l0-plan"
```

---

## 4. Implementation Phases

### Phase 1: Critical Bug Fixes
| Step | File | Action |
|------|------|--------|
| 1.1 | `naming.py` | Add `glue_app_service_plan()` method |
| 1.2 | `layer_0_glue.py` | Add `create_consumption_app_service_plan()` |
| 1.3 | `layer_0_glue.py` | Fix `serverFarmId` to use plan ID |
| 1.4 | `layer_0_glue.py` | Add fail-fast for missing identity_id |

### Phase 2: Exception Handling
| Step | File | Action |
|------|------|--------|
| 2.1 | `layer_setup_azure.py` | Add `ResourceNotFoundError` import |
| 2.2 | `layer_setup_azure.py` | Replace 7 string-based exception checks |
| 2.3 | `layer_0_glue.py` | Replace 2 string-based exception checks |

### Phase 3: Silent Fallbacks
| Step | File | Action |
|------|------|--------|
| 3.1 | `layer_setup_azure.py` | Remove default location param |
| 3.2 | `l_setup_adapter.py` | Remove getattr fallback |
| 3.3 | `layer_0_glue.py` | Add None check for app settings |

### Phase 4: Destroy Implementations
| Step | File | Action |
|------|------|--------|
| 4.1 | `layer_0_glue.py` | Add `_remove_function_app_setting()` helper |
| 4.2 | `layer_0_glue.py` | Implement 6 destroy functions |

### Phase 5: Test Updates
| Step | File | Action |
|------|------|--------|
| 5.1 | Tests | Update mocks for new behavior |
| 5.2 | All | Run full test suite |

---

## 5. Verification Checklist

### Automated Tests
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v --tb=short
```

### Manual Verification
- [ ] C1: `serverFarmId` gets actual plan ID (not None)
- [ ] C2: Missing identity raises ValueError
- [ ] C3: `get_managed_identity_id` only catches ResourceNotFoundError
- [ ] S1-S3: No silent fallbacks remain
- [ ] E1-E8: All exception checks use proper types
- [ ] I1-I6: All destroy functions remove settings
- [ ] M1-M3: App Service Plan created with Y1 SKU
- [ ] Test suite passes (681+ tests)

---

## 6. Design Decisions

1. **Y1 Consumption Plan** - Confirmed via cost optimizer (`freeRequests: 1,000,000`)
2. **App Service Plan ID** - Must be full resource ID, not just name
3. **Fail-fast on missing identity** - Prevents silent SystemAssigned fallback
4. **ResourceNotFoundError** - Azure SDK proper exception type

---

## 7. TODO (Future Work)

- [ ] Add `compile_azure_function()` to `src/util.py` (refactor from `compile_lambda_function`)
- [ ] Add actual function code ZIP deployment (compare with AWS pattern first)
- [ ] Add RBAC role assignments in L3 layer when Cosmos/Blob created

