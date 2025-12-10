# Hot Reader Multi-Cloud Adaptations

## 1. Executive Summary

### The Problem
The Hot Reader Lambda functions (`hot-reader` and `hot-reader-last-entry`) are used by AWS IoT TwinMaker (Layer 4) to query data from Hot Storage. However:

1. **Hot Reader always reads locally**: It uses `boto3.resource("dynamodb")` directly - no awareness of multi-cloud scenarios
2. **No HTTP endpoint for cross-cloud access**: Unlike Writer (which has a Function URL for remote Persisters), Hot Reader has no public endpoint
3. **`REMOTE_READER_URL` is specified but not implemented**: `technical_specs.md` (line 19) defines this variable but it's never used anywhere in the codebase
4. **No deployer logic for multi-cloud Reader**: `layer_3_storage.py` creates Hot Reader but never sets up cross-cloud access

### The Solution
1. Create a **Hot Reader API Gateway** endpoint (not Lambda Function URL) to provide authenticated external access
2. Add **multi-cloud logic to TwinMaker component types** to use `REMOTE_READER_URL` when L3 is on a different cloud than L4
3. Implement **credential isolation** - TwinMaker only gets read access via the API, not direct DynamoDB access
4. Add **comprehensive tests** for cross-cloud reader scenarios

### Impact
- Enables multi-cloud L4 deployments where TwinMaker (AWS) reads from Hot Storage on Azure/GCP
- Maintains security by not exposing DynamoDB directly to cross-cloud callers
- Completes the "read path" for multi-cloud, complementing the existing "write path"

---

## 2. Current State

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CURRENT HOT READER FLOW (AWS Only)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  L4 (AWS TwinMaker)              L3 Hot (AWS DynamoDB)                      │
│  ┌──────────────────┐           ┌──────────────────┐                        │
│  │  TwinMaker Scene │           │   DynamoDB       │                        │
│  │  (Grafana)       │           │   Hot Table      │                        │
│  └────────┬─────────┘           └────────▲─────────┘                        │
│           │                              │                                  │
│           │ TwinMaker                    │ boto3.resource("dynamodb")       │
│           │ Data Connector               │ DIRECT ACCESS                    │
│           ▼                              │                                  │
│  ┌──────────────────┐                   │                                  │
│  │  Hot Reader      │───────────────────┘                                  │
│  │  Lambda ⚠️       │                                                       │
│  │  (No multi-cloud)│                                                       │
│  └──────────────────┘                                                       │
│                                                                             │
│  ⚠️ = NO MULTI-CLOUD LOGIC - Always reads from local DynamoDB              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Current Files:
| File | Status | Multi-Cloud Logic |
|------|--------|-------------------|
| `hot-reader/lambda_function.py` | ⚠️ Incomplete | None - uses boto3 directly |
| `hot-reader-last-entry/lambda_function.py` | ⚠️ Incomplete | None - uses boto3 directly |
| `layer_3_storage.py` | ⚠️ Incomplete | No API Gateway or multi-cloud env vars |
| `layer_4_twinmaker.py` | ⚠️ Incomplete | No conditional Reader URL injection |
| `technical_specs.md` | Documented | `REMOTE_READER_URL` specified but unused |

---

## 3. Target State

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                           MULTI-CLOUD HOT READER FLOW                                        │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  L4 (AWS TwinMaker)              L3 Hot (AZURE Cosmos DB)                                   │
│  ┌──────────────────┐           ┌──────────────────┐                                        │
│  │  TwinMaker Scene │           │   Cosmos DB      │                                        │
│  │  (Grafana)       │           │   Hot Container  │                                        │
│  └────────┬─────────┘           └────────▲─────────┘                                        │
│           │                              │                                                  │
│           │ TwinMaker                    │ Azure SDK                                        │
│           │ Data Connector               │                                                  │
│           ▼                              │                                                  │
│  ┌──────────────────┐           ┌────────┴─────────┐                                        │
│  │  Hot Reader      │──HTTP──▶  │  Hot Reader API  │                                        │
│  │  Lambda ✅       │   POST    │  (Azure Function)│                                        │
│  │ (Multi-cloud)    │  ≤6MB     │  - Auth token    │                                        │
│  │ - Check provider │           │  - Query Cosmos  │                                        │
│  │ - POST to remote │           └──────────────────┘                                        │
│  │   or read local  │                                                                       │
│  └──────────────────┘                                                                       │
│                                                                                             │
│  ✅ = Multi-cloud aware - routes to local or remote based on config                        │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Gap Analysis

