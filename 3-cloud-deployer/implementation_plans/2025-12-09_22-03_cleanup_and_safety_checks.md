# Cleanup and Pre-Deployment Safety Checks

> **Status:** ✅ All phases complete (2025-12-09) | 384 tests passing

## 1. Executive Summary

### The Problem
1. **Dead code:** `src/sanity_checker.py` (52 lines) is not imported anywhere but contains `check_digital_twin_name` validation logic that should be preserved.
2. **Stale documentation:** 9 references to `globals_aws.py` (no longer exists) across 4 files.
3. **Stale TODOs:** 2 outdated TODO comments about moving `util_aws`.
4. **Missing safety:** No pre-deployment check to verify cloud resources don't already exist before deploying.

### The Solution
1. **Migrate** `check_digital_twin_name` logic from `sanity_checker.py` to `validator.py`.
2. **Add** `check_if_twin_exists()` method to `AWSProvider` that checks for DynamoDB table existence.
3. **Integrate** the pre-deployment check into `deploy_all()`.
4. **Clean up** stale docstring references and TODOs.
5. **Delete** `src/sanity_checker.py`.

### Impact
- Invalid twin names are caught during validation (before upload).
- Deployments fail fast if cloud resources already exist.
- Codebase is cleaner with accurate documentation.

---

## 2. Current State

```
Deployment Flow (Current):
┌─────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Upload    │─────▶│   deploy_all()  │─────▶│  AWS Resources  │
│  (no name   │      │  (no exists     │      │  (may conflict) │
│   check)    │      │   check)        │      │                 │
└─────────────┘      └─────────────────┘      └─────────────────┘

Proposed Flow:
┌─────────────┐      ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Upload    │─────▶│ validate_twin   │─────▶│  deploy_all()   │─────▶│  AWS Resources  │
│             │      │ _name()         │      │ check_if_twin   │      │                 │
│             │      │ (format check)  │      │ _exists()       │      │                 │
└─────────────┘      └─────────────────┘      └─────────────────┘      └─────────────────┘
                            ↓                        ↓
                     ValueError if                ValueError if
                     >10 chars or                 DynamoDB table
                     invalid chars                already exists
```

### Files with Issues

```
src/
├── sanity_checker.py         [DELETE] - Unused, migrate logic to validator.py
├── validator.py              [MODIFY] - Add validate_digital_twin_name()
└── providers/
    ├── deployer.py           [MODIFY] - Add pre-deployment check to deploy_all()
    └── aws/
        ├── provider.py       [MODIFY] - Add check_if_twin_exists(), fix line 14
        ├── util_aws.py       [MODIFY] - Fix docstrings lines 11, 44, 62, 103, 135, 173
        ├── naming.py         [MODIFY] - Fix docstring line 5
        ├── clients.py        [MODIFY] - Fix docstring line 5
        └── layers/
            ├── layer_1_iot.py     [MODIFY] - Remove TODO line 18
            └── layer_2_compute.py [MODIFY] - Remove TODO line 21
```

---

## 3. Proposed Changes

### Component: Core Validation

#### [MODIFY] validator.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/validator.py`
- **Description:** Add `validate_digital_twin_name(name: str)` function and integrate it into `validate_config_content` when validating `config.json`.

#### [DELETE] sanity_checker.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/sanity_checker.py`
- **Description:** Delete after migrating logic to `validator.py`. File is unused (no imports found).

---

### Component: AWS Provider

#### [MODIFY] provider.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/provider.py`
- **Description:** 
  1. Add `check_if_twin_exists() -> bool` method (uses DynamoDB `describe_table`)
  2. Update stale docstring on line 14

#### [MODIFY] util_aws.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/util_aws.py`
- **Description:** Update 6 stale docstring references to `globals_aws`:
  - Line 11: Module docstring
  - Line 44: `iot_rule_exists` docstring
  - Line 62: `destroy_s3_bucket` docstring
  - Line 103: `get_grafana_workspace_id_by_name` docstring
  - Line 135: `create_twinmaker_entity` docstring
  - Line 173: `create_twinmaker_component` docstring

#### [MODIFY] naming.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/naming.py`
- **Description:** Update stale docstring on line 5

#### [MODIFY] clients.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/clients.py`
- **Description:** Update stale docstring on line 5

---

### Component: Core Deployer

