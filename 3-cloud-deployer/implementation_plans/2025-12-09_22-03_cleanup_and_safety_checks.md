# Cleanup and Pre-Deployment Safety Checks

## 1. Executive Summary

### The Problem
1. **Dead code:** `src/sanity_checker.py` is not imported anywhere but contains useful validation logic (`check_digital_twin_name`).
2. **Stale documentation:** Multiple files reference `globals_aws.py` which no longer exists.
3. **Missing safety:** No pre-deployment check to prevent deploying over an existing twin.

### The Solution
1. **Migrate** the `check_digital_twin_name` logic to `src/validator.py`.
2. **Add** a `check_if_twin_exists()` method to `AWSProvider` to prevent duplicate deployments.
3. **Clean up** stale docstrings and TODOs.
4. **Delete** `src/sanity_checker.py`.

### Impact
- Deployments will fail fast if the twin already exists.
- Codebase will be cleaner and documentation accurate.

---

## 2. Current State

```
┌─────────────────────┐
│  sanity_checker.py  │  ← UNUSED, contains check_digital_twin_name()
└─────────────────────┘

┌─────────────────────┐      ┌─────────────────────┐
│    validator.py     │      │    deployer.py      │
│  (config validation)│      │  (deploy_all, etc.) │
└─────────────────────┘      └─────────────────────┘
         ↑                              │
         │                              ↓
         │                   ┌─────────────────────┐
         │                   │    AWSProvider      │
         └───────────────────│  (no exists check)  │
                             └─────────────────────┘
```

---

## 3. Proposed Changes

### Component: Validation

#### [MODIFY] validator.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/validator.py`
- **Description:** Add `validate_digital_twin_name(name: str)` function with:
  - Max 10 characters
  - Regex `^[A-Za-z0-9_-]+$`
  - Called during project validation

#### [DELETE] sanity_checker.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/sanity_checker.py`
- **Description:** Delete after migrating logic to `validator.py`

---

### Component: AWS Provider

#### [MODIFY] provider.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/provider.py`
- **Description:** 
  - Add `check_if_twin_exists() -> bool` method
  - Remove stale `globals_aws` docstring references

#### [MODIFY] util_aws.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/util_aws.py`
- **Description:** Remove stale `globals_aws` docstring references

#### [MODIFY] naming.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/naming.py`
- **Description:** Remove stale `globals_aws.py` docstring reference (line 5)

#### [MODIFY] clients.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/clients.py`
- **Description:** Remove stale `globals_aws.py` docstring reference (line 5)

---

### Component: Core Deployer

#### [MODIFY] deployer.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/deployer.py`
- **Description:** In `deploy_all()`, call `provider.check_if_twin_exists()` and raise error if True

---

### Component: AWS Layers

#### [MODIFY] layer_1_iot.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/layer_1_iot.py`
- **Description:** Remove stale TODO on line 18

#### [MODIFY] layer_2_compute.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/layer_2_compute.py`
- **Description:** Remove stale TODO (similar to layer_1_iot.py)

---

## 4. Code Examples

### validate_digital_twin_name (validator.py)
```python
import re

def validate_digital_twin_name(name: str) -> None:
    """
    Validates the digital twin name for AWS compatibility.
    
    Args:
        name: The digital twin name to validate
        
    Raises:
        ValueError: If name is invalid
    """
    if len(name) > 10:
        raise ValueError(f"Digital twin name '{name}' exceeds 10 characters.")
    
    if not re.match(r'^[A-Za-z0-9_-]+$', name):
        raise ValueError(
            f"Digital twin name '{name}' contains invalid characters. "
            "Only alphanumeric, hyphen, and underscore allowed."
        )
```

### check_if_twin_exists (provider.py)
```python
def check_if_twin_exists(self) -> bool:
    """
    Check if a digital twin with the current name already exists.
    
    Uses the hot DynamoDB table as the indicator since it's created
    in L3 and is a reliable marker of an existing deployment.
    
    Returns:
        True if the twin exists, False otherwise
    """
    table_name = self.naming.hot_dynamodb_table()
    try:
        self.clients["dynamodb"].describe_table(TableName=table_name)
        return True
    except self.clients["dynamodb"].exceptions.ResourceNotFoundException:
        return False
```

### deploy_all check (deployer.py)
```python
def deploy_all(context: 'DeploymentContext', provider: str) -> None:
    """Deploy all layers for a provider."""
    provider_instance = context.providers[provider]
    
    # Pre-deployment safety check
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

## 5. Implementation Phases

### Phase 1: Migrate Validation Logic
| Step | File | Action |
|------|------|--------|
| 1.1  | `src/validator.py` | Add `validate_digital_twin_name()` function |
| 1.2  | `src/validator.py` | Call from `verify_project_structure()` or similar |

### Phase 2: Add Pre-Deployment Check
| Step | File | Action |
|------|------|--------|
| 2.1  | `src/providers/aws/provider.py` | Add `check_if_twin_exists()` method |
| 2.2  | `src/providers/deployer.py` | Call check in `deploy_all()` |

### Phase 3: Cleanup
| Step | File | Action |
|------|------|--------|
| 3.1  | `src/providers/aws/util_aws.py` | Remove `globals_aws` docstring refs |
| 3.2  | `src/providers/aws/naming.py` | Remove `globals_aws.py` docstring ref (line 5) |
| 3.3  | `src/providers/aws/clients.py` | Remove `globals_aws.py` docstring ref (line 5) |
| 3.4  | `src/providers/aws/provider.py` | Remove `globals_aws` docstring refs |
| 3.5  | `src/providers/aws/layers/layer_1_iot.py` | Remove stale TODO (line 18) |
| 3.6  | `src/providers/aws/layers/layer_2_compute.py` | Remove stale TODO |
| 3.7  | `src/sanity_checker.py` | **DELETE** file |

---

## 6. Verification Checklist

- [ ] All existing tests pass:
  ```bash
  docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v
  ```
- [ ] `validate_digital_twin_name` raises error for invalid names
- [ ] `check_if_twin_exists` returns True when table exists
- [ ] `deploy_all` raises error when twin exists
- [ ] `sanity_checker.py` is deleted
- [ ] No remaining `globals_aws` references in docstrings

---

## 7. Design Decisions

| Decision | Rationale |
|----------|-----------|
| Use DynamoDB table as existence indicator | Created in L3, reliable marker. Could also use L1 Dispatcher Role, but L3 is more central. |
| 10 character limit on twin name | AWS naming constraints for S3 bucket prefixes and other resources |
| Regex `[A-Za-z0-9_-]` | Compatible with all AWS resource naming requirements |
