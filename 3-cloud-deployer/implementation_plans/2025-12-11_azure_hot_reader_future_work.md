# Azure Hot Reader Multi-Cloud Implementation Plan (Future Work)

> **Status:** 📝 Future Work  
> **Parent Plan:** [2025-12-10_22-45_hot_reader_multi_cloud.md](./2025-12-10_22-45_hot_reader_multi_cloud.md)  
> **Priority:** After AWS implementation is complete

---

## 1. Executive Summary

This document outlines the future implementation of Azure Hot Reader functions to enable cross-cloud data access when Azure Cosmos DB is the L3 Hot Storage provider.

### Scope

| Component | Description |
|-----------|-------------|
| `azure-hot-reader` | Azure Function that reads time-series **history** from Cosmos DB |
| `azure-hot-reader-last-entry` | Azure Function that reads **current/latest** value from Cosmos DB |

### Authentication

**MVP Approach:** Use `X-Inter-Cloud-Token` header only (same as AWS implementation).

---

## 2. Architecture

### When Azure L3 Hot Reader Is Needed

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO: L4 (any cloud) needs data from L3 Azure Cosmos DB               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   L4: AWS/Azure/GCP                        L3: Azure                        │
│   ┌─────────────────────┐                 ┌─────────────────────┐          │
│   │  Hot Requester      │     HTTPS       │  Azure Cosmos DB    │          │
│   │  (Lambda/Function)  │─────POST───────►│                     │          │
│   │                     │  X-Inter-Cloud  │  ┌───────────────┐  │          │
│   │  Determines L3 is   │     -Token      │  │ Hot Reader    │  │          │
│   │  on different cloud │                 │  │ (Azure Func)  │  │          │
│   └─────────────────────┘                 │  └───────────────┘  │          │
│                                           └─────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Functions to Implement

### 3.1 azure-hot-reader (Time-Series History)

**Purpose:** Returns data for a time range (used by graphs, charts, trend panels).

```python
# Azure Function: hot-reader (HTTP Trigger)
# File: src/providers/azure/functions/hot-reader/__init__.py

import azure.functions as func
from azure.cosmos import CosmosClient
import json
import os

# Fail-fast environment variable validation
def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value

# Required at startup
COSMOS_ENDPOINT = _require_env("COSMOS_ENDPOINT")
COSMOS_KEY = _require_env("COSMOS_KEY")
COSMOS_DATABASE = _require_env("COSMOS_DATABASE")
COSMOS_CONTAINER = _require_env("COSMOS_CONTAINER")
EXPECTED_TOKEN = _require_env("INTER_CLOUD_TOKEN")

# Cosmos client (reusable across invocations)
cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
container = cosmos_client.get_database_client(COSMOS_DATABASE).get_container_client(COSMOS_CONTAINER)

def main(req: func.HttpRequest) -> func.HttpResponse:
    # 1. Validate X-Inter-Cloud-Token
    token = req.headers.get("X-Inter-Cloud-Token", "").strip()
    if not token or token != EXPECTED_TOKEN:
        return func.HttpResponse("Unauthorized", status_code=401)
    
    # 2. Parse query parameters from body
    try:
        body = req.get_json()
        query_params = body.get("payload", {})
    except ValueError:
        return func.HttpResponse("Invalid JSON", status_code=400)
    
    # 3. Query Cosmos DB (TIME RANGE)
    device_id = query_params.get("iotDeviceId")
    start_time = query_params.get("startTime")
    end_time = query_params.get("endTime")
    selected_properties = query_params.get("selectedProperties", [])
    
    query = f"""
        SELECT * FROM c 
        WHERE c.iotDeviceId = @deviceId 
        AND c.id >= @startTime 
        AND c.id <= @endTime
    """
    parameters = [
        {"name": "@deviceId", "value": device_id},
        {"name": "@startTime", "value": start_time},
        {"name": "@endTime", "value": end_time}
    ]
    items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
    
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
    
    return func.HttpResponse(
        json.dumps({"propertyValues": property_values}),
        mimetype="application/json",
        status_code=200
    )
```

