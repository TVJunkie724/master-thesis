# Implementation Plan: Fix Azure Function Deployment Configuration

## Overview

Apply the working ZIP deploy configuration from the E2E test to all Azure Function Apps in Terraform, and implement user-editable function support.

## Findings

### Current Issues

| File | Problem |
|------|---------|
| All Azure TF files | Missing `ENABLE_ORYX_BUILD = "true"` |
| All Azure TF files | Has `WEBSITE_RUN_FROM_PACKAGE = "1"` (conflicts with remote build) |
| `function_bundler.py` | No `bundle_user_functions()` for upload/ directory |
| SDK deployment | No post-Terraform ZIP deploy for user functions |

### Affected Function Apps (5 total)

| App | File | zip_deploy_file |
|-----|------|-----------------|
| `l0_glue` | azure_glue.tf | var.azure_l0_zip_path |
| `l1` | azure_iot.tf | var.azure_l1_zip_path |
| `l2` | azure_compute.tf | var.azure_l2_zip_path |
| `l3` | azure_storage.tf | var.azure_l3_zip_path |
| `user` | azure_compute.tf | **None** (SDK deploy) |

---

## Proposed Changes

### 1. Update Terraform App Settings

For each function app, update `app_settings` block:

```diff
 app_settings = {
   FUNCTIONS_WORKER_RUNTIME       = "python"
   FUNCTIONS_EXTENSION_VERSION    = "~4"
-  WEBSITE_RUN_FROM_PACKAGE       = "1"
   SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
+  ENABLE_ORYX_BUILD              = "true"
   AzureWebJobsFeatureFlags       = "EnableWorkerIndexing"
```

#### Files to Modify
- `azure_glue.tf` - L0 glue
- `azure_iot.tf` - L1 dispatcher
- `azure_compute.tf` - L2 & user functions
- `azure_storage.tf` - L3 hot storage

---

### 2. Add User Functions Bundler

#### [NEW] `bundle_user_functions()` in function_bundler.py

Bundles functions from `upload/<project_name>/azure_functions/`:
- `processors/` - Custom data processors
- `event_actions/` - Event-triggered actions
- `event-feedback/` - Feedback handlers

```python
def bundle_user_functions(project_path: str) -> Optional[bytes]:
    """Bundle user-customizable functions from upload/ directory."""
    user_funcs_dir = Path(project_path) / "azure_functions"
    if not user_funcs_dir.exists():
        return None
    # Bundle processors, event_actions, event-feedback
```

---

### 3. SDK-Based User Function Deployment

#### Approach
Since `user` function app has no `zip_deploy_file` in Terraform, we need SDK deployment after `terraform apply`.

#### Location
Add to existing Python orchestrator (e.g., `azure_deployer.py`)

#### Flow
1. After `terraform apply` completes
2. Get user function app name from Terraform outputs
3. Call `bundle_user_functions(project_path)`
4. Deploy ZIP via Kudu API (same as E2E test)

---

### 4. Update lifecycle ignore_changes

Remove `WEBSITE_RUN_FROM_PACKAGE` from `ignore_changes` since we're removing it:

```diff
 lifecycle {
   ignore_changes = [
-    app_settings["WEBSITE_RUN_FROM_PACKAGE"],
     app_settings["COSMOS_CONNECTION_STRING"],
   ]
 }
```

---

## Verification Plan

1. Run existing unit tests for function_bundler
2. Run Azure E2E test to verify L2 deployment works
3. (Future) Test full deployment with user functions

---

## Decision Points for User

> [!IMPORTANT]
> 1. **User functions scope**: Should `bundle_user_functions` include all three folders (processors, event_actions, event-feedback) or be configurable?
> 2. **Deployment timing**: Should user function deployment happen automatically after terraform, or be a separate CLI command?
