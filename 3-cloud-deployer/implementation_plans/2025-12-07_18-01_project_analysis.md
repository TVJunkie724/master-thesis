# Cloud Deployer Project Analysis

## Executive Summary

This document presents a comprehensive analysis of the `3-cloud-deployer` project, identifying bugs, misconfigurations, missing error handling, and missing tests. The analysis covers the core codebase, API endpoints, AWS deployer logic, validators, and unit tests.

---

## 🔴 Critical Bugs

### 1. **Missing Function Call in `core_deployer.py`** (Line 50)
**File:** [core_deployer.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/deployers/core_deployer.py#L45-L56)

```python
def redeploy_l2_event_checker(provider=None):
  if provider is None:
    raise ValueError("Provider must be specified for deployment.")
  match provider:
    case "aws":
      core_aws.redeploy_event_checker_lambda_function  # ⚠️ MISSING PARENTHESES - FUNCTION NOT CALLED!
```

**Issue:** The function `core_aws.redeploy_event_checker_lambda_function` is referenced but **not called** (missing `()`). This means the events are never actually recreated when the user runs `recreate_updated_events`.

**Fix:** Add parentheses: `core_aws.redeploy_event_checker_lambda_function()`

---

### 2. **Raising String Instead of Exception in `iot_deployer_aws.py`** (Line 63)
**File:** [iot_deployer_aws.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/iot_deployer_aws.py#L58-L65)

```python
if len(principals) > 1:
  raise "Error at deleting IoT Thing: Too many principals or certificates attached. Not sure which one to delete."
```

**Issue:** Python does not allow raising a raw string. This will cause a `TypeError: exceptions must derive from BaseException`.

**Fix:** Use a proper exception: `raise ValueError("Error at deleting IoT Thing: Too many principals...")`

---

### 3. **Environment Variable Not Set for Event Checking in Persister Lambda**
**File:** [persister/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/lambda_functions/persister/lambda_function.py#L30)

```python
if os.environ.get("USE_EVENT_CHECKING", "false").lower() == "true":
```

**Issue:** The environment variable `USE_EVENT_CHECKING` is checked in the Persister Lambda, but when the Persister Lambda is created in [layer_2_compute.py#L130-L136](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/deployer_layers/layer_2_compute.py#L130-L136), it's **not passed** to the environment.

**Result:** Event checking will **never** be triggered by the Persister, even when `useEventChecking` is enabled.

---

### 4. **Connector Lambda Function Not Destroyed**
**File:** [iot_deployer_aws.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/iot_deployer_aws.py#L269-L277)

When `L2 != AWS` (multi-cloud scenario), a "Connector Lambda" is created instead of a "Processor Lambda". However, the destroy function only attempts to delete the **Processor** Lambda.

**Issue:** If a Connector was created, it won't be destroyed because the function name differs (`connector_lambda_function_name` vs `processor_lambda_function_name`).

---

### 5. **Code Validation Schema Mismatched with Template Files**
**File:** [constants.py#L36-L39](file:///d:/Git/master-thesis/3-cloud-deployer/src/constants.py#L36-L39)

The code validation schema uses **wrong field names** that don't match the template files (which are the source of truth):

**Templates use** ([config_credentials.json.example](file:///d:/Git/master-thesis/3-cloud-deployer/upload/template/config_credentials.json.example)):
```json
{
  "azure": {
    "azure_region": "westeurope"
  },
  "gcp": {
    "gcp_project_id": "your-project-id",
    "gcp_credentials_file": "/path/to/file.json",
    "gcp_region": "europe-west1"
  }
}
```

**Required Fixes in `constants.py`:**
| Current (Wrong) | Should Be (Per Template) |
|-----------------|--------------------------|
| `azure_location` | `azure_region` |
| `google_project_id` | `gcp_project_id` |
| `google_application_credentials` | `gcp_credentials_file` |
| `google_region` | `gcp_region` |
| `google_zone` | *(remove - not in template)* |

**Impact:** Current code will reject valid config files that follow the template.

---

## 🟠 Significant Issues

### 6. **Hardcoded Policy ARNs in `iot_deployer_aws.py`**
**File:** [iot_deployer_aws.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/iot_deployer_aws.py#L140-L143)

Policy ARNs are hardcoded inline instead of using the centralized constants from `constants.py`.

---

### 7. **Duplicate Function Definitions in `globals.py` and `util.py`**
Both files define `contains_provider()` and `validate_credentials()` functions with identical implementations.

---

### 8. **Inconsistent L3 Destroy Order in API vs CLI**
The destroy order is reversed between API (`hot→cold→archive`) and CLI (`archive→cold→hot`).

---

### 9. **Missing `init_values_deployer` in API Deployment**
The API's `/deploy` endpoint is missing `init_values_deployer.deploy()` call that exists in CLI.

---

## 🟡 Missing Error Handling

### 10. **No Error Handling for Missing State Machine File**
### 11. **Silent Failure When Inter-Cloud Connection Info Missing**
### 12. **`except:` Bare Exception in `validator.py`**
### 13. **No Validation for Invalid Provider in API Endpoints**

---

## 🔵 Missing Tests

### 14. **No Tests for AWS Lambda Code Validation**
### 15. **No Tests for `file_manager.py` Functions**
### 16. **No Integration Tests for API Endpoints**
### 17. **No Edge Case Tests for Validators**
### 18. **No Tests for CLI Safety Checks**

---

## 🟣 Misconfigurations & Code Quality

### 19. **Deprecated FastAPI Event Handler**
### 20. **Unused Import in `core_deployer.py`**
### 21. **Inconsistent Import Style**
### 22. **No Type Hints in Core Functions**

---

## 📚 Outdated Documentation

### 23. **`config.json` Schema Mismatch** - Docs show wrong field names
### 24. **Missing `project_name` Query Parameter in API Docs**
### 25. **Missing HTTP 409 Error Code**
### 26. **Missing `config_inter_cloud.json` Documentation**
### 27. **CLI Missing Project Management Commands**
### 28. ~~Azure Credentials Schema Mismatch~~ *(Covered by #5)*
### 29. **Typo in Architecture Docs** - `layer_5 _provider` has space
### 30. **Setup Usage Docs - Outdated config.json Schema**
### 31. ~~Setup Usage Docs - Azure Credentials Mismatch~~ *(Covered by #5)*
### 32. **Missing Validation Endpoints in API Docs**
### 33. **Missing Projects Endpoints in API Docs**
### 34. **Testing Docs - Incomplete Test File List**

---

## 📋 Recommendations Priority Matrix

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| 🔴 P0 | #1 Missing function call parentheses | Low | Critical |
| 🔴 P0 | #2 Raise string instead of exception | Low | Critical |
| 🔴 P0 | #3 Missing USE_EVENT_CHECKING env var | Low | High |
| 🔴 P0 | #5 Code validation schema mismatch | Low | Critical |
| 🟠 P1 | #4 Connector Lambda not destroyed | Medium | High |
| 🟠 P1 | #8 Inconsistent destroy order | Low | Medium |
| 🟠 P1 | #9 Missing init_values_deployer in API | Low | Medium |
| 🟡 P2 | #10-13 Missing error handling | Medium | Medium |
| 🔵 P3 | #14-18 Missing tests | High | Medium |
| 🟣 P4 | #19-22 Code quality | Medium | Low |
| 📚 P2 | #23-27, #29-30, #32-34 Docs | Medium | Medium |
