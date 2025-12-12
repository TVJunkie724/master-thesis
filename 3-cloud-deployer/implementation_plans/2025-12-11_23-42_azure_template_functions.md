# Azure Template Functions Implementation

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Current State](#2-current-state)
3. [Proposed Changes](#3-proposed-changes)
4. [Implementation Phases](#4-implementation-phases)
5. [Verification Checklist](#5-verification-checklist)

---

## 1. Executive Summary

### The Problem
AWS template functions in `upload/template/lambda_functions/` have no Azure equivalents. Users deploying to Azure cannot use these templates.

### The Solution
Create fully functional Azure equivalents for all 5 template functions with actual Azure SDK implementations.

### Impact
- Azure deployments will have feature parity with AWS
- Users can upload and customize Azure function templates

---

## 2. Current State

```
upload/template/
├── lambda_functions/           # AWS (existing)
│   ├── event-feedback/
│   │   └── lambda_function.py
│   ├── event_actions/
│   │   ├── high-temperature-callback/
│   │   │   └── lambda_function.py
│   │   └── high-temperature-callback-2/
│   │       └── lambda_function.py
│   └── processors/
│       ├── default_processor/
│       │   └── process.py
│       └── temperature-sensor-2/
│           └── lambda_function.py
└── azure_functions/            # Azure (TO BE CREATED)
    └── (mirror structure)
```

---

## 3. Proposed Changes

### Component: Event Feedback

#### [NEW] event-feedback/function_app.py
- **Path:** `upload/template/azure_functions/event-feedback/function_app.py`
- **Description:** Azure Function that sends C2D messages to IoT devices via `IoTHubRegistryManager`

---

### Component: Event Actions

#### [NEW] high-temperature-callback/function_app.py
- **Path:** `upload/template/azure_functions/event_actions/high-temperature-callback/function_app.py`
- **Description:** Simple event action template with Azure Functions `main(req)` entry point

#### [NEW] high-temperature-callback-2/function_app.py
- **Path:** `upload/template/azure_functions/event_actions/high-temperature-callback-2/function_app.py`
- **Description:** Event action with IoT Hub C2D feedback

---

### Component: Processors

#### [NEW] default_processor/process.py
- **Path:** `upload/template/azure_functions/processors/default_processor/process.py`
- **Description:** User processing logic template (pure Python, no SDK change needed)

#### [NEW] temperature-sensor-2/function_app.py
- **Path:** `upload/template/azure_functions/processors/temperature-sensor-2/function_app.py`
- **Description:** Processor with validation logic, Azure Functions entry point

---

### Component: Tests

#### [NEW] test_azure_templates.py
- **Path:** `tests/unit/azure_functions/test_azure_templates.py`
- **Description:** Unit tests for all 5 Azure template functions

---

## 4. Implementation Phases

### Phase 1: Create Directory Structure
| Step | Action |
|------|--------|
| 1.1 | Create `upload/template/azure_functions/` |
| 1.2 | Create subdirectories: `event-feedback/`, `event_actions/`, `processors/` |

### Phase 2: Implement Functions
| Step | File | Action |
|------|------|--------|
| 2.1 | `event-feedback/function_app.py` | Create with IoT Hub C2D |
| 2.2 | `event_actions/high-temperature-callback/function_app.py` | Create |
| 2.3 | `event_actions/high-temperature-callback-2/function_app.py` | Create with C2D |
| 2.4 | `processors/default_processor/process.py` | Create |
| 2.5 | `processors/temperature-sensor-2/function_app.py` | Create |

### Phase 3: Tests
| Step | File | Action |
|------|------|--------|
| 3.1 | `tests/unit/azure_functions/test_azure_templates.py` | Create comprehensive tests |

---

## 5. Verification Checklist

- [x] All 5 Azure template files created
- [x] All existing tests pass
- [x] New template tests pass (9 tests)
- [x] Test command: `docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --tb=short`
