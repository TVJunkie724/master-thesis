# GCP Function Lazy-Loading Fix

This plan addresses the GCP Cloud Function startup failures caused by `require_env()` being called at module-level, which fails during Cloud Functions container initialization.

## Problem

GCP Cloud Functions (Gen2) use Cloud Run under the hood. During container startup, Python modules are imported before environment variables are fully propagated, causing `require_env()` calls at module-level to fail with "Container Healthcheck failed".

## Solution: Lazy Loading Pattern (Azure Approach)

Azure functions solved this by using lazy-loading with getter functions:

```python
# BEFORE (fails at import time)
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))

# AFTER (loads on first use)
_digital_twin_info = None
def _get_digital_twin_info():
    global _digital_twin_info
    if _digital_twin_info is None:
        _digital_twin_info = json.loads(require_env("DIGITAL_TWIN_INFO"))
    return _digital_twin_info
```

---

## Proposed Changes

### GCP Cloud Functions to Update

#### [MODIFY] [dispatcher/main.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/gcp/cloud_functions/dispatcher/main.py)
- Convert `DIGITAL_TWIN_INFO` and `FUNCTION_BASE_URL` from module-level to lazy-loaded getters

#### [MODIFY] [persister/main.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/gcp/cloud_functions/persister/main.py)
- Convert `DIGITAL_TWIN_INFO` from module-level to lazy-loaded getter

#### [MODIFY] [processor_wrapper/main.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/gcp/cloud_functions/processor_wrapper/main.py)
- Convert `PERSISTER_FUNCTION_URL` from module-level to lazy-loaded getter

#### [MODIFY] [hot-reader/main.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/gcp/cloud_functions/hot-reader/main.py)
- Convert any `require_env()` calls from module-level to lazy-loaded getters

#### [MODIFY] [hot-to-cold-mover/main.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/gcp/cloud_functions/hot-to-cold-mover/main.py)
- Convert `DIGITAL_TWIN_INFO`, `FIRESTORE_COLLECTION`, `COLD_BUCKET_NAME` from module-level to lazy-loaded getters

#### [MODIFY] [default-processor/main.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/gcp/cloud_functions/default-processor/main.py)
- Convert `DIGITAL_TWIN_INFO` and `PERSISTER_FUNCTION_URL` from module-level to lazy-loaded getters

---

## Additional Terraform Fix Required

Also need to add `roles/run.admin` permission for the service account to set IAM policies on Cloud Run services.

---

## Verification Plan

### Automated Tests
- Re-run GCP E2E test after making changes:
  ```bash
  docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/e2e/gcp/test_gcp_terraform_e2e.py -v -s
  ```

### Expected Outcomes
- All Cloud Functions should deploy without "Container Healthcheck failed" errors
- Functions should invoke successfully when called