### 3.2 azure-hot-reader-last-entry (Current Value)

**Purpose:** Returns only the latest/current value (used by gauges, stat panels, live displays).

```python
# Azure Function: hot-reader-last-entry (HTTP Trigger)
# File: src/providers/azure/functions/hot-reader-last-entry/__init__.py

import azure.functions as func
from azure.cosmos import CosmosClient
import json
import os

def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value

COSMOS_ENDPOINT = _require_env("COSMOS_ENDPOINT")
COSMOS_KEY = _require_env("COSMOS_KEY")
COSMOS_DATABASE = _require_env("COSMOS_DATABASE")
COSMOS_CONTAINER = _require_env("COSMOS_CONTAINER")
EXPECTED_TOKEN = _require_env("INTER_CLOUD_TOKEN")

cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
container = cosmos_client.get_database_client(COSMOS_DATABASE).get_container_client(COSMOS_CONTAINER)

def main(req: func.HttpRequest) -> func.HttpResponse:
    # 1. Validate X-Inter-Cloud-Token
    token = req.headers.get("X-Inter-Cloud-Token", "").strip()
    if not token or token != EXPECTED_TOKEN:
        return func.HttpResponse("Unauthorized", status_code=401)
    
    # 2. Parse query parameters
    try:
        body = req.get_json()
        query_params = body.get("payload", {})
    except ValueError:
        return func.HttpResponse("Invalid JSON", status_code=400)
    
    device_id = query_params.get("iotDeviceId")
    selected_properties = query_params.get("selectedProperties", [])
    
    # 3. Query Cosmos DB (LATEST ENTRY ONLY)
    query = """
        SELECT TOP 1 * FROM c 
        WHERE c.iotDeviceId = @deviceId 
        ORDER BY c.id DESC
    """
    parameters = [{"name": "@deviceId", "value": device_id}]
    items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
    
    if not items:
        return func.HttpResponse(json.dumps({"propertyValues": {}}), mimetype="application/json")
    
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
    
    return func.HttpResponse(
        json.dumps({"propertyValues": property_values}),
        mimetype="application/json",
        status_code=200
    )
```

---

## 4. Deployment Requirements

### 4.1 Azure Resources

| Resource | Purpose |
|----------|---------|
| Azure Function App | Hosts both hot-reader functions |
| HTTP Trigger | Exposes functions as HTTP endpoints |
| Cosmos DB connection | Read access to L3 Hot Storage |

### 4.2 Environment Variables

```yaml
COSMOS_ENDPOINT: "https://{account}.documents.azure.com:443/"
COSMOS_KEY: "{primary_key}"
COSMOS_DATABASE: "digital_twin_db"
COSMOS_CONTAINER: "hot_storage"
INTER_CLOUD_TOKEN: "{shared_secret_from_config_inter_cloud.json}"
```

### 4.3 Deployer Changes Required

Add to `src/providers/azure/deployer_layers/layer_3_storage.py`:
- `deploy_azure_hot_reader()`
- `deploy_azure_hot_reader_last_entry()`
- Save Function URLs to `config_inter_cloud.json`

---

## 5. Test Cases

| # | Test Case | Description |
|---|-----------|-------------|
| A1 | `test_azure_hot_reader_valid_token` | Valid token → returns data |
| A2 | `test_azure_hot_reader_invalid_token` | Invalid token → 401 |
| A3 | `test_azure_hot_reader_missing_token` | No token → 401 |
| A4 | `test_azure_hot_reader_time_range` | Returns data within time range |
| A5 | `test_azure_hot_reader_empty_range` | No data in range → empty response |
| A6 | `test_azure_hot_reader_last_entry_returns_latest` | Returns only newest record |
| A7 | `test_azure_hot_reader_last_entry_no_data` | No data → empty propertyValues |

---

## 6. Estimated Effort

| Task | Estimate |
|------|----------|
| Azure Function implementation | 2-3 hours |
| Deployer integration | 2-3 hours |
| Unit tests | 2-3 hours |
| Integration testing | 1-2 hours |
| **Total** | **7-11 hours** |