#### [MODIFY] deployer.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/deployer.py`
- **Description:** Add pre-deployment check in `deploy_all()` (line 173-179) to call `check_if_twin_exists()` and raise error if resources exist.

---

### Component: AWS Layers

#### [MODIFY] layer_1_iot.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/layer_1_iot.py`
- **Description:** Remove stale TODO comment on line 18

#### [MODIFY] layer_2_compute.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/layer_2_compute.py`
- **Description:** Remove stale TODO comment on line 21

---

## 4. Code Examples

### 4.1 validate_digital_twin_name (validator.py)

**Add after imports (around line 20):**
```python
import re
```

**Add new function (before section 1):**
```python
def validate_digital_twin_name(name: str) -> None:
    """
    Validates the digital twin name for AWS resource naming compatibility.
    
    Constraints:
    - Maximum 10 characters (S3 bucket prefix limits)
    - Only alphanumeric, hyphen, underscore allowed
    
    Args:
        name: The digital twin name to validate
        
    Raises:
        ValueError: If name exceeds length or contains invalid characters
    """
    max_length = 10
    if len(name) > max_length:
        raise ValueError(
            f"Digital twin name '{name}' exceeds {max_length} characters."
        )
    
    valid_pattern = r'^[A-Za-z0-9_-]+$'
    if not re.match(valid_pattern, name):
        raise ValueError(
            f"Digital twin name '{name}' contains invalid characters. "
            "Only alphanumeric, hyphen, and underscore allowed."
        )
```

**Integrate into validate_config_content (around line 60):**
```python
# Inside validate_config_content, after checking CONFIG_FILE
if filename == CONSTANTS.CONFIG_FILE:
    # Validate digital_twin_name format
    twin_name = content.get("digital_twin_name")
    if twin_name:
        validate_digital_twin_name(twin_name)
```

---

### 4.2 check_if_twin_exists (provider.py)

**Add inside AWSProvider class (after line 100):**
```python
def check_if_twin_exists(self) -> bool:
    """
    Check if a digital twin with the current name already exists in AWS.
    
    Uses the hot DynamoDB table as the indicator since it's created
    in L3 and is a reliable marker of an existing deployment.
    
    Returns:
        True if the twin's resources exist, False otherwise.
        
    Raises:
        RuntimeError: If clients are not initialized.
    """
    if not self._clients:
        raise RuntimeError("AWS clients not initialized. Call initialize_clients() first.")
    
    from botocore.exceptions import ClientError
    
    table_name = self.naming.hot_dynamodb_table()
    try:
        self._clients["dynamodb"].describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise
```

---

### 4.3 deploy_all pre-check (deployer.py)

**Before (lines 173-179):**
```python
def deploy_all(context: 'DeploymentContext', provider: str) -> None:
    """Deploy all layers for a provider."""
    deploy_l1(context, provider)
    deploy_l2(context, provider)
    deploy_l3(context, provider)
    deploy_l4(context, provider)
    deploy_l5(context, provider)
```

**After:**
```python
def deploy_all(context: 'DeploymentContext', provider: str) -> None:
    """Deploy all layers for a provider.
    
    Pre-deployment safety: Checks if cloud resources already exist.
    """
    # Pre-deployment safety check
    if provider in context.providers:
        provider_instance = context.providers[provider]
        if hasattr(provider_instance, 'check_if_twin_exists'):
            if provider_instance.check_if_twin_exists():
                raise ValueError(
                    f"Digital Twin '{context.config.digital_twin_name}' already exists "
                    f"for provider '{provider}'. Destroy it first or use a different name."
                )
    
    deploy_l1(context, provider)
    deploy_l2(context, provider)
    deploy_l3(context, provider)
    deploy_l4(context, provider)
    deploy_l5(context, provider)
```

---

### 4.4 Docstring Fixes

**util_aws.py line 11 - Before:**
```python
with backward-compatible fallback to globals_aws.
```
**After:**
```python
All functions require explicit client parameters.
```

**util_aws.py lines 44, 62, 103, 135, 173 - Before:**
```python
iot_client: Optional boto3 IoT client. If None, uses globals_aws.aws_iot_client
```
**After:**
```python
iot_client: boto3 IoT client (required)
```

