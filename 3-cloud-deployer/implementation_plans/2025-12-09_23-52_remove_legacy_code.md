# Remove Legacy Code and Comments

> **Status:** ✅ Complete (2025-12-09) | 384 tests passing

## 1. Executive Summary

### The Problem
The codebase contains legacy references to a now-deleted `globals.py` module:
- **1 functional issue:** `src/api/validation.py` still imports and uses a `globals` module
- **30+ stale comments** mentioning "globals", "legacy", "fallback has been removed"

### The Solution
1. Replace the `globals` usage in `api/validation.py` with `src.core.state`
2. Clean up stale comments across all affected files

### Impact
- Cleaner codebase without dead references
- No functional changes (stale comments only)
- Easier maintenance and onboarding

---

## 2. Current State

```
Findings Summary:
┌──────────────────────────────────────────────────────────────────────────────┐
│ CRITICAL: api/validation.py still imports 'globals' module (lines 10-18)    │
├──────────────────────────────────────────────────────────────────────────────┤
│ STALE COMMENTS (30+ occurrences across 15+ files)                            │
│ - "globals fallback has been removed"                                        │
│ - "uses globals for..."                                                      │
│ - "replaces/replacing the legacy..."                                         │
│ - "If None, uses globals..."                                                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Files with Stale Comments

| File | Line(s) | Content |
|------|---------|---------|
| `api/validation.py` | 10-18, 238 | Actually imports and uses `globals` |
| `validator.py` | 8, 365, 407 | "globals fallback" |
| `util.py` | 61, 159 | "falls back to globals for legacy" |
| `util_aws.py` | 134, 136, 172, 174, 323, 347 | "If None, uses globals" |
| `lambda_manager.py` | 8, 107, 156 | "legacy (globals-based)" |
| `info.py` | 8 | "Legacy globals fallback has been removed" |
| `file_manager.py` | 8 | "Legacy globals fallback has been removed" |
| `logger.py` | 66 | "Removed circular dependency on globals" |
| `core/state.py` | 5 | "replacing the legacy" |
| `core/context.py` | 4, 17 | "replaces globals" |
| `core/config_loader.py` | 5 | "replaces the configuration loading" |
| `api/deployment.py` | 112 | "legacy files still rely" |
| `api/projects.py` | 90 | "is removed as we move" |
| `layer_1_iot.py` | 9, 150 | "instead of using globals" |
| `layer_2_compute.py` | 10, 573, 603, 607 | "instead of globals", "legacy code" |
| `layer_3_storage.py` | 10 | "instead of using globals" |
| `layer_4_twinmaker.py` | 10 | "instead of using globals" |
| `layer_5_grafana.py` | 9 | "instead of using globals" |
| `naming.py` | 16 | "rather than reading from globals" |
| `l1_adapter.py` | 39, 77 | "no globals needed" |
| `core/__init__.py` | 9 | "replaces globals" |

> **Note:** `iot_device_simulator/aws/` files use their own `globals.py` - this is intentional for the simulator package and should NOT be changed.

---

## 3. Proposed Changes

### Component: API Layer

#### [MODIFY] validation.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/api/validation.py`
- **Description:** 
  - Remove lines 10-18 (lazy `globals` import)
  - Replace `_get_globals().project_path()` with `state.get_project_base_path()`
  - Add `import src.core.state as state`

---

### Component: Core Modules (Comment Cleanup)

#### [MODIFY] validator.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/validator.py`
- **Lines:** 8, 365, 407
- **Action:** Update/remove stale comments

#### [MODIFY] util.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/util.py`
- **Lines:** 61, 159
- **Action:** Update docstrings

#### [MODIFY] info.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/info.py`
- **Line:** 8
- **Action:** Remove "Legacy globals fallback has been removed"

#### [MODIFY] file_manager.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/file_manager.py`
- **Line:** 8
- **Action:** Remove "Legacy globals fallback has been removed"

#### [MODIFY] logger.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/logger.py`
- **Line:** 66
- **Action:** Remove stale comment

---

### Component: AWS Provider Layer

#### [MODIFY] util_aws.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/util_aws.py`
- **Lines:** 134, 136, 172, 174, 323, 347
- **Action:** Update docstrings to reflect current behavior