### A. Lambda Function Code Gaps

| Component | File | Gap | Status |
|-----------|------|-----|--------|
| **Hot Reader** | `hot-reader/lambda_function.py` | No `REMOTE_READER_URL` check | ❌ Missing |
| **Hot Reader** | `hot-reader/lambda_function.py` | No `_is_multi_cloud_hot_storage()` dual validation | ❌ Missing |
| **Hot Reader** | `hot-reader/lambda_function.py` | No `_query_remote_hot_storage()` HTTP POST | ❌ Missing |
| **Hot Reader Last Entry** | `hot-reader-last-entry/lambda_function.py` | Same gaps as Hot Reader | ❌ Missing |

### B. Deployer Code Gaps

| Component | File | Gap | Status |
|-----------|------|-----|--------|
| **Hot Reader Deployer** | `layer_3_storage.py` | No multi-cloud env vars: `REMOTE_READER_URL`, `INTER_CLOUD_TOKEN` | ❌ Missing |
| **Hot Reader API** | `layer_3_storage.py` | No API Gateway creation for public access | ❌ Missing |
| **L3 Hot Adapter** | `l3_adapter.py` | No conditional Hot Reader API deployment | ❌ Missing |

### C. L4 TwinMaker Integration Gaps

| Component | File | Gap | Status |
|-----------|------|-----|--------|
| **TwinMaker Component Type** | `layer_4_twinmaker.py` | No awareness of remote L3 provider | ❌ Missing |
| **Data Connector** | `layer_4_twinmaker.py` | Hardcoded to local Lambda ARN | ❌ Missing |

### D. New Lambda Function Required

| Function | Purpose | Status |
|----------|---------|--------|
| **Hot Reader API** | HTTP endpoint for cross-cloud reads | ❌ Need to create (AWS) |
| **Hot Reader API** | HTTP endpoint for cross-cloud reads | ⏳ Future (Azure/GCP) |

---

## 5. Proposed Changes

### Component: AWS Lambda Functions

---

#### [MODIFY] [hot-reader/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/hot-reader/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/hot-reader/lambda_function.py`
- **Description:** Add multi-cloud logic to detect `REMOTE_READER_URL` and POST query to remote Hot Storage API.

**Changes:**
1. Add `_require_env()` helper for fail-fast env var validation
2. Add `_is_multi_cloud_hot_storage()` dual validation function
3. Add `_query_remote_hot_storage()` with retry logic
4. Modify `lambda_handler` to route based on multi-cloud detection

**Proposed Code:**
```python
REMOTE_READER_URL = os.environ.get("REMOTE_READER_URL", "").strip()
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "").strip()

class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is incomplete."""
    pass

def _is_multi_cloud_hot_storage() -> bool:
    """Check if L3 Hot is on a different cloud than L4."""
    if not REMOTE_READER_URL:
        return False
    
    providers = DIGITAL_TWIN_INFO.get("config_providers")
    if not providers:
        raise ConfigurationError("config_providers missing from DIGITAL_TWIN_INFO")
    
    l3_hot = providers.get("layer_3_hot_provider")
    l4 = providers.get("layer_4_provider")
    
    if not l3_hot or not l4:
        raise ConfigurationError(f"Missing provider: l3_hot={l3_hot}, l4={l4}")
    
    return l3_hot != l4

def _query_remote_hot_storage(query_params: dict) -> dict:
    """POST query to remote Hot Storage API with retry."""
    headers = {
        "Content-Type": "application/json",
        "X-Inter-Cloud-Token": INTER_CLOUD_TOKEN
    }
    
    payload = {
        "source_cloud": "aws",
        "target_layer": "L3-Hot-Read",
        "message_type": "query",
        "payload": query_params
    }
    
    # Retry logic with exponential backoff (same as Writer)
    ...

def lambda_handler(event, context):
    # ... existing validation ...
    
    if _is_multi_cloud_hot_storage():
        # Remote query
        query_params = {
            "iot_device_id": iot_device_id,
            "start_time": event["startTime"],
            "end_time": event["endTime"],
            "selected_properties": event["selectedProperties"]
        }
        result = _query_remote_hot_storage(query_params)
        return result
    else:
        # Local query (existing DynamoDB logic)
        ...
```