**provider.py line 14 - Before:**
```python
    This provider wraps the existing code in src/aws/globals_aws.py,
```
**After:**
```python
    This provider centralizes AWS client and naming management,
```

**naming.py line 5 - Before:**
```python
names for all AWS resources. It extracts the naming logic from globals_aws.py.
```
**After:**
```python
names for all AWS resources.
```

**clients.py line 5 - Before:**
```python
It extracts the client creation logic from the legacy globals_aws.py.
```
**After:**
```python
It provides centralized client initialization for the AWSProvider.
```

---

### 4.5 TODO Removals

**layer_1_iot.py line 18 - Before:**
```python
import src.providers.aws.util_aws as util_aws  # TODO: Update import after moving util_aws
```
**After:**
```python
import src.providers.aws.util_aws as util_aws
```

**layer_2_compute.py line 21 - Before:**
```python
import src.providers.aws.util_aws as util_aws  # TODO: Update import after moving util_aws
```
**After:**
```python
import src.providers.aws.util_aws as util_aws
```

---

## 5. Implementation Phases

### Phase 1: Migrate Validation Logic
| Step | File | Action |
|------|------|--------|
| 1.1  | `src/validator.py` | Add `import re` after line 19 |
| 1.2  | `src/validator.py` | Add `validate_digital_twin_name()` function before section 1 |
| 1.3  | `src/validator.py` | Integrate call in `validate_config_content()` for `config.json` |

### Phase 2: Add Pre-Deployment Check
| Step | File | Action |
|------|------|--------|
| 2.1  | `src/providers/aws/provider.py` | Add `check_if_twin_exists()` method to `AWSProvider` class |
| 2.2  | `src/providers/deployer.py` | Add pre-deployment check to `deploy_all()` (lines 173-179) |

### Phase 3: Cleanup Stale References
| Step | File | Line(s) | Action |
|------|------|---------|--------|
| 3.1  | `util_aws.py` | 11 | Update module docstring |
| 3.2  | `util_aws.py` | 44 | Update `iot_rule_exists` docstring |
| 3.3  | `util_aws.py` | 62 | Update `destroy_s3_bucket` docstring |
| 3.4  | `util_aws.py` | 103 | Update `get_grafana_workspace_id_by_name` docstring |
| 3.5  | `util_aws.py` | 135 | Update `create_twinmaker_entity` docstring |
| 3.6  | `util_aws.py` | 173 | Update `create_twinmaker_component` docstring |
| 3.7  | `provider.py` | 14 | Update module docstring |
| 3.8  | `naming.py` | 5 | Update module docstring |
| 3.9  | `clients.py` | 5 | Update module docstring |
| 3.10 | `layer_1_iot.py` | 18 | Remove TODO comment |
| 3.11 | `layer_2_compute.py` | 21 | Remove TODO comment |
| 3.12 | `sanity_checker.py` | - | **DELETE** entire file |

---

## 6. Verification Checklist

### Automated Tests
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v
```

### Manual Verification
- [ ] All existing tests pass (331+ tests)
- [ ] `validate_digital_twin_name("valid-name")` - no error
- [ ] `validate_digital_twin_name("toolongname!")` - raises ValueError
- [ ] `validate_digital_twin_name("invalid@chars")` - raises ValueError
- [ ] No remaining `globals_aws` references:
  ```bash
  docker exec master-thesis-3cloud-deployer-1 grep -r "globals_aws" /app/src --include="*.py"
  ```
- [ ] `sanity_checker.py` is deleted
- [ ] No remaining stale TODOs in layer files

---

## 7. Design Decisions

| Decision | Rationale |
|----------|-----------|
| Use DynamoDB `describe_table` for existence check | DynamoDB table is created in L3 and is a reliable, persistent marker. Faster than checking multiple resources. |
| 10 character limit on twin name | AWS naming constraints for S3 bucket prefixes (63 char total, need room for suffixes). |
| Regex `^[A-Za-z0-9_-]+$` | Compatible with all AWS resource naming requirements (IAM, Lambda, S3, DynamoDB). |
| `hasattr` check for `check_if_twin_exists` | Allows graceful fallback for providers that don't implement it (Azure, GCP stubs). |
| Integrate name validation in `validate_config_content` | Catches issues early, before project creation. |
| Delete `sanity_checker.py` rather than keep | Dead code; all logic migrated to `validator.py`. |
