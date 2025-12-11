# GCP Hot Reader Multi-Cloud Implementation Plan (Future Work)

> **Status:** 📝 Future Work  
> **Parent Plan:** [2025-12-10_22-45_hot_reader_multi_cloud.md](./2025-12-10_22-45_hot_reader_multi_cloud.md)  
> **Priority:** After AWS implementation is complete

---

## 1. Executive Summary

This document outlines the future implementation of GCP Hot Reader functions to enable cross-cloud data access when GCP Firestore is the L3 Hot Storage provider.

### Scope

| Component | Description |
|-----------|-------------|
| `gcp-hot-reader` | Cloud Function that reads time-series **history** from Firestore |
| `gcp-hot-reader-last-entry` | Cloud Function that reads **current/latest** value from Firestore |

### Authentication

**MVP Approach:** Use `X-Inter-Cloud-Token` header only (same as AWS implementation).

---

## 2. Architecture

### When GCP L3 Hot Reader Is Needed

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO: L4 (any cloud) needs data from L3 GCP Firestore                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   L4: AWS/Azure/GCP                        L3: GCP                          │
│   ┌─────────────────────┐                 ┌─────────────────────┐          │
│   │  Hot Requester      │     HTTPS       │  GCP Firestore      │          │
│   │  (Lambda/Function)  │─────POST───────►│                     │          │
│   │                     │  X-Inter-Cloud  │  ┌───────────────┐  │          │
│   │  Determines L3 is   │     -Token      │  │ Hot Reader    │  │          │
│   │  on different cloud │                 │  │ (Cloud Func)  │  │          │
│   └─────────────────────┘                 │  └───────────────┘  │          │
│                                           └─────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Cross-Cloud Example: L3=GCP, L4=AWS, L5=Azure

This is a concrete example of a fully cross-cloud digital twin deployment using only `X-Inter-Cloud-Token` for authentication.

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                           MVP: X-INTER-CLOUD-TOKEN EVERYWHERE                              │
├───────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                           │
│   L5: Azure                   L4: AWS                         L3: GCP                     │
│   ┌──────────────────┐       ┌──────────────────┐            ┌──────────────────┐        │
│   │ Azure M.Grafana  │       │ AWS TwinMaker    │            │ GCP Firestore    │        │
│   │                  │       │                  │            │                  │        │
│   │ ┌──────────────┐ │       │ ┌──────────────┐ │   HTTPS    │ ┌──────────────┐ │        │
│   │ │ Infinity     │ │ POST  │ │Hot Requester │ │   POST     │ │ Hot Reader   │ │        │
│   │ │ Plugin       │─┼──────►│ │  (Lambda)    │─┼───────────►│ │(Cloud Func)  │ │        │
│   │ │              │ │       │ │              │ │            │ │              │ │        │
│   │ └──────────────┘ │       │ └──────────────┘ │            │ └──────────────┘ │        │
│   └──────────────────┘       └──────────────────┘            └──────────────────┘        │
│          │                          │                               │                    │
│          │                          │                               │                    │
│          ▼                          ▼                               ▼                    │
│   X-Inter-Cloud-Token        X-Inter-Cloud-Token             X-Inter-Cloud-Token        │
│   (validates at L4)          (passes to L3)                  (validates at L3)          │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

### Components Required:

| Layer | Cloud | Component | Auth |
|-------|-------|-----------|------|
| **L3** | GCP | Hot Reader (Cloud Function with HTTP URL) | Validates `X-Inter-Cloud-Token` |
| **L4** | AWS | Hot Requester (Lambda with Function URL) | Validates `X-Inter-Cloud-Token`, passes same token to L3 |
| **L5** | Azure | Grafana + Infinity plugin | Sends `X-Inter-Cloud-Token` header |

### Data Flow:

1. **Azure Grafana** POST → **AWS Hot Requester** (header: `X-Inter-Cloud-Token`)
2. **AWS Hot Requester** POST → **GCP Hot Reader** (header: `X-Inter-Cloud-Token`)  
3. **GCP Hot Reader** queries Firestore, returns TwinMaker-compatible JSON
4. Response flows back: GCP → AWS → Azure Grafana

---

## 4. Functions to Implement

### 4.1 gcp-hot-reader (Time-Series History)

**Purpose:** Returns data for a time range (used by graphs, charts, trend panels).

```python
# GCP Cloud Function: hot-reader (HTTP Trigger)
# File: src/providers/gcp/functions/hot-reader/main.py

import functions_framework
from google.cloud import firestore
import json
import os

def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value

# Required at startup
EXPECTED_TOKEN = _require_env("INTER_CLOUD_TOKEN")
FIRESTORE_COLLECTION = _require_env("FIRESTORE_COLLECTION")

# Firestore client (reusable across invocations)
db = firestore.Client()

@functions_framework.http
def hot_reader(request):
    # 1. Validate X-Inter-Cloud-Token
    token = request.headers.get("X-Inter-Cloud-Token", "").strip()
    if not token or token != EXPECTED_TOKEN:
        return ("Unauthorized", 401)
    
    # 2. Parse query parameters from body
    try:
        body = request.get_json()
        query_params = body.get("payload", {})
    except Exception:
        return ("Invalid JSON", 400)
    
    # 3. Query Firestore (TIME RANGE)
    device_id = query_params.get("iotDeviceId")
    start_time = query_params.get("startTime")
    end_time = query_params.get("endTime")
    selected_properties = query_params.get("selectedProperties", [])
    
    docs = db.collection(FIRESTORE_COLLECTION) \
        .where("iotDeviceId", "==", device_id) \
        .where("id", ">=", start_time) \
        .where("id", "<=", end_time) \
        .order_by("id") \
        .stream()
    
    items = [doc.to_dict() for doc in docs]
    
    # 4. Format response (TwinMaker-compatible)
    property_values = []
    for prop_name in selected_properties:
        entry = {
            "entityPropertyReference": {"propertyName": prop_name},
            "values": []
        }
        for item in items:
            if prop_name in item:
                entry["values"].append({
                    "time": item["id"],
                    "value": {"DoubleValue": item[prop_name]}
                })
        property_values.append(entry)
    
    return (json.dumps({"propertyValues": property_values}), 200, {"Content-Type": "application/json"})
```