---

#### [MODIFY] [hot-reader-last-entry/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/hot-reader-last-entry/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/hot-reader-last-entry/lambda_function.py`
- **Description:** Same multi-cloud changes as Hot Reader.

---

#### [NEW] hot-reader-api/lambda_function.py
- **Path:** `src/providers/aws/lambda_functions/hot-reader-api/lambda_function.py`
- **Description:** HTTP endpoint for remote clouds to query AWS Hot Storage.

**Purpose:** When L4 (TwinMaker) is on Azure/GCP but L3 Hot is on AWS, remote TwinMaker's Reader Lambda calls this API.

**Key Features:**
- Token validation via `X-Inter-Cloud-Token` header
- Accepts query parameters: `iot_device_id`, `start_time`, `end_time`, `selected_properties`
- Returns TwinMaker-compatible response format
- Rate limiting to prevent abuse

---

### Component: Deployer Code

---

#### [MODIFY] [layer_3_storage.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/layer_3_storage.py)
- **Path:** `src/providers/aws/layers/layer_3_storage.py`

**Changes:**

**1. Update `create_hot_reader_lambda_function()` to inject multi-cloud env vars:**
```python
env_vars = {
    "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
    "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table(),
}

# Multi-cloud: Add remote reader URL if L3 Hot is on different cloud than L4
l3_hot = config.providers.get("layer_3_hot_provider", "aws")
l4 = config.providers.get("layer_4_provider", "aws")

if l3_hot != l4:
    conn_id = f"{l4}_l4_to_{l3_hot}_l3hot_read"
    connections = getattr(config, 'inter_cloud', {}).get("connections", {})
    conn = connections.get(conn_id, {})
    url = conn.get("url", "")
    token = conn.get("token", "")
    
    if not url or not token:
        raise ValueError(
            f"Multi-cloud config incomplete for {conn_id}: url={bool(url)}, token={bool(token)}"
        )
    
    env_vars["REMOTE_READER_URL"] = url
    env_vars["INTER_CLOUD_TOKEN"] = token
```

**2. Add Hot Reader API functions:**
```python
# ==========================================
# 1.8. Hot Reader API (Multi-Cloud Only)
# ==========================================
# Hot Reader API is deployed when L4 is on a DIFFERENT cloud than L3 Hot.
# It receives queries FROM remote TwinMaker Hot Reader Lambdas via HTTP POST.

def create_hot_reader_api_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Hot Reader API Lambda (multi-cloud only)."""
    ...

def create_hot_reader_api_lambda_function(...) -> str:
    """Creates the Hot Reader API Lambda with API Gateway."""
    ...
    return api_gateway_url

def destroy_hot_reader_api_lambda_function(provider: 'AWSProvider') -> None:
    """Destroys the Hot Reader API Lambda and API Gateway."""
    ...
```

---

#### [MODIFY] [l3_adapter.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/l3_adapter.py)
- **Path:** `src/providers/aws/layers/l3_adapter.py`
- **Description:** Add conditional Hot Reader API deployment when L4 is on a different cloud.

**Change in `deploy_l3_hot()`:**
```python
def deploy_l3_hot(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    # ... existing code ...
    
    # NEW: Deploy Hot Reader API if L4 is on a different cloud
    l4_provider = context.config.providers.get("layer_4_provider", "aws")
    if l4_provider != "aws":
        from .layer_3_storage import (
            create_hot_reader_api_iam_role,
            create_hot_reader_api_lambda_function,
        )
        logger.info("[L3-Hot] Deploying Hot Reader API for multi-cloud (L4 is remote)...")
        create_hot_reader_api_iam_role(provider)
        url = create_hot_reader_api_lambda_function(provider, context.config, project_path)
        
        # Save URL to config_inter_cloud.json
        from src.core.config_loader import save_inter_cloud_connection
        save_inter_cloud_connection(
            project_path=project_path,
            conn_id=f"{l4_provider}_l4_to_aws_l3hot_read",
            url=url,
            token=generate_secure_token()
        )
```

---

### Component: Naming Functions

---

