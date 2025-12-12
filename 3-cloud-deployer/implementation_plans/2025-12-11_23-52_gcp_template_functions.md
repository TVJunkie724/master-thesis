# Google Cloud Template Functions Implementation

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Current State](#2-current-state)
3. [Proposed Changes](#3-proposed-changes)
4. [Implementation Phases](#4-implementation-phases)
5. [Verification Checklist](#5-verification-checklist)

---

## 1. Executive Summary

### The Problem
AWS template functions in `upload/template/lambda_functions/` have no Google Cloud equivalents.

### The Solution
Create fully functional Google Cloud Function equivalents for all 5 template functions with actual GCP SDK implementations.

### Impact
- GCP deployments will have feature parity with AWS and Azure
- Users can upload and customize GCP function templates

---

## 2. Current State

```
upload/template/
├── lambda_functions/           # AWS (existing)
├── azure_functions/            # Azure (created)
└── cloud_functions/            # GCP (TO BE CREATED)
    ├── event-feedback/
    ├── event_actions/
    │   ├── high-temperature-callback/
    │   └── high-temperature-callback-2/
    └── processors/
        ├── default_processor/
        └── temperature-sensor-2/
```

---

## 3. Proposed Changes

### Component: Event Feedback

#### [NEW] event-feedback/main.py
- **Path:** `upload/template/cloud_functions/event-feedback/main.py`
- **Description:** GCP Function that sends commands to IoT devices via `google.cloud.iot_v1`

---

### Component: Event Actions

#### [NEW] high-temperature-callback/main.py
- **Path:** `upload/template/cloud_functions/event_actions/high-temperature-callback/main.py`
- **Description:** Simple event action with GCP HTTP function entry point

#### [NEW] high-temperature-callback-2/main.py
- **Path:** `upload/template/cloud_functions/event_actions/high-temperature-callback-2/main.py`
- **Description:** Event action with IoT Core command feedback

---

### Component: Processors

#### [NEW] default_processor/process.py
- **Path:** `upload/template/cloud_functions/processors/default_processor/process.py`
- **Description:** User processing logic template (pure Python)

#### [NEW] temperature-sensor-2/main.py
- **Path:** `upload/template/cloud_functions/processors/temperature-sensor-2/main.py`
- **Description:** Processor with validation logic

---

### Component: Tests

#### [NEW] test_gcp_templates.py
- **Path:** `tests/unit/gcp_functions/test_gcp_templates.py`
- **Description:** Unit tests for all 5 GCP template functions

---

## 4. Implementation Phases

### Phase 1: Create Directory Structure
| Step | Action |
|------|--------|
| 1.1 | Create `upload/template/cloud_functions/` |
| 1.2 | Create subdirectories |

### Phase 2: Implement Functions
| Step | File | Action |
|------|------|--------|
| 2.1 | `event-feedback/main.py` | Create with IoT Core commands |
| 2.2 | `event_actions/high-temperature-callback/main.py` | Create |
| 2.3 | `event_actions/high-temperature-callback-2/main.py` | Create |
| 2.4 | `processors/default_processor/process.py` | Create |
| 2.5 | `processors/temperature-sensor-2/main.py` | Create |

### Phase 3: Tests
| Step | File | Action |
|------|------|--------|
| 3.1 | `tests/unit/gcp_functions/test_gcp_templates.py` | Create |

---

## 5. Verification Checklist

- [x] All 5 GCP template files created
- [x] All existing tests pass
- [x] New template tests pass (9 tests)
- [x] Test command: `docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --tb=short`