### 4.2 gcp-hot-reader-last-entry (Current Value)

**Purpose:** Returns only the latest/current value (used by gauges, stat panels, live displays).

```python
# GCP Cloud Function: hot-reader-last-entry (HTTP Trigger)
# File: src/providers/gcp/functions/hot-reader-last-entry/main.py

import functions_framework
from google.cloud import firestore
import json
import os

def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value

EXPECTED_TOKEN = _require_env("INTER_CLOUD_TOKEN")
FIRESTORE_COLLECTION = _require_env("FIRESTORE_COLLECTION")

db = firestore.Client()

@functions_framework.http
def hot_reader_last_entry(request):
    # 1. Validate X-Inter-Cloud-Token
    token = request.headers.get("X-Inter-Cloud-Token", "").strip()
    if not token or token != EXPECTED_TOKEN:
        return ("Unauthorized", 401)
    
    # 2. Parse query parameters
    try:
        body = request.get_json()
        query_params = body.get("payload", {})
    except Exception:
        return ("Invalid JSON", 400)
    
    device_id = query_params.get("iotDeviceId")
    selected_properties = query_params.get("selectedProperties", [])
    
    # 3. Query Firestore (LATEST ENTRY ONLY)
    docs = db.collection(FIRESTORE_COLLECTION) \
        .where("iotDeviceId", "==", device_id) \
        .order_by("id", direction=firestore.Query.DESCENDING) \
        .limit(1) \
        .stream()
    
    items = [doc.to_dict() for doc in docs]
    
    if not items:
        return (json.dumps({"propertyValues": {}}), 200, {"Content-Type": "application/json"})
    
    item = items[0]
    
    # 4. Format response (TwinMaker-compatible for last entry)
    property_values = {}
    for prop_name in selected_properties:
        if prop_name in item:
            property_values[prop_name] = {
                "propertyReference": {
                    "entityId": query_params.get("entityId", ""),
                    "componentName": query_params.get("componentName", ""),
                    "propertyName": prop_name
                },
                "propertyValue": {"doubleValue": item[prop_name]}
            }
    
    return (json.dumps({"propertyValues": property_values}), 200, {"Content-Type": "application/json"})
```

---

## 5. Deployment Requirements

### 5.1 GCP Resources

| Resource | Purpose |
|----------|---------|
| Cloud Functions (2nd gen) | Hosts both hot-reader functions |
| HTTP Trigger | Exposes functions as HTTP endpoints |
| Firestore access | Read access to L3 Hot Storage |

### 5.2 Environment Variables

```yaml
INTER_CLOUD_TOKEN: "{shared_secret_from_config_inter_cloud.json}"
FIRESTORE_COLLECTION: "hot_storage"
```

### 5.3 Firestore Index Requirements

Create composite index for efficient querying:
```
Collection: hot_storage
Fields: iotDeviceId (ASC), id (DESC)
```

### 5.4 Deployer Changes Required

Add to `src/providers/gcp/deployer_layers/layer_3_storage.py`:
- `deploy_gcp_hot_reader()`
- `deploy_gcp_hot_reader_last_entry()`
- Save Function URLs to `config_inter_cloud.json`

---

## 6. Test Cases

| # | Test Case | Description |
|---|-----------|-------------|
| G1 | `test_gcp_hot_reader_valid_token` | Valid token → returns data |
| G2 | `test_gcp_hot_reader_invalid_token` | Invalid token → 401 |
| G3 | `test_gcp_hot_reader_missing_token` | No token → 401 |
| G4 | `test_gcp_hot_reader_time_range` | Returns data within time range |
| G5 | `test_gcp_hot_reader_empty_range` | No data in range → empty response |
| G6 | `test_gcp_hot_reader_last_entry_returns_latest` | Returns only newest record |
| G7 | `test_gcp_hot_reader_last_entry_no_data` | No data → empty propertyValues |

---

## 7. Estimated Effort

| Task | Estimate |
|------|----------|
| GCP Cloud Function implementation | 2-3 hours |
| Deployer integration | 2-3 hours |
| Unit tests | 2-3 hours |
| Firestore index setup | 30 min |
| Integration testing | 1-2 hours |
| **Total** | **8-12 hours** |

---

## 8. Future Considerations

### 8.1 Performance Optimization
- Consider Firestore's 1MB document limit for large datasets
- May need pagination for very large time ranges

### 8.2 Cost Optimization
- Firestore charges per document read
- Use targeted queries with proper indexes to minimize reads