#### [MODIFY] [naming.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/naming.py)
- **Path:** `src/providers/aws/naming.py`
- **Description:** Add naming functions for Hot Reader API.

**Add:**
```python
def hot_reader_api_lambda_function(self) -> str:
    """Lambda function name for the hot reader API (multi-cloud)."""
    return f"{self._twin_name}-hot-reader-api"

def hot_reader_api_iam_role(self) -> str:
    """IAM role name for the hot reader API Lambda (multi-cloud)."""
    return f"{self._twin_name}-hot-reader-api"

def hot_reader_api_gateway(self) -> str:
    """API Gateway name for the hot reader API (multi-cloud)."""
    return f"{self._twin_name}-hot-reader-api"
```

---

## 6. Implementation Phases

### Phase 1: Pre-requisites (Bug Fixes)

| Step | File | Action |
|------|------|--------|
| 1.1 | `hot-reader/lambda_function.py` | Add `_require_env()` validation for env vars |
| 1.2 | `hot-reader-last-entry/lambda_function.py` | Add `_require_env()` validation for env vars |

### Phase 2: Lambda Function Multi-Cloud Logic

| Step | File | Action |
|------|------|--------|
| 2.1 | `hot-reader/lambda_function.py` | Add `_is_multi_cloud_hot_storage()` |
| 2.2 | `hot-reader/lambda_function.py` | Add `_query_remote_hot_storage()` |
| 2.3 | `hot-reader/lambda_function.py` | Modify `lambda_handler` for routing |
| 2.4 | `hot-reader-last-entry/lambda_function.py` | Same changes as hot-reader |
| 2.5 | `hot-reader-api/lambda_function.py` | **[NEW]** Create HTTP endpoint Lambda |

### Phase 3: Deployer Updates

| Step | File | Action |
|------|------|--------|
| 3.1 | `naming.py` | Add `hot_reader_api_*` naming functions |
| 3.2 | `layer_3_storage.py` | Update `create_hot_reader_lambda_function()` with multi-cloud env vars |
| 3.3 | `layer_3_storage.py` | Add `create_hot_reader_api_*` functions |
| 3.4 | `l3_adapter.py` | Add conditional Hot Reader API deployment |

### Phase 4: Testing

| Step | File | Action |
|------|------|--------|
| 4.1 | `test_hot_reader_multi_cloud.py` | **[NEW]** Tests for `_is_multi_cloud_hot_storage()` |
| 4.2 | `test_hot_reader_multi_cloud.py` | Tests for `_query_remote_hot_storage()` |
| 4.3 | `test_hot_reader_api.py` | **[NEW]** Tests for Hot Reader API Lambda |

---

## 7. Verification Checklist

### Automated Tests

```bash
# Run all tests in Docker container
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v
```

Specific test files:
```bash
# Hot Reader multi-cloud tests (new)
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_hot_reader_multi_cloud.py -v

# Hot Reader API tests (new)
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_hot_reader_api.py -v
```

### Manual Verification
- [ ] All existing tests pass
- [ ] New multi-cloud tests pass
- [ ] Documentation updated

---

## 8. Design Decisions

### Why API Gateway instead of Lambda Function URL?

| Aspect | Lambda Function URL | API Gateway |
|--------|---------------------|-------------|
| **Authentication** | Custom header validation | Native API Key + IAM + Cognito options |
| **Rate Limiting** | None (must implement) | Built-in throttling |
| **Monitoring** | CloudWatch only | CloudWatch + X-Ray + Access Logs |
| **Cost** | Free | ~$3.50/million requests |
| **TwinMaker Compatibility** | May work | Known working pattern |

**Decision:** Use API Gateway for better security, rate limiting, and TwinMaker compatibility.

### Connection ID Format

Per existing pattern, new connection IDs for reading:
```python
# L4 → L3 Hot (Read)
conn_id = f"{l4_provider}_l4_to_{l3_hot_provider}_l3hot_read"  # e.g., "azure_l4_to_aws_l3hot_read"
```

---

## 9. Future Considerations (Out of Scope)

- **Azure/GCP Hot Reader API**: Implement Azure Functions and Cloud Functions equivalents
- **Cold/Archive Reader**: Similar pattern for reading from Cold/Archive storage
- **Caching**: Add caching layer to reduce cross-cloud latency
