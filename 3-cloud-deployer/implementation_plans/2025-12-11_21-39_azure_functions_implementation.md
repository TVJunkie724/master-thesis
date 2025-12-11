# Azure Deployer: Azure Functions Implementation Plan

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Complete AWS → Azure Function Mapping](#2-complete-aws--azure-function-mapping)
3. [Azure Service Equivalents](#3-azure-service-equivalents)
4. [Azure Functions Python v2 Patterns](#4-azure-functions-python-v2-patterns)
5. [Directory Structure](#5-proposed-directory-structure)
6. [Phased Implementation](#6-phased-implementation)
7. [Test Strategy](#7-test-strategy)
8. [Verification Checklist](#8-verification-checklist)

---

## 1. Executive Summary

### The Problem
AWS Lambda functions are fully implemented (17 functions). Azure only has stubs.

### The Solution
Create Azure Functions (Python v2) mirroring the AWS Lambda structure, starting with the shared module and L1/L2 functions.

### Impact
When complete, the deployer will support Azure as a first-class deployment target with full multi-cloud interoperability.

### Reference
- **Source of Truth:** AWS docs roadmap (`docs/docs-aws-deployment.html`)
- **Azure Services:** Azure IoT Hub, Azure Functions, Cosmos DB, Blob Storage (no API Management)

---

## 2. Complete AWS → Azure Function Mapping

### AWS Lambda Folder: `src/providers/aws/lambda_functions/`
### Azure Functions Folder: `src/providers/azure/azure_functions/`

| # | AWS Lambda | Azure Equivalent | Layer | Trigger Type | Purpose |
|---|------------|------------------|-------|--------------|---------|
| 1 | `_shared/inter_cloud.py` | `_shared/inter_cloud.py` | Shared | N/A | HTTP POST with retry, token validation |
| 2 | `dispatcher` | `dispatcher` | L1 | Event Grid (IoT Hub) | Route MQTT to processor/connector |
| 3 | `connector` | `connector` | L1 | HTTP (invoke from dispatcher) | Bridge L1→L2 cross-cloud |
| 4 | `ingestion` | `ingestion` | L0 | HTTP Trigger | Receive from remote connector |
| 5 | `default-processor` | `default-processor` | L2 | HTTP (invoke by ingestion) | Default processing logic |
| 6 | `processor_wrapper` | `processor_wrapper` | L2 | HTTP (invoke by ingestion) | Merge user logic + invoke persister |
| 7 | `persister` | `persister` | L2 | HTTP (invoke by processor) | Write to Cosmos DB or remote |
| 8 | `event-checker` | `event-checker` | L2 | HTTP (Optional) | Evaluate thresholds, trigger workflow |
| 9 | `hot-writer` | `hot-writer` | L0 | HTTP Trigger | Receive from remote persister, write Cosmos DB |
| 10 | `hot-reader` | `hot-reader` | L3 | HTTP Trigger | Query Cosmos DB for time-range |
| 11 | `hot-reader-last-entry` | `hot-reader-last-entry` | L3 | HTTP Trigger | Query last entry per device |
| 12 | `hot-to-cold-mover` | `hot-to-cold-mover` | L3 | Timer Trigger | Move Cosmos DB → Blob Cool |
| 13 | `cold-writer` | `cold-writer` | L0 | HTTP Trigger | Receive chunks, write Blob Cool |
| 14 | `cold-to-archive-mover` | `cold-to-archive-mover` | L3 | Timer Trigger | Move Blob Cool → Archive |
| 15 | `archive-writer` | `archive-writer` | L0 | HTTP Trigger | Receive data, write Blob Archive |
| 16 | `digital-twin-data-connector` | `digital-twin-data-connector` | L4 | HTTP (invoke by ADT) | Route to hot-reader |
| 17 | `digital-twin-data-connector-last-entry` | `digital-twin-data-connector-last-entry` | L4 | HTTP (invoke by ADT) | Route to hot-reader-last-entry |

---

## 3. Azure Service Equivalents

| AWS Service | Azure Equivalent | Notes |
|-------------|------------------|-------|
| Lambda | Azure Functions | Python v2 programming model |
| Lambda Function URL | Azure Functions HTTP Trigger | No API Management needed |
| DynamoDB | Cosmos DB for NoSQL | Hot storage |
| S3 (STANDARD_IA) | Blob Storage (Cool tier) | Cold storage |
| S3 (DEEP_ARCHIVE) | Blob Storage (Archive tier) | Archive storage |
| EventBridge (Schedule) | Timer Trigger | `@app.timer_trigger()` |
| IoT Core Rule | Event Grid (IoT Hub events) | Route telemetry to functions |
| Step Functions | Logic Apps | Workflow orchestration |
| IoT TwinMaker | Azure Digital Twins | L4 management |

---

## 4. Azure Functions Python v2 Patterns

### HTTP Trigger (replaces Lambda Function URL)
```python
import azure.functions as func

app = func.FunctionApp()

@app.route(route="ingestion", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingestion(req: func.HttpRequest) -> func.HttpResponse:
    token = req.headers.get("x-inter-cloud-token")
    if token != os.environ["INTER_CLOUD_TOKEN"]:
        return func.HttpResponse("Unauthorized", status_code=401)
    return func.HttpResponse(json.dumps({"status": "ok"}), mimetype="application/json")
```

### Timer Trigger (replaces EventBridge scheduled rule)
```python
@app.timer_trigger(schedule="0 0 0 * * *", arg_name="timer", run_on_startup=False)
def hot_to_cold_mover(timer: func.TimerRequest) -> None:
    pass  # Run daily at midnight UTC
```

---

## 5. Proposed Directory Structure

```
src/providers/azure/
├── __init__.py
├── provider.py              # Existing
├── deployer_strategy.py     # Existing
├── azure_functions/         # NEW
│   ├── __init__.py
│   ├── _shared/
│   │   ├── __init__.py
│   │   └── inter_cloud.py
│   ├── dispatcher/
│   ├── connector/
│   ├── ingestion/
│   ├── persister/
│   ├── processor_wrapper/
│   ├── default-processor/
│   ├── event-checker/
│   ├── hot-writer/
│   ├── hot-reader/
│   ├── hot-reader-last-entry/
│   ├── hot-to-cold-mover/
│   ├── cold-writer/
│   ├── cold-to-archive-mover/
│   ├── archive-writer/
│   ├── digital-twin-data-connector/
│   └── digital-twin-data-connector-last-entry/
└── layers/
```

---

## 6. Phased Implementation

### Phase 1: Foundation + L1/L2
| Step | Function | Priority | Status |
|------|----------|----------|--------|
| 1.1 | `_shared/inter_cloud.py` | Required | [x] |
| 1.2 | `dispatcher` | Required | [x] |
| 1.3 | `connector` | Multi-cloud | [x] |
| 1.4 | `ingestion` | Multi-cloud | [x] |
| 1.5 | `processor_wrapper` | Required | [x] |
| 1.6 | `default-processor` | Required | [x] |
| 1.7 | `persister` | Required | [x] |
| 1.8 | `event-checker` | Optional | [x] |

### Phase 2: L3 Storage Functions
| Step | Function | Priority | Status |
|------|----------|----------|--------|
| 2.1 | `hot-writer` | Multi-cloud | [x] |
| 2.2 | `hot-reader` | Required | [x] |
| 2.3 | `hot-reader-last-entry` | Required | [x] |
| 2.4 | `hot-to-cold-mover` | Required | [x] |
| 2.5 | `cold-writer` | Multi-cloud | [x] |
| 2.6 | `cold-to-archive-mover` | Required | [x] |
| 2.7 | `archive-writer` | Multi-cloud | [x] |

### Phase 3: L4 Digital Twin + Tests
| Step | Function | Priority | Status |
|------|----------|----------|--------|
| 3.1 | `digital-twin-data-connector` | Required | [x] |
| 3.2 | `digital-twin-data-connector-last-entry` | Required | [x] |
| 3.3 | All Azure unit tests | Required | [x] |

---

## 7. Test Strategy

### Azure Test Files to Create

| Test File | Functions Tested |
|-----------|------------------|
| `tests/unit/azure_functions/test_azure_multi_cloud.py` | ingestion, hot-writer, connector |
| `tests/unit/azure_functions/test_azure_movers.py` | movers |
| `tests/unit/azure_functions/test_azure_persister.py` | persister |
| `tests/unit/azure_functions/test_azure_event_checker.py` | event-checker |
| `tests/unit/azure_functions/test_azure_inter_cloud.py` | _shared module |

---

## 8. Verification Checklist

- [ ] All existing AWS tests pass
- [ ] Phase 1 Azure functions created
- [ ] Phase 1 Azure tests pass
- [ ] Documentation updated
