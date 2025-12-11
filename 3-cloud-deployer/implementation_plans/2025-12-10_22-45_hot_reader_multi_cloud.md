# Digital Twin Data Connector/Reader Multi-Cloud Adaptations

---

## Table of Contents

**Quick Start:**
- [Hot Reader vs Digital Twin Data Connector](#quick-reference-hot-reader-vs-digital-twin-data-connector) ← Start here!

**Core Plan:**
1. [Executive Summary](#1-executive-summary)
2. [Architecture Diagrams](#2-architecture-diagrams)
3. [Detailed Changes](#3-detailed-changes)
4. [Comprehensive Test Cases](#4-comprehensive-test-cases)
5. [Documentation Updates](#5-documentation-updates)
6. [Implementation Phases](#6-implementation-phases)
7. [Verification Plan](#7-verification-plan)
8. [Codebase Gap Audit](#8-codebase-gap-audit-critical-findings)

**Future Work:**
9. [Azure/GCP L4/L5 Scenarios](#9-future-work-azure-l4l5-provider-scenarios)
10. [Expanded Test Cases](#10-expanded-test-cases)

**Appendices:**
11. [Documentation Updates Required](#11-documentation-updates-required)
12. [Updated Implementation Phases](#12-updated-implementation-phases)
13. [Verification Plan Summary](#13-verification-plan-summary)
14. [Out of Scope](#14-out-of-scope)

**Related Documents:**
- [Azure Hot Reader Future Work](./2025-12-11_azure_hot_reader_future_work.md)
- [GCP Hot Reader Future Work](./2025-12-11_gcp_hot_reader_future_work.md)

---

## Quick Reference: Hot Reader vs Digital Twin Data Connector

> [!IMPORTANT]
> **This explains when each function is needed based on single-cloud vs multi-cloud scenarios.**

### Definitions

| Function | Purpose | Location |
|----------|---------|----------|
| **Hot Reader** | Reads data from local hot storage (DynamoDB, Cosmos DB, Firestore) | L3 cloud (where data lives) |
| **Digital Twin Data Connector** | Routes requests to local OR remote Hot Reader | L4 cloud (where TwinMaker/ADT lives) |

### Single-Cloud Scenario (L3 = L4 same cloud)

```
┌──────────────────────────────────────────────────────────────────────┐
│  SINGLE-CLOUD: L3 and L4 on same cloud                               │
│                                                                      │
│   L4: TwinMaker              L3: DynamoDB                            │
│   ┌─────────────────┐        ┌─────────────────┐                     │
│   │  Component      │ invoke │  hot-reader     │                     │
│   │  Connector      │───────►│  (Lambda)       │                     │
│   └─────────────────┘        └─────────────────┘                     │
│                                                                      │
│   ✅ Hot Reader needed (TwinMaker calls it directly)                │
│   ❌ Digital Twin Data Connector NOT needed (no routing required)   │
└──────────────────────────────────────────────────────────────────────┘
```

### Multi-Cloud Scenario (L3 ≠ L4 different clouds)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  MULTI-CLOUD: L3 and L4 on different clouds                                    │
│                                                                                │
│   L4: AWS TwinMaker           L4: AWS                       L3: Azure          │
│   ┌─────────────────┐        ┌───────────────────────┐     ┌───────────────┐   │
│   │  Component      │ invoke │  digital-twin-data-   │HTTP │  Hot Reader   │   │
│   │  Connector      │───────►│  connector (Lambda)   │POST►│ (Azure Func)  │   │
│   └─────────────────┘        └───────────────────────┘     └───────────────┘   │
│                                                                                │
│   ✅ Hot Reader needed (on L3 cloud - reads local data)                       │
│   ✅ Digital Twin Data Connector needed (on L4 cloud - routes to L3)          │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Why "Digital Twin Data Connector"?

> [!NOTE]
> **This function exists specifically as an adapter for Digital Twin services** (TwinMaker, Azure Digital Twins, etc.) which can only invoke local functions, not make HTTP calls to external URLs. It bridges the gap between the Digital Twin service and potentially remote Hot Storage.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                  DIGITAL TWIN DATA CONNECTOR ARCHITECTURE                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  L4: Any Cloud (AWS/Azure/GCP)              L3: Any Cloud                  │
│  ┌──────────────────────────┐              ┌────────────────────────┐      │
│  │ Digital Twin Service     │   invoke     │                        │      │
│  │ (TwinMaker / ADT / etc)  │─────────────►│  digital-twin-data-    │      │
│  │                          │              │  connector             │      │
│  └──────────────────────────┘              │  (routes to local/     │      │
│                                            │   remote hot-reader)   │      │
│                                            └───────────┬────────────┘      │
│                                                        │                   │
│                          ┌─────────────────────────────┼───────────────────┤
│                          │ If L3=L4: invoke            │ If L3≠L4: HTTP    │
│                          ▼                             ▼                   │
│               ┌─────────────────┐           ┌─────────────────┐            │
│               │  hot-reader     │           │  hot-reader     │ (remote)   │
│               │  (local Lambda) │           │  (Function URL) │            │
│               └─────────────────┘           └─────────────────┘            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Summary Table

| Scenario | Hot Reader | Digital Twin Data Connector |
|----------|------------|------------------|
| **Single-cloud** (L3=L4 same cloud) | ✅ Yes (TwinMaker calls it directly) | ❌ No |
| **Multi-cloud** (L3≠L4 different clouds) | ✅ Yes (on L3 cloud) | ✅ Yes (on L4 cloud, routes to L3) |
| **L5 Direct (Pattern B)** | ✅ Yes (via Function URL) | ❌ No (Grafana calls Hot Reader directly) |

---

## 1. Executive Summary

### The Problem
Current Hot Reader functions read directly from local DynamoDB with no multi-cloud awareness:
1. **No cross-cloud read path**: Unlike Writer (for writes), there's no Reader endpoint for cross-cloud data access
2. **`REMOTE_READER_URL` specified but unused**: `technical_specs.md` defines this but it's never implemented
3. **L4/L5 cannot access remote L3 Hot Storage**: If TwinMaker (AWS) is on different cloud than Hot Storage, queries fail

### Key Research Findings

| Cloud | L4 Service | Data Access Pattern | L5 (Grafana) Pattern |
|-------|------------|---------------------|---------------------|
| **AWS** | TwinMaker | Custom Lambda connector queries DynamoDB | TwinMaker plugin invokes Lambda |
| **Azure** | Digital Twins | REST API with OAuth2 (NO Lambda equivalent) | ADX historization → ADX Grafana plugin |
| **GCP** | *(None)* | N/A - excluded from L4 per user decision | Self-hosted Grafana + JSON API plugin |

> [!IMPORTANT]
> **AWS TwinMaker REQUIRES a Lambda connector** for DynamoDB data. There is NO built-in connector like SiteWise. Our `hot-reader` Lambda IS necessary and correct.

> [!NOTE]
> **Azure uses a fundamentally different pattern** - Digital Twins historizes to Azure Data Explorer, and Grafana connects to ADX. This means L4/L5 multi-cloud for Azure requires different implementation (future work).

### The Solution
1. **Keep `hot-reader` as-is**: Reads data directly from local DynamoDB (already works)
2. **Add Function URL to Hot Reader**: Enables remote access via HTTP 
3. **Create NEW `digital-twin-data-connector` Lambda**: Invoked by TwinMaker, routes to local or remote Hot Reader
4. **Update deployers**: Conditional deployment and env var injection
5. **Comprehensive tests**: 80+ test cases covering all scenarios

### Provider Compatibility Matrix

> [!IMPORTANT]
> **Key Discovery**: The **L5 → Hot Reader Direct** pattern is **universal**! Any Grafana instance (AWS, Azure, GCP, or self-hosted) can call any Hot Reader HTTP endpoint using the Infinity plugin with `X-Inter-Cloud-Token` header. This bypasses L4 entirely for data visualization.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE L3/L4/L5 MULTI-CLOUD SUPPORT MATRIX                                   │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│ PATTERN A: STANDARD DIGITAL TWIN FLOW (L5 → L4 → L3)                                                       │
│ Use when: Need L4 features (3D scene viewer, entity relationships, component types)                        │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│                                                                                                             │
│   L3 Hot Provider     L4 Provider        L5 Provider          How It Works                                 │
│   ────────────────    ──────────────     ─────────────────    ──────────────────────────────────────────── │
│   AWS (DynamoDB)      AWS (TwinMaker)    AWS (M.Grafana)      ✅ Native: TwinMaker plugin (existing)        │
│   Azure (Cosmos)      AWS (TwinMaker)    AWS (M.Grafana)      🔶 This plan: Digital Twin Data Connector→Azure Hot Reader  │
│   GCP (Firestore)     AWS (TwinMaker)    AWS (M.Grafana)      🔶 This plan: Digital Twin Data Connector→GCP Hot Reader    │
│   Azure (Cosmos)      Azure (ADT)        Azure (M.Grafana)    📝 Future: Infinity→ADT Query API (OAuth2)    │
│   AWS (DynamoDB)      Azure (ADT)        Azure (M.Grafana)    📝 Future: ADT calls AWS Hot Reader           │
│                                                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│ PATTERN B: L5 DIRECT TO L3 HOT READER ⭐ UNIVERSAL SOLUTION (Bypasses L4!)                                 │
│ Use when: Need simple time-series data visualization without L4 features                                   │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│                                                                                                             │
│   L3 Hot Storage      Hot Reader Endpoint           L5 Grafana          Status                             │
│   ────────────────    ────────────────────────      ──────────────────  ────────────────────────────────── │
│   AWS (DynamoDB)      AWS Lambda Function URL       AWS M.Grafana       🔶 THIS PLAN (Hot Reader created)   │
│   AWS (DynamoDB)      AWS Lambda Function URL       Azure M.Grafana     🔶 THIS PLAN (same Hot Reader)      │
│   AWS (DynamoDB)      AWS Lambda Function URL       GCP Self-hosted     🔶 THIS PLAN (same Hot Reader)      │
│   AWS (DynamoDB)      AWS Lambda Function URL       Grafana Cloud       🔶 THIS PLAN (same Hot Reader)      │
│   ─────────────────────────────────────────────────────────────────────────────────────────────────────────│
│   Azure (Cosmos DB)   Azure Function HTTP Trigger   AWS M.Grafana       📝 FUTURE (Azure Hot Reader needed) │
│   Azure (Cosmos DB)   Azure Function HTTP Trigger   Azure M.Grafana     📝 FUTURE (Azure Hot Reader needed) │
│   Azure (Cosmos DB)   Azure Function HTTP Trigger   GCP Self-hosted     📝 FUTURE (Azure Hot Reader needed) │
│   Azure (Cosmos DB)   Azure Function HTTP Trigger   Grafana Cloud       📝 FUTURE (Azure Hot Reader needed) │
│   ─────────────────────────────────────────────────────────────────────────────────────────────────────────│
│   GCP (Firestore)     GCP Cloud Function HTTP       AWS M.Grafana       📝 FUTURE (GCP Hot Reader needed)   │
│   GCP (Firestore)     GCP Cloud Function HTTP       Azure M.Grafana     📝 FUTURE (GCP Hot Reader needed)   │
│   GCP (Firestore)     GCP Cloud Function HTTP       GCP Self-hosted     📝 FUTURE (GCP Hot Reader needed)   │
│   GCP (Firestore)     GCP Cloud Function HTTP       Grafana Cloud       📝 FUTURE (GCP Hot Reader needed)   │
│                                                                                                             │
│   🔶 THIS PLAN: Creates AWS Hot Reader (Lambda + Function URL) - enables ALL 4 AWS L3 scenarios           │
│   📝 FUTURE: Azure/GCP Hot Readers follow IDENTICAL pattern (just different cloud function)                │
│   * All use same auth: Infinity plugin + API Key (X-Inter-Cloud-Token header)                              │
│   * All use same response format: TwinMaker-compatible JSON                                                 │
│                                                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│ PATTERN C: L4 ≠ L5 CLOUD WITH L4 FEATURES (Cross-cloud L4 access)                                          │
│ Use when: Need L4 features but L5 is on different cloud from L4                                            │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│                                                                                                             │
│   L4 Provider         L5 Provider          Solution                                                         │
│   ──────────────────  ───────────────────  ──────────────────────────────────────────────────────────────  │
│   AWS (TwinMaker)     Azure M.Grafana      ✅ Infinity + AWS Sigv4 → TwinMaker REST API                     │
│   AWS (TwinMaker)     GCP Self-hosted      ✅ Infinity + AWS Sigv4 → TwinMaker REST API                     │
│   Azure (ADT)         AWS M.Grafana        📝 Infinity + Azure OAuth2 → ADT Query API                       │
│   Azure (ADT)         GCP Self-hosted      📝 Infinity + Azure OAuth2 → ADT Query API                       │
│                                                                                                             │
│   * TwinMaker plugin only works on AWS M.Grafana. Other Grafana uses Infinity + Sigv4.                     │
│   * Limitation: No 3D Scene Viewer panel without TwinMaker plugin.                                         │
│                                                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│ SELF-HOSTED GRAFANA L5 OPTIONS                                                                              │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│                                                                                                             │
│   Hosting Location    Plugin Access        Best For                                                         │
│   ────────────────    ─────────────────    ────────────────────────────────────────────────────────────────│
│   AWS EC2             Full (TwinMaker ✅)  AWS-centric with full L4 features                                │
│   Azure VM            Full (manual install) Azure-centric, install TwinMaker plugin manually                │
│   GCP Compute Engine  Full (manual install) GCP-centric, install TwinMaker plugin manually                  │
│   Grafana Cloud       Full ecosystem       Zero maintenance, all plugins available                          │
│                                                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│ NOT SUPPORTED                                                                                               │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│   *                   GCP (L4)             ❌ GCP has no native L4 digital twin service                     │
│                                                                                                             │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│ LEGEND                                                                                                      │
│ ═══════════════════════════════════════════════════════════════════════════════════════════════════════════ │
│   ✅ Works now  |  🔶 This plan  |  📝 Future (documented)  |  ⭐ Universal pattern (recommended)          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

> [!TIP]
> **Pattern B is the recommended solution for cross-cloud L5!** All 12 L3/L5 combinations work via Infinity plugin + `X-Inter-Cloud-Token`. See Section 9.9 for configuration details.

---

## 2. Architecture Diagrams

### Current State (AWS-Only)
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     CURRENT: AWS L4 → AWS L3 (Single Cloud)                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  L5: Grafana        L4: TwinMaker                L3: DynamoDB               │
│  ┌─────────────┐    ┌─────────────┐              ┌─────────────┐            │
│  │  Dashboard  │───▶│  Workspace  │───Lambda────▶│  Hot Table  │            │
│  └─────────────┘    └─────────────┘   invoke     └─────────────┘            │
│                            │                           ▲                     │
│                            │                           │                     │
│                            ▼                           │                     │
│                     ┌─────────────┐                   │                     │
│                     │ hot-reader  │───boto3──────────┘                      │
│                     │ Lambda      │   (direct)                              │
│                     └─────────────┘                                         │
│                                                                              │
│  ✅ Works - all components on AWS                                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Target State (Multi-Cloud)
```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                TARGET: AWS L4 → Azure/GCP L3 (Multi-Cloud)                                │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  AWS CLOUD                                    AZURE/GCP CLOUD                            │
│  ┌────────────────────────────────────┐      ┌────────────────────────────────────┐     │
│  │                                    │      │                                    │     │
│  │  L5: Grafana      L4: TwinMaker    │      │  L3: Cosmos DB / Firestore         │     │
│  │  ┌─────────┐     ┌─────────┐       │      │  ┌─────────────────────────┐       │     │
│  │  │Dashboard│────▶│Workspace│       │      │  │    Hot Data Container   │       │     │
│  │  └─────────┘     └────┬────┘       │      │  └────────────▲────────────┘       │     │
│  │                       │            │      │               │                    │     │
│  │                  Lambda invoke     │      │          SDK query                 │     │
│  │                       │            │      │               │                    │     │
│  │                       ▼            │      │  ┌────────────┴────────────┐       │     │
│  │              ┌────────────────┐    │      │  │      Hot Reader         │       │     │
│  │              │ Digital Twin Data Connector  │    │      │  │  (Azure Func / Cloud Fn)│       │     │
│  │              │ Lambda ✅      │    │      │  │  - Token validation     │       │     │
│  │              │                │    │      │  │  - Query local storage  │       │     │
│  │              │ _is_multi...() │    │      │  └────────────▲────────────┘       │     │
│  │              │    ↓           │    │      │               │                    │     │
│  │              │ POST to remote │───────────────HTTP POST───┘                    │     │
│  │              └────────────────┘    │      │  X-Inter-Cloud-Token               │     │
│  │                                    │      │                                    │     │
│  └────────────────────────────────────┘      └────────────────────────────────────┘     │
│                                                                                          │
│  ✅ = Multi-cloud aware: routes to local DynamoDB OR remote Hot Reader based on config  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Changes

### 3.1 Lambda Function Overview

| Function | Purpose | Change |
|----------|---------|--------|
| `hot-reader/` | Reads data directly from local DynamoDB | **KEEP** - Add Function URL + token validation |
| `hot-reader-last-entry/` | Reads last entry from DynamoDB | **KEEP** - Add Function URL + token validation |
| `digital-twin-data-connector/` | TwinMaker connector - routes to local or remote Hot Reader | **NEW** |
| `digital-twin-data-connector-last-entry/` | Same for "last entry" queries | **NEW** |

### 3.2 AWS Lambda Functions

#### [MODIFY] hot-reader/lambda_function.py
Add HTTP request handling for cross-cloud access:
```python
# NEW: Token validation for HTTP requests
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

def _is_http_request(event: dict) -> bool:
    """Detect if invoked via Function URL vs direct Lambda invoke."""
    return "requestContext" in event and "http" in event.get("requestContext", {})

def _validate_token(event: dict) -> bool:
    """Validate X-Inter-Cloud-Token header."""
    headers = event.get("headers", {})
    token = headers.get("x-inter-cloud-token", "")
    return token == INTER_CLOUD_TOKEN
```

#### [NEW] digital-twin-data-connector/lambda_function.py
New Lambda invoked by TwinMaker, routes to local or remote Hot Reader:
```python
# Multi-cloud environment variables
REMOTE_READER_URL = os.environ.get("REMOTE_READER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()
LOCAL_HOT_READER_NAME = _require_env("LOCAL_HOT_READER_NAME")

def _is_multi_cloud_hot_storage() -> bool:
    """Dual validation: URL present AND providers differ."""
    if not REMOTE_READER_URL:
        return False
    providers = DIGITAL_TWIN_INFO.get("config_providers", {})
    l3_hot = providers.get("layer_3_hot_provider", "aws")
    l4 = providers.get("layer_4_provider", "aws")
    return l3_hot != l4

def _invoke_local_hot_reader(event: dict) -> dict:
    """Direct Lambda invocation to local hot-reader."""
    response = lambda_client.invoke(
        FunctionName=LOCAL_HOT_READER_NAME,
        Payload=json.dumps(event)
    )
    return json.loads(response["Payload"].read())

def _query_remote_hot_reader(event: dict) -> dict:
    """POST to remote Hot Reader with retry + exponential backoff."""
    # Same pattern as Connector → Ingestion
    ...
```

### 3.3 Deployer Updates

#### [MODIFY] layer_3_storage.py
- Add `create_hot_reader_function_url()` - creates Function URL for hot-reader 
- Add `create_dt_data_connector_iam_role()` - new IAM role
- Add `create_dt_data_connector_lambda_function()` - new Lambda
- Inject `REMOTE_READER_URL`, `INTER_CLOUD_TOKEN`, `LOCAL_HOT_READER_NAME`
- Pattern identical to Writer/Cold Writer/Archive Writer

#### [MODIFY] l3_adapter.py
- Always deploy Hot Reader (with Function URL for cross-cloud access)
- Conditionally deploy Digital Twin Data Connector when L3 ≠ L4
- Save Function URL to `config_inter_cloud.json`

#### [MODIFY] naming.py
- Add `dt_data_connector_lambda_function()` - new
- Add `dt_data_connector_iam_role()` - new
- Add `dt_data_connector_last_entry_*` - new

---

## 4. Comprehensive Test Cases

### 4.1 Digital Twin Data Connector Unit Tests (NEW)

| # | Test Case | Description |
|---|-----------|-------------|
| 1 | `test_is_multi_cloud_no_url_returns_false` | No REMOTE_READER_URL → single cloud |
| 2 | `test_is_multi_cloud_empty_url_returns_false` | Empty/whitespace URL → single cloud |
| 3 | `test_is_multi_cloud_same_provider_returns_false` | L3=aws, L4=aws → single cloud |
| 4 | `test_is_multi_cloud_different_provider_returns_true` | L3=azure, L4=aws → multi-cloud |
| 5 | `test_is_multi_cloud_missing_config_providers_raises` | No config_providers → ConfigurationError |
| 6 | `test_query_remote_success` | POST succeeds, returns data |
| 7 | `test_query_remote_retry_on_500` | Retries on 500, succeeds on 3rd |
| 8 | `test_query_remote_retry_on_503` | Retries on 503 |
| 9 | `test_query_remote_no_retry_on_400` | 400 = permanent failure, no retry |
| 10 | `test_query_remote_no_retry_on_401` | 401 = auth failure, no retry |
| 11 | `test_query_remote_max_retries_exceeded` | Fails after max retries |
| 12 | `test_handler_routes_to_local_when_single_cloud` | Uses DynamoDB directly |
| 13 | `test_handler_routes_to_remote_when_multi_cloud` | POSTs to remote URL |
| 14 | `test_sends_x_inter_cloud_token_header` | Token in header |
| 15 | `test_envelope_format_correct` | source_cloud, target_layer, payload |

### 4.2 Hot Reader (HTTP Endpoint) Unit Tests (NEW)

| # | Test Case | Description |
|---|-----------|-------------|
| 16 | `test_rejects_missing_token` | 401 if no X-Inter-Cloud-Token |
| 17 | `test_rejects_invalid_token` | 401 if token mismatch |
| 18 | `test_accepts_valid_token` | 200 with correct token |
| 19 | `test_token_case_insensitive_header` | x-inter-cloud-token works |
| 20 | `test_rejects_empty_body` | 400 if no request body |
| 21 | `test_rejects_malformed_json` | 400 if invalid JSON |
| 22 | `test_queries_dynamodb_correctly` | Correct KeyConditionExpression |
| 23 | `test_returns_twinmaker_format` | propertyValues structure |
| 24 | `test_handles_no_results` | Empty propertyValues |
| 25 | `test_handles_dynamodb_error` | 500 on DB failure |

### 4.3 Deployer Unit Tests (NEW)

| # | Test Case | Description |
|---|-----------|-------------|
| 26 | `test_dt_data_connector_no_remote_url_when_same_provider` | L3=L4 → no REMOTE_READER_URL |
| 27 | `test_dt_data_connector_injects_remote_url_when_different` | L3≠L4 → sets REMOTE_READER_URL |
| 28 | `test_hot_reader_deployed_when_l4_remote` | L4≠L3 → Hot Reader created |
| 29 | `test_hot_reader_not_deployed_when_same_cloud` | L4=L3 → no Hot Reader |
| 30 | `test_hot_reader_function_url_created` | Lambda Function URL configured (not API Gateway) |
| 31 | `test_function_url_saved_to_config_inter_cloud` | URL persisted |

### 4.4 Integration Tests (UPDATE EXISTING)

| # | Test Case | File | Description |
|---|-----------|------|-------------|
| 32 | `test_create_dt_data_connector_components` | `test_aws_l3_readers.py` | NEW - tests digital-twin-data-connector creation |
| 33 | `test_destroy_dt_data_connector_components` | `test_aws_l3_readers.py` | NEW - tests digital-twin-data-connector destruction |
| 34 | `test_create_hot_reader_http_endpoint` | `test_aws_l3_readers.py` | NEW |
| 35 | `test_hot_reader_with_function_url` | `test_aws_l3_readers.py` | NEW |

### 4.5 Edge Cases & Error Handling (Expanded)

| # | Test Case | Description |
|---|-----------|-------------|
| 36 | `test_require_env_raises_on_missing` | _require_env() EnvironmentError |
| 37 | `test_require_env_raises_on_empty` | Empty string → EnvironmentError |
| 38 | `test_require_env_raises_on_whitespace_only` | "   " → EnvironmentError |
| 39 | `test_config_providers_missing_l3_hot` | Graceful error message |
| 40 | `test_config_providers_missing_l4` | Graceful error message |
| 41 | `test_config_providers_empty_dict` | {} → proper error |
| 42 | `test_config_providers_null_value` | layer_4_provider: null → error |

### 4.6 Network & HTTP Edge Cases

| # | Test Case | Description |
|---|-----------|-------------|
| 43 | `test_http_connection_timeout` | Timeout after 30s → proper error |
| 44 | `test_http_read_timeout` | Response takes too long → error |
| 45 | `test_http_ssl_verification_failure` | Invalid cert → SSLError |
| 46 | `test_http_dns_resolution_failure` | Invalid hostname → connection error |
| 47 | `test_http_connection_refused` | Port closed → connection error |
| 48 | `test_remote_returns_empty_body` | 200 OK but empty → graceful handling |
| 49 | `test_remote_returns_invalid_json` | 200 OK but garbage → JSONDecodeError |
| 50 | `test_remote_returns_html_error_page` | 200 OK but HTML → parsing error |
| 51 | `test_retry_respects_backoff_timing` | Exponential backoff verified |
| 52 | `test_retry_stops_after_max_attempts` | Max 3 retries then fail |

### 4.7 Payload & Format Edge Cases

| # | Test Case | Description |
|---|-----------|-------------|
| 53 | `test_oversized_query_params` | Query > 6MB → error before send |
| 54 | `test_special_characters_in_device_id` | Unicode device IDs handled |
| 55 | `test_empty_selected_properties` | Empty list → empty propertyValues |
| 56 | `test_missing_entity_id` | No entityId in event → clear error |
| 57 | `test_missing_workspace_id` | No workspaceId → clear error |
| 58 | `test_invalid_time_range` | startTime > endTime → error |
| 59 | `test_dynamodb_pagination` | Large result sets handled |
| 60 | `test_property_type_mapping` | int/float/string/bool types correct |

### 4.8 Token & Authentication Edge Cases

| # | Test Case | Description |
|---|-----------|-------------|
| 61 | `test_token_with_special_characters` | Base64 encoded tokens work |
| 62 | `test_token_very_long` | 512+ char token works |
| 63 | `test_token_comparison_timing_safe` | Prevent timing attacks |
| 64 | `test_token_header_multiple_values` | Multiple headers → first used |
| 65 | `test_missing_inter_cloud_token_env` | Env not set → startup failure |

### 4.9 Phase 0 Bug Fix Tests

| # | Test Case | File | Description |
|---|-----------|------|-------------|
| 66 | `test_hot_reader_last_entry_require_env_digital_twin_info` | `test_hot_reader_last_entry.py` | Missing → EnvironmentError |
| 67 | `test_hot_reader_last_entry_require_env_dynamodb_table` | `test_hot_reader_last_entry.py` | Missing → EnvironmentError |
| 68 | `test_default_processor_require_env_digital_twin_info` | `test_default_processor.py` | Missing → EnvironmentError |
| 69 | `test_default_processor_require_env_persister_name` | `test_default_processor.py` | Missing → EnvironmentError |
| 70 | `test_processor_wrapper_fail_fast_on_missing_persister` | `test_processor_wrapper.py` | Raise not warn |

### 4.10 Config Inter-Cloud Tests

| # | Test Case | Description |
|---|-----------|-------------|
| 71 | `test_save_inter_cloud_connection_creates_file` | Creates config_inter_cloud.json if missing |
| 72 | `test_save_inter_cloud_connection_updates_existing` | Adds to existing connections |
| 73 | `test_hot_reader_url_persisted_on_deploy` | URL saved after Lambda creation |
| 74 | `test_inter_cloud_config_missing_connection_raises` | Fail-fast if connection missing |
| 75 | `test_inter_cloud_config_missing_url_raises` | url key missing → error |
| 76 | `test_inter_cloud_config_missing_token_raises` | token key missing → error |

### 4.11 Provider Validation Tests

| # | Test Case | Description |
|---|-----------|-------------|
| 77 | `test_config_providers_invalid_provider_name` | "azur" (typo) → UnsupportedProviderError |
| 78 | `test_config_providers_case_sensitivity` | "AWS" vs "aws" handling |
| 79 | `test_dual_validation_url_set_but_same_provider` | URL present but L3=L4 → no remote call |
| 80 | `test_dual_validation_url_missing_but_different_provider` | L3≠L4 but no URL → error |

## 5. Documentation Updates

### 5.1 Files to Update

| File | Changes |
|------|---------|
| `docs/docs-multi-cloud.html` | Add L3→L4/L5 Read section with flowchart |
| `docs/docs-aws-deployment.html` | Update Digital Twin Data Connector status |
| `technical_specs.md` | Document REMOTE_READER_URL implementation |

### 5.2 Proposed Flowchart for docs-multi-cloud.html

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           MULTI-CLOUD L3→L4/L5 READ FLOW                            │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  L5 (Grafana)           L4 (TwinMaker)                    L3 Hot Storage            │
│  ┌────────────┐         ┌────────────┐                    ┌────────────┐            │
│  │ Dashboard  │         │ Workspace  │                    │ DynamoDB / │            │
│  │ Panel      │         │            │                    │ Cosmos DB  │            │
│  └─────┬──────┘         └─────┬──────┘                    └─────▲──────┘            │
│        │                      │                                 │                   │
│        │  TwinMaker           │  Data Connector                │                    │
│        │  Plugin              │  Invokes                       │                    │
│        ▼                      ▼                                │                    │
│  ╔════════════════════════════════════════════════════════════════╗                 │
│  ║  IS L4 ON SAME CLOUD AS L3 HOT?                                ║                 │
│  ╚════════════════════════════════════════════════════════════════╝                 │
│                      │                                                              │
│      ┌───────────────┴───────────────┐                                              │
│      │                               │                                              │
│      ▼ YES                           ▼ NO                                           │
│  ┌────────────────┐       ┌──────────────────────────────────────────────────┐      │
│  │ Digital Twin   │       |  Digital Twin                                    |      | 
|  | Data Connector │       |  Data Connector                                  │      │
│  │ queries        │       │  POSTs query to REMOTE_READER_URL                │      │
│  │ local          │       │  (with X-Inter-Cloud-Token)                      │      │
│  │ DynamoDB       │       │                                                  │      │
│  └──────┬─────────┘       │       ┌────────────────────────────────────┐     │      │
│         │                 │       │  HTTP POST with X-Inter-Cloud-Token│     │      │
│         │                 │       └──────────────┬─────────────────────┘     │      │
│         │                 │                      │                           │      │
│         │                 │                      ▼                           │      │
│         │                 │           ┌─────────────────────┐                │      │
│         │                 │           │  Hot Reader         │ (on L3 cloud)  │      │
│         │                 │           │  - Validates token  │                │      │
│         │                 │           │  - Queries local DB │                │      │
│         │                 │           └──────────┬──────────┘                │      │
│         │                 └──────────────────────┼───────────────────────────┘      │
│         │                                        │                                  │
│         └────────────────┬───────────────────────┘                                  │
│                          │                                                          │
│                          ▼                                                          │
│               ╔════════════════════╗                                                │
│               ║   DATA RETURNED    ║                                                │
│               ║   TO TWINMAKER     ║                                                │
│               ╚════════════════════╝                                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 6. Implementation Phases

### Phase 0: Pre-requisite Bug Fixes (CRITICAL - Do First)

> [!CAUTION]
> These fixes MUST be completed before any other work. They address silent crash bugs.

| Step | File | Action |
|------|------|--------|
| 0.1 | `hot-reader-last-entry/lambda_function.py` | Add `_require_env()` function |
| 0.2 | `hot-reader-last-entry/lambda_function.py` | Replace `json.loads(os.environ.get("DIGITAL_TWIN_INFO", None))` |
| 0.3 | `hot-reader-last-entry/lambda_function.py` | Replace `os.environ.get("DYNAMODB_TABLE_NAME", None)` |
| 0.4 | `default-processor/lambda_function.py` | Add `_require_env()` function |
| 0.5 | `default-processor/lambda_function.py` | Replace `json.loads(os.environ.get(..., None))` pattern |
| 0.6 | `processor_wrapper/lambda_function.py` | Change warning to fail-fast (raise if missing) |
| 0.7 | Run existing tests | `pytest tests/ -v` to verify no regressions |

**Code Pattern to Apply (from hot-reader which is already fixed):**
```python
def _require_env(name: str) -> str:
    """Get required environment variable or raise error at module load time."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: Required environment variable '{name}' is missing or empty")
    return value

# Usage:
DIGITAL_TWIN_INFO = json.loads(_require_env("DIGITAL_TWIN_INFO"))
DYNAMODB_TABLE_NAME = _require_env("DYNAMODB_TABLE_NAME")
```

### Phase 1: API Gateway Removal (CLEANUP)

> [!WARNING]
> **API Gateway is not needed** - we use Lambda Function URLs with `X-Inter-Cloud-Token` instead.

| Step | File | Action |
|------|------|--------|
| 1.1 | `layer_3_storage.py` | Remove `create_l3_api_gateway()` function (lines ~1095-1147) |
| 1.2 | `layer_3_storage.py` | Remove `destroy_l3_api_gateway()` function (lines ~1150-1177) |
| 1.3 | `l3_adapter.py` | Remove any calls to API Gateway functions |
| 1.4 | `naming.py` | Remove `api_gateway()` naming function if exists |
| 1.5 | Run tests | Verify no API Gateway references remain |

### Phase 2: Add Function URL to Existing Hot Reader

> [!NOTE]
> **Hot Reader stays as-is** - it already reads from DynamoDB. We just add a Function URL so remote Digital Twin Data Connectors can call it.

| Step | File | Action |
|------|------|--------|
| 2.1 | `hot-reader/lambda_function.py` | Add HTTP request parsing (detect if invoked via Function URL) |
| 2.2 | `hot-reader/lambda_function.py` | Add `X-Inter-Cloud-Token` validation for HTTP requests |
| 2.3 | `hot-reader-last-entry/lambda_function.py` | Same changes as above |
| 2.4 | `layer_3_storage.py` | Add `create_hot_reader_function_url()` - creates Function URL with NONE auth |
| 2.5 | `layer_3_storage.py` | Add `create_hot_reader_last_entry_function_url()` |
| 2.6 | Inject `INTER_CLOUD_TOKEN` env var | For token validation |

### Phase 3: Create NEW Digital Twin Data Connector Lambda

> [!IMPORTANT]
> **Digital Twin Data Connector is a NEW Lambda** invoked by TwinMaker. It checks if L3=L4, routes to local Hot Reader OR remote Hot Reader (via HTTP POST).

| Step | File | Action |
|------|------|--------|
| 3.1 | Create `digital-twin-data-connector/lambda_function.py` | NEW Lambda function |
| 3.2 | Add `_require_env()` pattern | Fail-fast validation |
| 3.3 | Add `_is_multi_cloud_hot_storage()` | Check `config_providers` L3 vs L4 |
| 3.4 | Add `_invoke_local_hot_reader()` | Direct Lambda invocation |
| 3.5 | Add `_query_remote_hot_reader()` | HTTP POST with X-token + retry |
| 3.6 | Add `lambda_handler()` routing | If L3=L4 → local, else → remote |
| 3.7 | Create `digital-twin-data-connector-last-entry/lambda_function.py` | Same pattern |

### Phase 4: Deployer Updates

| Step | File | Action |
|------|------|--------|
| 4.1 | `naming.py` | Add `dt_data_connector_lambda_function()`, `dt_data_connector_last_entry_lambda_function()` |
| 4.2 | `naming.py` | Add `dt_data_connector_iam_role()`, `dt_data_connector_last_entry_iam_role()` |
| 4.3 | `layer_3_storage.py` | Add `create_dt_data_connector_iam_role()` |
| 4.4 | `layer_3_storage.py` | Add `create_dt_data_connector_lambda_function()` with multi-cloud env vars |
| 4.5 | `layer_3_storage.py` | Add `create_dt_data_connector_last_entry_*` functions |
| 4.6 | `l3_adapter.py` | Conditional: Digital Twin Data Connector only deployed if L3≠L4 |
| 4.7 | `l3_adapter.py` | Always deploy Hot Reader Function URL (for cross-cloud access) |
| 4.8 | `l3_adapter.py` | Save Function URL to `config_inter_cloud.json` |
| 4.9 | Inject env vars | `REMOTE_READER_URL`, `INTER_CLOUD_TOKEN`, `LOCAL_HOT_READER_NAME`

### Phase 5: Update TwinMaker to Use Digital Twin Data Connector

> [!IMPORTANT]
> TwinMaker component types must point to Digital Twin Data Connector (in multi-cloud) instead of Hot Reader (in single-cloud).

| Step | File | Action |
|------|------|--------|
| 5.1 | `layer_4_digital_twin.py` | Update component type to use Digital Twin Data Connector Lambda ARN |
| 5.2 | `layer_4_digital_twin.py` | Conditional: If L3=L4, use Hot Reader directly (no change from current) |
| 5.3 | `layer_4_digital_twin.py` | If L3≠L4, use Digital Twin Data Connector Lambda |

### Phase 6: Tests
| Step | Action |
|------|--------|
| 6.1 | Create `test_dt_data_connector_multi_cloud.py` (25 tests) |
| 6.2 | Create `test_hot_reader.py` (10 tests) |
| 6.3 | Update `test_aws_l3_readers.py` |
| 6.4 | Run all tests |

### Phase 7: Documentation
| Step | Action |
|------|--------|
| 7.1 | Update `docs/docs-multi-cloud.html` with L3→L4 section |
| 7.2 | Update `docs/docs-aws-deployment.html` status |
| 7.3 | Update `technical_specs.md` |

---

## 7. Verification Plan

### Automated Tests
```bash
# Run all tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v

# Run specific new tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_dt_data_connector_multi_cloud.py -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_hot_reader.py -v

# Run L3 reader integration tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/integration/aws/test_aws_l3_readers.py -v
```

### Manual Verification
- [ ] All existing tests pass after renaming
- [ ] All new unit tests pass  
- [ ] Documentation renders correctly

## 8. Codebase Gap Audit (Critical Findings)

### 8.1 Lambda Functions Missing `_require_env()` Pattern

> [!CAUTION]
> These functions have **silent fallback patterns** that cause crashes or undefined behavior:

| Function | File | Issue | Severity |
|----------|------|-------|----------|
| **hot-reader-last-entry** | `hot-reader-last-entry/lambda_function.py` | `json.loads(os.environ.get(..., None))` → TypeError crash | 🔴 CRITICAL |
| **default-processor** | `default-processor/lambda_function.py` | Same pattern: `json.loads(None)` → crash | 🔴 CRITICAL |
| **processor_wrapper** | `processor_wrapper/lambda_function.py` | `os.environ.get("PERSISTER_LAMBDA_NAME")` → None, silent warning only | 🟡 HIGH |

### 8.2 Lambda Functions Already Fixed ✅

| Function | Status |
|----------|--------|
| hot-reader | ✅ Has `_require_env()` |
| writer | ✅ Has `_require_env()` |
| cold-writer | ✅ Has `_require_env()` |
| archive-writer | ✅ Has `_require_env()` |
| persister | ✅ Has `_require_env()` |
| ingestion | ✅ Has `_require_env()` |
| connector | ✅ Has `_require_env()` |
| dispatcher | ✅ Has `_require_env()` |
| event-checker | ✅ Has `_require_env()` |
| hot-to-cold-mover | ✅ Has `_require_env()` |
| cold-to-archive-mover | ✅ Has `_require_env()` |

### 8.3 config_inter_cloud.json Handling

| Component | Status | Notes |
|-----------|--------|-------|
| `config_loader.py` | ✅ Has `save_inter_cloud_connection()` | Persists URLs |
| `layer_3_storage.py` | ✅ Uses config | Lines 651, 836 |
| `layer_2_compute.py` | ⚠️ Has inconsistent attr access | Line 731: `getattr(config, "config_inter_cloud", {})` |
| **Digital Twin Data Connector** | ❌ MISSING | Needs to read `REMOTE_READER_URL` from config |

### 8.4 Additional Pre-requisite Fixes Required

| # | Fix | File | Description |
|---|-----|------|-------------|
| P1 | Add `_require_env()` | `hot-reader-last-entry/lambda_function.py` | Replace `os.environ.get(..., None)` |
| P2 | Add `_require_env()` | `default-processor/lambda_function.py` | Replace `json.loads(None)` pattern |
| P3 | Fail-fast in processor_wrapper | `processor_wrapper/lambda_function.py` | Raise if PERSISTER_LAMBDA_NAME missing |

## 9. Future Work: Azure L4/L5 Provider Scenarios

> [!NOTE]
> These notes document Azure L4/L5 multi-cloud patterns (out of scope for AWS implementation, but documented for future Azure work).

### 9.1 Key Architectural Differences: AWS vs Azure

| Aspect | AWS (TwinMaker) | Azure (Digital Twins) |
|--------|-----------------|----------------------|
| **Data Connector Pattern** | Lambda function invoked by TwinMaker | No equivalent - REST API only |
| **Authentication** | IAM Role (internal), X-Inter-Cloud-Token (cross-cloud) | OAuth2 / Managed Identity |
| **Grafana Integration** | Native TwinMaker plugin | Infinity plugin with OAuth2 |
| **Real-time Updates** | Lambda invoked on-demand | Event Grid → Azure Function |
| **Query Language** | TwinMaker format (via Lambda) | SQL-like ADT Query Language |

### 9.2 Azure Provider Combination Matrix

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                     AZURE L4/L5 PROVIDER SCENARIOS                                             │
├────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                │
│  L3 Hot Provider    L4 Provider       L5 Provider        Solution                              │
│  ────────────────   ──────────────    ──────────────     ───────────────────                   │
│  Azure (Cosmos DB)  Azure (ADT)       Azure (M.Grafana)  Direct: Infinity→ADT                  │
│  Azure (Cosmos DB)  Azure (ADT)       Azure (M.Grafana)  Alt: Cosmos DB plugin                 │
│  AWS (DynamoDB)     Azure (ADT)       Azure (M.Grafana)  Infinity→AWS Hot Reader               │
│  Azure (Cosmos DB)  AWS (TwinMaker)   AWS (M.Grafana)    Digital Twin Data Connector→Azure HR  │
│                                                                                                │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Scenario A: Azure L4 + Azure L3 (Same Cloud)

**Pattern:** Grafana Infinity plugin → Azure Digital Twins Query API

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                    AZURE L4/L5: SAME CLOUD (AZURE)                            │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Azure Managed Grafana          Azure Digital Twins         Azure Cosmos DB   │
│  ┌────────────────────┐         ┌────────────────────┐     ┌────────────────┐ │
│  │  Dashboard Panel   │         │  Twin Graph        │     │  Hot Data      │ │
│  └─────────┬──────────┘         └─────────┬──────────┘     └───────▲────────┘ │
│            │                              │                        │          │
│            │Infinity Plugin               │ADT Query API           │          │
│            │(OAuth2 Auth)                 │                        │          │
│            ▼                              ▼                        │          │
│  ┌────────────────────────────────────────────────────┐            │          │
│  │     POST /query?api-version=2023-10-31             │            │          │
│  │     { "query": "SELECT * FROM DIGITALTWINS" }      │────────────┘          │
│  └────────────────────────────────────────────────────┘                       │
│                                                                               │
│  Authentication: Service Principal with OAuth2 Client Credentials             │
│  Token URL: https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token      │
│  Resource: https://digitaltwins.azure.net                                     │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Grafana Infinity Plugin Configuration:**
```yaml
# Data Source Settings
Name: Azure Digital Twins
Type: Infinity (JSON)
Authentication: OAuth2 Client Credentials

OAuth2 Settings:
  Client ID: {app_registration_client_id}
  Client Secret: {app_registration_secret}
  Token URL: https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
  Scopes: (empty)
  Endpoint Params:
    - Key: resource
    - Value: https://digitaltwins.azure.net

Query Example:
  URL: https://{adt-instance}.api.{region}.digitaltwins.azure.net/query?api-version=2023-10-31
  Method: POST
  Body: { "query": "SELECT T.temperature, T.pressure FROM DIGITALTWINS T WHERE $dtId='device-001'" }
```

### 9.4 Scenario B: Azure L5 + AWS L3 (Cross-Cloud Read)

**Pattern:** Grafana Infinity plugin → AWS Hot Reader API

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                    AZURE L5 → AWS L3: CROSS-CLOUD READ                          │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  AZURE CLOUD                                 AWS CLOUD                         │
│  ┌────────────────────────────────────┐     ┌─────────────────────────────────┐│
│  │                                    │     │                                 ││
│  │  L5: Azure Managed Grafana         │     │  L3: AWS DynamoDB               ││
│  │  ┌────────────────────┐            │     │  ┌─────────────────────────┐    ││
│  │  │  Dashboard Panel   │            │     │  │   Hot Table             │    ││
│  │  └─────────┬──────────┘            │     │  └────────────▲────────────┘    ││
│  │            │                       │     │               │                 ││
│  │            │Infinity Plugin        │     │          DynamoDB query         ││
│  │            │(X-Inter-Cloud-Token)  │     │               │                 ││
│  │            │                       │     │  ┌────────────┴────────────┐    ││
│  │            ▼                       │     │  │  Hot Reader Lambda      │    ││
│  │  ┌────────────────────────────┐    │     │  │  (Function URL)         │    ││
│  │  │  POST to Hot Reader URL    │──────────│  │  - Token validation     │    ││
│  │  │  X-Inter-Cloud-Token       │    │     │  │  - Returns JSON         │    ││
│  │  └────────────────────────────┘    │     │  └─────────────────────────┘    ││
│  │                                    │     │                                 ││
│  └────────────────────────────────────┘     └─────────────────────────────────┘│
└────────────────────────────────────────────────────────────────────────────────┘
```

### 9.5 Scenario C: AWS L4 + Azure L3 (Cross-Cloud Read - THIS PLAN)

**Pattern:** AWS Digital Twin Data Connector → Azure Hot Reader

This is the primary focus of this implementation plan. When AWS TwinMaker (L4) needs data from Azure Cosmos DB (L3):

1. TwinMaker invokes **Digital Twin Data Connector Lambda** (AWS)
2. Digital Twin Data Connector detects `L3_provider != L4_provider` via dual validation
3. Digital Twin Data Connector POSTs to **Azure Hot Reader** (Azure Function with Function URL)
4. Azure Hot Reader validates `X-Inter-Cloud-Token`
5. Azure Hot Reader queries Cosmos DB
6. Returns TwinMaker-compatible format to Digital Twin Data Connector
7. Digital Twin Data Connector returns data to TwinMaker

### 9.6 Azure Hot Reader (Future Work)

> **See:** [2025-12-11_azure_hot_reader_future_work.md](./2025-12-11_azure_hot_reader_future_work.md)

Contains full implementation details for:
- `azure-hot-reader` (time-series history)
- `azure-hot-reader-last-entry` (current value)

### 9.7 GCP Hot Reader (Future Work)

> **See:** [2025-12-11_gcp_hot_reader_future_work.md](./2025-12-11_gcp_hot_reader_future_work.md)

Contains full implementation details for:
- `gcp-hot-reader` (time-series history)
- `gcp-hot-reader-last-entry` (current value)
- Cross-cloud example: L3=GCP, L4=AWS, L5=Azure



### 9.8 AWS L4 + Azure L5 Workaround (Infinity + AWS Sigv4)

> [!TIP]
> **This solves the plugin restriction!** Azure Managed Grafana can call AWS TwinMaker REST API using the Infinity plugin with AWS Sigv4 authentication.

**Solution Overview:**
- Azure Managed Grafana CANNOT install TwinMaker plugin
- Azure Managed Grafana CAN use **Infinity plugin** (pre-installed)
- Infinity plugin supports **AWS Sigv4 authentication**
- TwinMaker exposes a **REST API** for queries

**Step 1: Create IAM User for API Access**
```yaml
# In AWS Console: IAM → Users → Create User
User Name: grafana-twinmaker-api
Access Type: Programmatic access (Access Key ID + Secret)
Policy: AmazonawsIoTTwinMakerReadOnly (or custom policy)
```

**Step 2: Configure Infinity Data Source in Azure Managed Grafana**
```yaml
Name: AWS TwinMaker API
Type: Infinity

Authentication:
  Type: AWS
  Access Key: {IAM_ACCESS_KEY_ID}
  Secret Key: {IAM_SECRET_ACCESS_KEY}
  Region: {your-twinmaker-region}  # e.g., us-east-1
  Service: iottwinmaker

Allowed Hosts:
  - https://iottwinmaker.*.amazonaws.com
```

**Step 3: Query TwinMaker API in Panel**
```yaml
Query Type: JSON
Method: GET or POST
URL: https://iottwinmaker.{region}.amazonaws.com/workspaces/{workspaceId}/entity-properties

# Example: Get property value history
POST https://iottwinmaker.us-east-1.amazonaws.com/workspaces/MyWorkspace/entity-properties/value
Body: {
  "entityId": "device-001",
  "componentName": "SensorComponent",
  "selectedProperties": ["temperature", "humidity"],
  "startTime": "$__from",
  "endTime": "$__to"
}

Root Selector: propertyValues
```

**Cost Comparison:**

| L5 Option | Monthly Cost | Pros | Cons |
|-----------|-------------|------|------|
| Azure M.Grafana Standard | ~$62 + $6/user | Managed, Azure-native | No TwinMaker plugin (workaround) |
| Self-hosted Grafana on Azure VM | ~$15-30 (B1s) | Full plugins | Manual maintenance |
| Grafana Cloud Free | $0 (10k series) | Full plugins, managed | Limited metrics |

**Limitation:** This workaround provides data access but NOT the TwinMaker Scene Viewer panel (3D visualization). For 3D scenes, use self-hosted Grafana or AWS Managed Grafana.

### 9.9 Pattern B: L5 → Hot Reader Direct (Universal Solution) ⭐

> [!IMPORTANT]
> **This is the universal solution for cross-cloud L5!** Works for ALL 12 L3/L5 combinations.

**Concept:** Grafana (on any cloud) calls our Hot Reader HTTP endpoint directly using the Infinity plugin with `X-Inter-Cloud-Token` header. No L4 service needed for simple data visualization.

```
┌───────────────────────────────────────────────────────────────────────────┐
│  L5 GRAFANA (any cloud)                L3 HOT READER (any cloud)         │
│  ┌─────────────────────┐               ┌───────────────────────────┐     │
│  │  Grafana Dashboard  │               │  AWS Lambda / Azure Func  │     │
│  │  ┌───────────────┐  │    HTTPS      │  / GCP Cloud Function     │     │
│  │  │ Infinity      │──┼───POST────────│  ┌──────────────────────┐ │     │
│  │  │ Data Source   │  │               │  │ 1. Validate X-Token  │ │     │
│  │  └───────────────┘  │               │  │ 2. Query local DB    │ │     │
│  └─────────────────────┘               │  │ 3. Return JSON       │ │     │
│                                        │  └──────────────────────┘ │     │
│  Header: X-Inter-Cloud-Token           └───────────────────────────┘     │
└───────────────────────────────────────────────────────────────────────────┘
```

**Step 1: Configure Infinity Data Source (Same for all L5 providers)**

```yaml
Name: Hot Reader - {AWS/Azure/GCP}
Type: Infinity

Base URL: (leave empty, set per query)

Authentication:
  Type: API Key
  Key: X-Inter-Cloud-Token
  Value: {your_inter_cloud_token_from_config}
  In: Header

Allowed Hosts:
  # AWS Lambda Function URL
  - https://*.lambda-url.*.on.aws
  # Azure Function HTTP Trigger
  - https://*.azurewebsites.net
  # GCP Cloud Function
  - https://*.cloudfunctions.net
```

**Step 2: Query Hot Reader in Panel**

```yaml
Query Type: JSON
Method: POST
URL: https://{hot-reader-function-url}

Body:
{
  "source_cloud": "azure",       # or "aws", "gcp"
  "target_layer": "L3-hot",
  "payload": {
    "iotDeviceId": "device-001",
    "startTime": "$__from",      # Grafana variable
    "endTime": "$__to",          # Grafana variable
    "selectedProperties": ["temperature", "humidity"]
  }
}

# Parse response
Root Selector: propertyValues
Columns:
  - Selector: entityPropertyReference.propertyName
    As: property
  - Selector: values[0].time
    As: timestamp
  - Selector: values[0].value.DoubleValue
    As: value
```

**Hot Reader Response Format (TwinMaker-compatible):**

```json
{
  "propertyValues": [
    {
      "entityPropertyReference": { "propertyName": "temperature" },
      "values": [
        { "time": "2024-01-15T10:30:00Z", "value": { "DoubleValue": 23.5 } }
      ]
    }
  ]
}
```

**Comparison: Pattern B vs Pattern A**

| Aspect | Pattern A (via L4) | Pattern B (Direct to L3) |
|--------|-------------------|--------------------------|
| Complexity | Higher (L4 + L5 setup) | Lower (L5 only) |
| L4 Features | ✅ 3D scenes, entities | ❌ Data only |
| Multi-cloud | Needs Digital Twin Data Connector | ✅ Universal (Infinity) |
| Cost | L4 service charges | HTTP calls only |
| Best for | Full digital twin | Simple dashboards |

---

## 10. Expanded Test Cases

### 10.1 Pre-requisite Fix Tests (NEW)

| # | Test Case | File | Description |
|---|-----------|------|-------------|
| P1 | `test_hot_reader_last_entry_require_env_digital_twin_info` | `test_hot_reader_last_entry.py` | Missing DIGITAL_TWIN_INFO → EnvironmentError |
| P2 | `test_hot_reader_last_entry_require_env_dynamodb_table` | `test_hot_reader_last_entry.py` | Missing DYNAMODB_TABLE_NAME → EnvironmentError |
| P3 | `test_default_processor_require_env_digital_twin_info` | `test_default_processor.py` | Missing env → EnvironmentError |
| P4 | `test_default_processor_require_env_persister_name` | `test_default_processor.py` | Missing PERSISTER_LAMBDA_NAME → EnvironmentError |
| P5 | `test_processor_wrapper_require_env_persister_name` | `test_processor_wrapper.py` | Missing → EnvironmentError (not warning) |

### 10.2 Config Inter-Cloud Tests (NEW)

| # | Test Case | Description |
|---|-----------|-------------|
| C1 | `test_save_inter_cloud_connection_creates_file` | Creates config_inter_cloud.json if missing |
| C2 | `test_save_inter_cloud_connection_updates_existing` | Adds to existing connections |
| C3 | `test_dt_data_connector_reads_remote_url_from_config` | Reads URL from config_inter_cloud.json |
| C4 | `test_hot_reader_url_persisted_on_deploy` | URL saved after Lambda creation |
| C5 | `test_inter_cloud_config_missing_raises` | Fail-fast if config incomplete |

### 10.3 Provider/Layer Mapping Validation Tests (NEW)

| # | Test Case | Description |
|---|-----------|-------------|
| V1 | `test_config_providers_missing_l3_hot_raises` | Missing layer_3_hot_provider → error |
| V2 | `test_config_providers_missing_l4_raises` | Missing layer_4_provider → error |
| V3 | `test_config_providers_invalid_provider_raises` | Invalid value (e.g., "azur") → error |
| V4 | `test_config_providers_empty_value_raises` | Empty string provider → error |
| V5 | `test_dual_validation_config_providers_mismatch` | URL set but providers same → no remote call |

### 10.4 Error Handling Edge Cases (NEW)

| # | Test Case | Description |
|---|-----------|-------------|
| E1 | `test_http_post_timeout_handling` | Connection timeout → proper error |
| E2 | `test_http_post_ssl_error_handling` | SSL verification failure → error |
| E3 | `test_json_decode_error_from_remote` | Invalid JSON response → graceful error |
| E4 | `test_remote_reader_returns_500` | 500 response → retry logic |
| E5 | `test_remote_reader_returns_400` | 400 response → no retry, log error |
| E6 | `test_remote_reader_returns_401` | 401 response → no retry, auth error |
| E7 | `test_empty_response_from_remote` | Empty body → graceful handling |
| E8 | `test_oversized_response_handling` | Response > 6MB → chunked handling |

### 10.5 Documentation Update Tests

| # | Test | Description |
|---|------|-------------|
| D1 | `test_docs_multi_cloud_renders` | HTML page loads correctly |
| D2 | `test_docs_nav_contains_multi_cloud` | Nav has link to multi-cloud page |

---

## 11. Documentation Updates Required

### Files to Update

| File | Changes |
|------|---------|
| `docs/docs-multi-cloud.html` | Add L3→L4/L5 Read section with flowchart |
| `docs/docs-aws-deployment.html` | Update Digital Twin Data Connector/Reader status |
| `technical_specs.md` | Document REMOTE_READER_URL implementation |

### Proposed Flowchart (for docs-multi-cloud.html)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                           MULTI-CLOUD L3→L4/L5 READ FLOW                              │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  L5 (Grafana)           L4 (TwinMaker)                    L3 Hot Storage            │
│  ┌────────────┐         ┌────────────┐                    ┌────────────┐            │
│  │ Dashboard  │         │ Workspace  │                    │ DynamoDB / │            │
│  │ Panel      │         │            │                    │ Cosmos DB  │            │
│  └─────┬──────┘         └─────┬──────┘                    └─────▲──────┘            │
│        │                      │                                 │                    │
│        │  TwinMaker           │  Data Connector                │                    │
│        │  Plugin              │  Invokes                       │                    │
│        ▼                      ▼                                │                    │
│  ╔════════════════════════════════════════════════════════════════╗                 │
│  ║  IS L4 ON SAME CLOUD AS L3 HOT?                               ║                 │
│  ╚════════════════════════════════════════════════════════════════╝                 │
│                      │                                                              │
│      ┌───────────────┴───────────────┐                                              │
│      │                               │                                              │
│      ▼ YES                           ▼ NO                                           │
│  ┌──────────────┐         ┌──────────────────────────────────────────────────┐      │
│  │ Digital Twin Data Connector│         │  Digital Twin Data Connector                                   │      │
│  │ queries      │         │  POSTs query to REMOTE_READER_URL                │      │
│  │ local        │         │  (with X-Inter-Cloud-Token)                      │      │
│  │ DynamoDB     │         │                                                  │      │
│  └──────┬───────┘         │       ┌────────────────────────────────────┐     │      │
│         │                 │       │  HTTP POST with X-Inter-Cloud-Token│     │      │
│         │                 │       └──────────────┬─────────────────────┘     │      │
│         │                 │                      ▼                           │      │
│         │                 │           ┌─────────────────────┐                │      │
│         │                 │           │  Hot Reader         │ (on L3 cloud)  │      │
│         │                 │           │  - Validates token  │                │      │
│         │                 │           │  - Queries local DB │                │      │
│         │                 │           └──────────┬──────────┘                │      │
│         │                 └──────────────────────┼───────────────────────────┘      │
│         └────────────────┬───────────────────────┘                                  │
│                          ▼                                                          │
│               ╔════════════════════╗                                                │
│               ║   DATA RETURNED    ║                                                │
│               ╚════════════════════╝                                                │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Updated Implementation Phases

### Phase 0: Pre-requisite Bug Fixes (CRITICAL)
| Step | File | Action |
|------|------|--------|
| 0.1 | `hot-reader-last-entry/lambda_function.py` | Add `_require_env()`, replace `None` defaults |
| 0.2 | `default-processor/lambda_function.py` | Add `_require_env()` |
| 0.3 | `processor_wrapper/lambda_function.py` | Fail-fast instead of warning |
| 0.4 | Run all existing tests | Verify no regressions |

### Phase 1-7: (See Section 6 for detailed steps)

---

## 13. Verification Plan Summary

### Automated Tests
```bash
# Run ALL tests after pre-requisite fixes
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v

# Run specific new tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_dt_data_connector_multi_cloud.py -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_hot_reader.py -v
```

### Test Coverage Summary

| Category | # Tests | Description |
|----------|---------|-------------|
| Digital Twin Data Connector multi-cloud | 15 | Dual validation, routing, HTTP POST |
| Hot Reader API | 10 | Token auth, query handling |
| Deployer | 6 | Conditional deployment |
| Integration | 4 | Updated existing tests |
| Edge cases & error handling | 7 | Env var validation |
| Network & HTTP | 10 | Timeouts, SSL, retries |
| Payload & format | 8 | Oversized, unicode, pagination |
| Token & auth | 5 | Special chars, timing attacks |
| Phase 0 bug fixes | 5 | `_require_env()` additions |
| Config inter-cloud | 6 | URL persistence, validation |
| Provider validation | 4 | Invalid names, case sensitivity |
| Documentation | 2 | Render checks |
| **TOTAL** | **80+** | Comprehensive coverage |

---

## 14. Out of Scope

- Azure/GCP Hot Reader function implementations (documented in Section 9)
- GCP L4 implementation (no equivalent service)
- Cold/Archive Reader for multi-cloud
- Grafana plugin development