#### [MODIFY] lambda_manager.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_manager.py`
- **Lines:** 8, 107, 156
- **Action:** Update docstrings

#### [MODIFY] naming.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/naming.py`
- **Line:** 16
- **Action:** Update comment

#### [MODIFY] l1_adapter.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/l1_adapter.py`
- **Lines:** 39, 77
- **Action:** Simplify comments

---

### Component: AWS Layers

#### [MODIFY] layer_1_iot.py
- **Lines:** 9, 150
- **Action:** Update comments

#### [MODIFY] layer_2_compute.py
- **Lines:** 10, 573, 603, 607
- **Action:** Update/remove legacy comments

#### [MODIFY] layer_3_storage.py, layer_4_twinmaker.py, layer_5_grafana.py
- **Action:** Update module docstrings

---

### Component: Core Package

#### [MODIFY] core/state.py, context.py, config_loader.py, __init__.py
- **Action:** Update docstrings to remove "legacy/replacing" language

---

### Component: API Deployment

#### [MODIFY] api/deployment.py
- **Line:** 112
- **Action:** Update comment

#### [MODIFY] api/projects.py
- **Line:** 90
- **Action:** Update comment

---

## 4. Implementation Phases

### Phase 1: Fix Functional Issue
| Step | File | Action |
|------|------|--------|
| 1.1  | `api/validation.py` | Remove lines 10-18, add `import src.core.state as state` |
| 1.2  | `api/validation.py` | Update line 238 to use `state.get_project_base_path()` |

### Phase 2: Clean Core Module Comments
| Step | File | Lines | Action |
|------|------|-------|--------|
| 2.1  | `validator.py` | 8 | Simplify docstring |
| 2.2  | `validator.py` | 365, 407 | Update error messages |
| 2.3  | `util.py` | 61, 159 | Update docstrings |
| 2.4  | `info.py` | 8 | Remove legacy line |
| 2.5  | `file_manager.py` | 8 | Remove legacy line |
| 2.6  | `logger.py` | 66 | Remove comment |

### Phase 3: Clean AWS Provider Comments
| Step | File | Lines | Action |
|------|------|-------|--------|
| 3.1  | `util_aws.py` | 134, 136, 172, 174, 323, 347 | Update docstrings |
| 3.2  | `lambda_manager.py` | 8, 107, 156 | Update docstrings |
| 3.3  | `naming.py` | 16 | Update comment |
| 3.4  | `l1_adapter.py` | 39, 77 | Simplify comments |

### Phase 4: Clean AWS Layer Comments
| Step | File | Lines | Action |
|------|------|-------|--------|
| 4.1  | `layer_1_iot.py` | 9, 150 | Update comments |
| 4.2  | `layer_2_compute.py` | 10, 573, 603, 607 | Update comments |
| 4.3  | `layer_3_storage.py` | 10 | Update docstring |
| 4.4  | `layer_4_twinmaker.py` | 10 | Update docstring |
| 4.5  | `layer_5_grafana.py` | 9 | Update docstring |

### Phase 5: Clean Core Package & API Comments
| Step | File | Lines | Action |
|------|------|-------|--------|
| 5.1  | `core/state.py` | 5 | Update docstring |
| 5.2  | `core/context.py` | 4, 17 | Update docstring |
| 5.3  | `core/config_loader.py` | 5 | Update docstring |
| 5.4  | `core/__init__.py` | 9 | Update docstring |
| 5.5  | `api/deployment.py` | 112 | Update comment |
| 5.6  | `api/projects.py` | 90 | Update comment |

---

## 5. Verification Checklist

```bash
# Run all tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v

# Verify no 'globals' references remain (except iot_device_simulator)
docker exec master-thesis-3cloud-deployer-1 grep -r "globals" /app/src --include="*.py" | grep -v iot_device_simulator
```

- [ ] All 384+ tests pass
- [ ] No `globals` imports outside `iot_device_simulator/`
- [ ] Stale comments removed/updated

---

## 6. Design Decisions

| Decision | Rationale |
|----------|-----------|
| Keep `iot_device_simulator/aws/globals.py` | This is a separate, self-contained package for the simulator that runs independently |
| Replace with `src.core.state` | The state module is the canonical replacement for the old globals.py |
| Focus on comments, not functionality | Most changes are docstring/comment updates, low risk |
