# Gluecode Multi-Cloud Adaptations

## 1. Executive Summary

### The Problem
The AWS gluecode functions (Connector, Ingestion, Writer, Persister) are designed to enable data flow between layers across different cloud providers (AWS, Azure, GCP). However:

1. **Persister is incomplete**: It only writes to local DynamoDB but lacks logic to call a remote cloud's Writer API when L3 (storage) is on a different provider.
2. **Deployer code is incomplete**: Ingestion and Writer functions lack deployment code. Persister lacks multi-cloud environment variable injection.
3. **Authentication is inconsistent**: Each cloud roadmap specifies different auth mechanisms.
4. **No documentation**: Multi-cloud architecture is not documented for users.

### The Solution
1. Add multi-cloud logic to the **Persister** function to POST to a remote Writer API when `REMOTE_WRITER_URL` is set.
2. **Standardize on `X-Inter-Cloud-Token`** header for all cross-cloud authentication (validated via research).
3. Add **deployer code** for Ingestion and Writer functions.
4. Update **Persister deployer code** to inject multi-cloud env vars.
5. Create **comprehensive documentation** with flowcharts.
6. Add **extensive tests** for all edge cases.

### Impact
- Enables true multi-cloud deployments from L1 → L2 → L3.
- Consistent authentication simplifies security.
- Documentation enables users to understand multi-cloud architecture.

---

## 2. Current State

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CURRENT AWS GLUECODE FLOW                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  L1 (Remote Cloud)                    L2 (AWS)                  L3 (AWS)    │
│  ┌──────────────┐                    ┌──────────────┐         ┌──────────┐  │
│  │  Connector   │──HTTP POST──>      │  Ingestion   │──────>  │Processor │  │
│  │  (GCP/Azure) │                    │  Function ✅ │         │          │  │
│  └──────────────┘                    └──────────────┘         └────┬─────┘  │
│                                                                    │        │
│                                                                    ▼        │
│  L1 (AWS)                            L2 (AWS)                    ┌───────┐  │
│  ┌──────────────┐                    ┌──────────────┐            │       │  │
│  │  Dispatcher  │──Invoke──>         │  Processor   │──Invoke──>│Persist│  │
│  │              │                    │              │            │  er   │  │
│  └──────────────┘                    └──────────────┘            │  ⚠️   │  │
│                        ┌────────────────────────────────────────┬┘       │  │
│                        │             WRITES ONLY LOCALLY        │        │  │
│                        ▼                                        ▼        │  │
│                    ┌──────────────┐                      ┌─────────────┐ │  │
│                    │  DynamoDB ✅ │                      │ Remote      │ │  │
│                    │  (Local L3)  │                      │ Writer ❌   │ │  │
│                    └──────────────┘                      │ NOT CALLED  │ │  │
│                                                          └─────────────┘ │  │
│                                                                          │  │
│  L2 (Remote Cloud)                   L3 (AWS)                            │  │
│  ┌──────────────┐                    ┌──────────────┐                    │  │
│  │  Remote      │──HTTP POST──>      │  Writer      │──────> DynamoDB   │  │
│  │  Persister   │                    │  Function ✅ │                    │  │
│  └──────────────┘                    └──────────────┘                    │  │
│                                                                          │  │
└──────────────────────────────────────────────────────────────────────────────┘

Legend:  ✅ = Implemented    ⚠️ = Missing Multi-Cloud Logic    ❌ = Not Called
```

---

## 3. Deep Investigation: Gap Analysis

> **Scope:** This section documents ALL gaps identified during thorough investigation of the codebase, technical specs, and cloud provider documentation to ensure complete AWS multi-cloud interoperability.

### A. Lambda Function Code Gaps

| Component | File | Gap | Status |
|-----------|------|-----|--------|
| **Persister** | `persister/lambda_function.py` | Missing `REMOTE_WRITER_URL` check and HTTP POST logic | ❌ Not implemented |
| **Persister** | `persister/lambda_function.py` | Missing `_is_multi_cloud_storage()` dual validation | ❌ Not implemented |
| **Connector** | `connector/lambda_function.py` | Uses `"source": "aws"` instead of `"source_cloud": "aws"` | ❌ Needs update |
| **Connector** | `connector/lambda_function.py` | Missing other envelope fields (`target_layer`, `message_type`, etc.) | 📋 TODO (future) |
| **Ingestion** | `ingestion/lambda_function.py` | Reads `body.get("source")` but should read `body.get("source_cloud")` | ❌ Needs update |
| **Ingestion** | `ingestion/lambda_function.py` | Missing source-cloud logging | ⚠️ Minor |
| **Writer** | `writer/lambda_function.py` | Expects `payload` key but doesn't log source | ⚠️ Minor |

### B. Deployer Code Gaps

| Component | File | Gap | Status |
|-----------|------|-----|--------|
| **Connector Deployer** | `layer_2_compute.py` | ✅ Exists in `create_processor_lambda_function()` | ✅ Implemented |
| **Ingestion Deployer** | `layer_2_compute.py` | Missing `create_ingestion_*` functions | ❌ Not implemented |
| **Writer Deployer** | `layer_3_storage.py` | Missing `create_writer_*` functions | ❌ Not implemented |
| **Persister Deployer** | `layer_2_compute.py` | Missing multi-cloud env var injection | ⚠️ Needs update |
| **`_get_digital_twin_info`** | `layer_2_compute.py` | Missing `config_providers` field | ❌ Needs update |
| **`_get_digital_twin_info`** | `layer_3_storage.py` | Missing `config_providers` field (separate copy!) | ❌ Needs update |
| **`digital_twin_info`** | `layer_1_iot.py` | Inline dict, missing `config_providers` | ❌ Needs update |

### B2. Naming Convention Gaps

> **Missing:** IAM role naming functions for Ingestion and Writer.

| Function | File | Status | Required Change |
|----------|------|--------|-----------------|
| `ingestion_iam_role()` | `naming.py` | ❌ Missing | Add: `return f"{self._twin_name}-ingestion"` |
| `writer_iam_role()` | `naming.py` | ❌ Missing | Add: `return f"{self._twin_name}-writer"` |

### B3. Layer Adapter Gaps (CRITICAL!)

> **Warning:** The layer adapters do NOT have conditional logic to deploy OR destroy the multi-cloud gluecode functions!

| Adapter | Function | Missing Logic | Required Change |
|---------|----------|---------------|-----------------|
| **L2 Adapter** | `deploy_l2()` | No Ingestion deployment when L1 is remote | Add: `if l1_provider != "aws": create_ingestion_*()` |
| **L2 Adapter** | `destroy_l2()` | No Ingestion destruction when L1 is remote | Add: `if l1_provider != "aws": destroy_ingestion_*()` |
| **L3 Adapter** | `deploy_l3_hot()` | No Writer deployment when L2 is remote | Add: `if l2_provider != "aws": create_writer_*()` |
| **L3 Adapter** | `destroy_l3_hot()` | No Writer destruction when L2 is remote | Add: `if l2_provider != "aws": destroy_writer_*()` |

### C. Function URL Creation Gaps

AWS Lambda Function URLs require **two API calls** (from boto3 documentation):
1. `lambda_client.create_function_url_config(FunctionName=..., AuthType='NONE')`
2. `lambda_client.add_permission(FunctionName=..., Principal='*', Action='lambda:InvokeFunctionUrl', FunctionUrlAuthType='NONE', ...)`

| Function | Function URL Needed? | Current Status |
|----------|---------------------|----------------|
| **Ingestion** | ✅ Yes (receives from remote Connector) | ❌ Not implemented |
| **Writer** | ✅ Yes (receives from remote Persister) | ❌ Not implemented |
| **Connector** | ❌ No (makes outbound calls) | N/A |
| **Persister** | ❌ No (makes outbound calls) | N/A |

### C2. Credentials Checker Permissions Gap (IMPORTANT!)

> **Missing:** The `credentials_checker.py` file needs to include the new Lambda Function URL permissions.

| File | Location | Missing Permissions | Priority |
|------|----------|---------------------|----------|
| `credentials_checker.py` | `REQUIRED_AWS_PERMISSIONS["layer_2"]["lambda"]` | `lambda:CreateFunctionUrlConfig`, `lambda:DeleteFunctionUrlConfig`, `lambda:GetFunctionUrlConfig` | ⚡ Critical |
| `credentials_checker.py` | `REQUIRED_AWS_PERMISSIONS["layer_3"]["lambda"]` | Same permissions (for Writer) | ⚡ Critical |

**Required Changes:**
```python
# In credentials_checker.py, update REQUIRED_AWS_PERMISSIONS:

"layer_2": {
    # ... existing ...
    "lambda": [
        "lambda:CreateFunctionUrlConfig",   # NEW: For Ingestion Function URL
        "lambda:DeleteFunctionUrlConfig",   # NEW: For Ingestion Function URL
        "lambda:GetFunctionUrlConfig",      # NEW: For Ingestion Function URL
    ],
},
"layer_3": {
    # ... existing ...
    "lambda": [
        "lambda:CreateFunctionUrlConfig",   # NEW: For Writer Function URL
        "lambda:DeleteFunctionUrlConfig",   # NEW: For Writer Function URL
        "lambda:GetFunctionUrlConfig",      # NEW: For Writer Function URL
    ],
},
```

### D. Layer Adapter Gaps

The layer adapters (`l2_adapter.py`, `l3_adapter.py`) need to **conditionally call** the new deployer functions:

| Adapter | Missing Logic | Required Change |
|---------|---------------|-----------------|
| **l2_adapter.py** | Ingestion deployment when L1 is on different cloud | Add: `if l1_provider != "aws": create_ingestion_*()` |
| **l3_adapter.py** | Writer deployment when L2 is on different cloud | Add: `if l2_provider != "aws": create_writer_*()` |

### E. Payload Envelope Verification

Per `technical_specs.md`, the standard envelope should include:

```json
{
  "source_cloud": "aws",
  "target_layer": "L2",
  "message_type": "telemetry",
  "timestamp": "2023-10-27T10:00:00Z",
  "payload": { ... },
  "trace_id": "abc-123-xyz"
}
```

**Current Implementation Check:**
| Function | Field | Implemented? |
|----------|-------|--------------|
| Connector | `source` | ✅ Yes (`"aws"`) |
| Connector | `source_cloud` | ❌ Uses `source` instead |
| Connector | `target_layer` | ❌ Missing |
| Connector | `message_type` | ❌ Missing |
| Connector | `trace_id` | ❌ Missing |

**Implementation:** Use full envelope structure with proper field names. Fields marked as TODO will be populated in future work.

```json
{
  "source_cloud": "aws",
  "target_layer": "L2",
  "message_type": "telemetry",
  "timestamp": "2023-10-27T10:00:00Z",
  "payload": { ... },
  "trace_id": null
}
```

**Current Implementation:**
| Field | Status | Notes |
|-------|--------|-------|
| `source_cloud` | ✅ Implement now | Rename from `source` to match spec |
| `payload` | ✅ Implement now | Core data |
| `target_layer` | 📋 TODO | Set to target layer ("L2", "L3") |
| `message_type` | 📋 TODO | Always "telemetry" for now |
| `timestamp` | 📋 TODO | Add ISO8601 timestamp |
| `trace_id` | 📋 TODO | Future: correlation tracking |

> **Future Work TODO:** Populate `target_layer`, `message_type`, `timestamp`, and `trace_id` fields for comprehensive observability and tracing. These fields will enable cross-cloud request correlation, latency measurement, and debugging.

### F. Destroy and Info Functions

For complete lifecycle management, all new deployer functions need corresponding destroy/info functions:

| Function Type | Create | Destroy | Info/Check |
|--------------|--------|---------|------------|
| Ingestion IAM Role | ⬜ NEW | ⬜ NEW | ⬜ NEW |
| Ingestion Lambda | ⬜ NEW | ⬜ NEW | ⬜ NEW |
| Ingestion Function URL | ⬜ NEW | ⬜ NEW | ⬜ NEW |
| Writer IAM Role | ⬜ NEW | ⬜ NEW | ⬜ NEW |
| Writer Lambda | ⬜ NEW | ⬜ NEW | ⬜ NEW |
| Writer Function URL | ⬜ NEW | ⬜ NEW | ⬜ NEW |

### G. config_inter_cloud.json Schema

Existing schema in `config_loader.py` expects:
```json
{
  "connections": {
    "aws_l1_to_azure_l2": {
      "url": "https://...",
      "token": "secret-token"
    },
    "gcp_l2_to_aws_l3": {
      "url": "https://...",
      "token": "secret-token"
    }
  }
}
```

**Validation:** Add schema validation for `config_inter_cloud.json` in Phase 1.

### H. Summary: Complete Implementation Checklist

Based on this deep investigation, the **complete** implementation requires:

| # | Category | Item | Priority |
|---|----------|------|----------|
| **Lambda Function Changes** | | |
| 1 | Lambda | Persister: Add multi-cloud logic with dual validation | ⚡ Critical |
| 2 | Lambda | Connector: Change `"source"` → `"source_cloud"` + add timestamp/trace_id | ⚡ Critical |
| 3 | Lambda | Ingestion: Change `body.get("source")` → `body.get("source_cloud")` | ⚡ Critical |
| 4 | Lambda | Ingestion: Add source-cloud logging | 📋 Normal |
| 5 | Lambda | Writer: Add source-cloud logging | 📋 Normal |
| **Helper Function Updates** | | |
| 6 | Helper | `layer_2_compute.py`: Update `_get_digital_twin_info()` to include `config_providers` | ⚡ Critical |
| 7 | Helper | `layer_3_storage.py`: Update `_get_digital_twin_info()` to include `config_providers` | ⚡ Critical |
| 8 | Helper | `layer_1_iot.py`: Update inline `digital_twin_info` dict to include `config_providers` | ⚡ Critical |
| **Naming Functions** | | |
| 9 | Naming | Add `ingestion_iam_role()` to `naming.py` | ⚡ Critical |
| 10 | Naming | Add `writer_iam_role()` to `naming.py` | ⚡ Critical |
| **Deployer Functions** | | |
| 11 | Deployer | Update `create_persister_lambda_function()` with multi-cloud env vars | ⚡ Critical |
| 12 | Deployer | Add `create_ingestion_iam_role()` | ⚡ Critical |
| 13 | Deployer | Add `create_ingestion_lambda_function()` with Function URL | ⚡ Critical |
| 14 | Deployer | Add `destroy_ingestion_iam_role()` | ⚡ Critical |
| 15 | Deployer | Add `destroy_ingestion_lambda_function()` | ⚡ Critical |
| 16 | Deployer | Add `create_writer_iam_role()` | ⚡ Critical |
| 17 | Deployer | Add `create_writer_lambda_function()` with Function URL | ⚡ Critical |
| 18 | Deployer | Add `destroy_writer_iam_role()` | ⚡ Critical |
| 19 | Deployer | Add `destroy_writer_lambda_function()` | ⚡ Critical |
| **Adapter Conditional Logic** | | |
| 20 | Adapter | `deploy_l2()`: Add conditional Ingestion deployment when L1 ≠ aws | ⚡ Critical |
| 21 | Adapter | `destroy_l2()`: Add conditional Ingestion destruction when L1 ≠ aws | ⚡ Critical |
| 22 | Adapter | `deploy_l3_hot()`: Add conditional Writer deployment when L2 ≠ aws | ⚡ Critical |
| 23 | Adapter | `destroy_l3_hot()`: Add conditional Writer destruction when L2 ≠ aws | ⚡ Critical |
| **Tests** | | |
| 24 | Tests | 56 unit tests across 4 files (comprehensive edge cases) | ⚡ Critical |
| **Credentials Checker** | | |
| 25 | CredChk | Add `lambda:CreateFunctionUrlConfig` to `REQUIRED_AWS_PERMISSIONS["layer_2"]["lambda"]` | ⚡ Critical |
| 26 | CredChk | Add `lambda:DeleteFunctionUrlConfig` to `REQUIRED_AWS_PERMISSIONS["layer_2"]["lambda"]` | ⚡ Critical |
| 27 | CredChk | Add same permissions to `REQUIRED_AWS_PERMISSIONS["layer_3"]["lambda"]` | ⚡ Critical |
| **Documentation** | | |
| 28 | Docs | New multi-cloud documentation page | 📋 Normal |
| 29 | Docs | Update existing roadmap docs | 📋 Normal |

---

## 4. Authentication Strategy

### Research Summary

Based on cloud provider documentation research:

| Cloud | Native Auth | Custom Header Support | Recommendation |
|-------|-------------|----------------------|----------------|
| **AWS Lambda** | SigV4, IAM | ✅ Via `event.headers` | Use `X-Inter-Cloud-Token` |
| **Azure Functions** | Function Keys, AAD | ✅ Via `req.headers` | Use `X-Inter-Cloud-Token` |
| **GCP Cloud Functions** | OIDC, IAM | ✅ Via `request.headers` | Use `X-Inter-Cloud-Token` |

**Conclusion:** All three clouds support custom HTTP header validation in Python. The `X-Inter-Cloud-Token` approach is simple, consistent, and works everywhere.

### Standardized Token Validation Pattern

```python
# Universal pattern for all clouds
def validate_inter_cloud_token(headers: dict, expected_token: str) -> bool:
    """Validate X-Inter-Cloud-Token header (case-insensitive)."""
    for k, v in headers.items():
        if k.lower() == "x-inter-cloud-token":
            return v == expected_token
    return False
```

---

## 5. Proposed Changes

### Component: AWS Lambda Functions

---

#### [MODIFY] [persister/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/persister/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/persister/lambda_function.py`
- **Description:** Add multi-cloud logic to detect `REMOTE_WRITER_URL` and POST to remote Writer API.

**Proposed Logic (Dual Validation):**

> **Important:** To avoid misconfiguration, we implement **dual validation**: both the `REMOTE_WRITER_URL` environment variable AND the provider mapping in `DIGITAL_TWIN_INFO` must indicate multi-cloud mode.

```python
def _is_multi_cloud_storage() -> bool:
    """
    Check if L3 storage is on a different cloud.
    
    Returns True only if:
    1. REMOTE_WRITER_URL is set AND non-empty
    2. layer_2_provider != layer_3_hot_provider in DIGITAL_TWIN_INFO
    
    Raises:
        ConfigurationError: If config_providers is missing from DIGITAL_TWIN_INFO
    """
    remote_url = os.environ.get("REMOTE_WRITER_URL", "").strip()
    if not remote_url:
        return False
    
    providers = DIGITAL_TWIN_INFO.get("config_providers")
    if providers is None:
        raise ConfigurationError(
            "CRITICAL: 'config_providers' missing from DIGITAL_TWIN_INFO. "
            "This indicates a deployment configuration error. "
            "Ensure deployer injects config.providers into DIGITAL_TWIN_INFO."
        )
    
    l2_provider = providers.get("layer_2_provider")
    l3_provider = providers.get("layer_3_hot_provider")
    
    if l2_provider is None or l3_provider is None:
        raise ConfigurationError(
            f"CRITICAL: Missing provider mapping. "
            f"layer_2_provider={l2_provider}, layer_3_hot_provider={l3_provider}"
        )
    
    if l2_provider == l3_provider:
        print(f"Warning: REMOTE_WRITER_URL is set but providers match ({l2_provider}). Using local write.")
        return False
    
    return True

def lambda_handler(event, context):
    # ... validation ...
    
    if _is_multi_cloud_storage():
        remote_url = os.environ.get("REMOTE_WRITER_URL")
        token = os.environ.get("INTER_CLOUD_TOKEN", "").strip()
        if not token:
            raise ValueError("Multi-cloud mode enabled but INTER_CLOUD_TOKEN is missing or empty")
        _post_to_remote_writer(remote_url, item)
    else:
        # Single-Cloud: Write locally
        dynamodb_table.put_item(Item=item)

def _post_to_remote_writer(url: str, data: dict) -> dict:
    """POST data to remote Writer API with exponential backoff."""
    token = os.environ.get("INTER_CLOUD_TOKEN")
    
    # Full envelope per technical_specs.md
    payload = {
        "source_cloud": "aws",         # Renamed from 'source' per spec
        "target_layer": "L3",          # TODO: Make configurable
        "message_type": "telemetry",   # TODO: Support other types
        "timestamp": None,             # TODO: Add ISO8601 timestamp
        "payload": data,
        "trace_id": None               # TODO: Add correlation ID
    }
    # ... retry logic matching Connector ...
```

**Edge Cases Handled:**
| Edge Case | Handling |
|-----------|----------|
| `REMOTE_WRITER_URL` empty string | Treated as not set → local write |
| `REMOTE_WRITER_URL` whitespace only | `.strip()` → treated as empty → local write |
| URL set but providers match | Warning logged → local write (fail-safe) |
| URL set, providers differ, token empty | `ValueError` raised (fail-fast) |

---

#### [MODIFY] [ingestion/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/ingestion/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/ingestion/lambda_function.py`
- **Description:** Add source-cloud logging.

**Change:**
```python
source_cloud = body.get("source_cloud", "unknown")  # Renamed from 'source' per spec
print(f"Received event from source cloud: {source_cloud}")
```

---

#### [MODIFY] [writer/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/writer/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/writer/lambda_function.py`
- **Description:** Add source-cloud logging.

---

#### [MODIFY] [connector/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/connector/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/connector/lambda_function.py`
- **Description:** Update payload envelope to use `source_cloud` instead of `source`.

**Change:**
```python
# Current (line 15-18):
payload = {
    "source": "aws",
    "payload": event
}

# Updated:
import uuid
from datetime import datetime, timezone

payload = {
    "source_cloud": "aws",                                          # Renamed per technical_specs.md
    "target_layer": "L2",                                           # TODO: Make configurable per call
    "message_type": "telemetry",                                    # TODO: Support other types
    "timestamp": datetime.now(timezone.utc).isoformat(),            # Current UTC (TODO: verify format matches spec)
    "payload": event,
    "trace_id": str(uuid.uuid4())                                   # Random GUID (TODO: propagate through chain)
}
```

---

### Component: Deployer Code

---

#### [MODIFY] [layer_2_compute.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/layer_2_compute.py)
- **Path:** `src/providers/aws/layers/layer_2_compute.py`
- **Description:** Update `create_persister_lambda_function()` to inject multi-cloud env vars when L3 is remote.

**Proposed Change:**

> **Important:** The `_get_digital_twin_info()` helper must be updated to include `config_providers` so Lambda functions can validate provider mapping.

```python
# Step 1: Update _get_digital_twin_info() to include providers
def _get_digital_twin_info(config: 'ProjectConfig') -> dict:
    """Build digital twin info dict for Lambda environment."""
    return {
        "config": {
            "digital_twin_name": config.digital_twin_name,
            "hot_storage_size_in_days": config.hot_storage_size_in_days,
            "cold_storage_size_in_days": config.cold_storage_size_in_days,
            "mode": config.mode,
        },
        "config_iot_devices": config.iot_devices,
        "config_events": config.events,
        "config_providers": config.providers  # NEW: Add provider mapping
    }

# Step 2: Update create_persister_lambda_function()
def create_persister_lambda_function(...):
    # ... existing code ...
    
    env_vars = {
        "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),  # Now includes providers
        "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table(),
        "EVENT_CHECKER_LAMBDA_NAME": provider.naming.event_checker_lambda_function(),
        "USE_EVENT_CHECKING": str(config.is_optimization_enabled("useEventChecking")).lower()
    }
    
    # Multi-cloud: Add remote writer URL if L3 is on different cloud
    l2_provider = config.providers.get("layer_2_provider", "aws")
    l3_provider = config.providers.get("layer_3_hot_provider", "aws")
    
    if l3_provider != l2_provider:
        connections = config.inter_cloud.get("connections", {}) if hasattr(config, "inter_cloud") else {}
        conn_id = f"{l2_provider}_l2_to_{l3_provider}_l3"
        conn = connections.get(conn_id, {})
        url = conn.get("url", "")
        token = conn.get("token", "")
        
        # Validate configuration at deployment time
        if not url or not token:
            raise ConfigurationError(
                f"Multi-cloud config incomplete for {conn_id}: url={bool(url)}, token={bool(token)}"
            )
        
        env_vars["REMOTE_WRITER_URL"] = url
        env_vars["INTER_CLOUD_TOKEN"] = token
    
    lambda_client.create_function(
        ...
        Environment={"Variables": env_vars}
    )
```

**Files affected by `_get_digital_twin_info` / `digital_twin_info` change:**
| File | Impact |
|------|--------|
| `layer_2_compute.py` | Primary - update `_get_digital_twin_info()` function |
| `layer_3_storage.py` | Has separate copy - must also update |
| `layer_1_iot.py` | Inline dict in `create_dispatcher_lambda_function()` - must add `config_providers` |

---

#### [NEW] Ingestion Function Deployer
- **Path:** `src/providers/aws/layers/layer_2_compute.py`
- **Description:** Add `create_ingestion_lambda_function()` and `destroy_ingestion_lambda_function()`.

**Purpose:** Deploy Ingestion function when L1 is on a different cloud (receives data FROM remote Connector).

```python
def create_ingestion_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Ingestion Lambda (multi-cloud only)."""
    # Similar to dispatcher role with Lambda invoke permissions
    
def create_ingestion_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """Creates the Ingestion Lambda Function with Function URL."""
    # Only created if L1 is on a different cloud
    # Sets up Function URL for HTTP access
    # Injects INTER_CLOUD_TOKEN for validation
```

---

#### [NEW] Writer Function Deployer
- **Path:** `src/providers/aws/layers/layer_3_storage.py`
- **Description:** Add `create_writer_lambda_function()` and `destroy_writer_lambda_function()`.

**Purpose:** Deploy Writer function when L2 is on a different cloud (receives data FROM remote Persister).

```python
def create_writer_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Writer Lambda (multi-cloud only)."""
    # DynamoDB write access
    
def create_writer_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> None:
    """Creates the Writer Lambda Function with Function URL."""
    # Only created if L2 is on a different cloud
    # Sets up Function URL for HTTP access
    # Injects INTER_CLOUD_TOKEN and DYNAMODB_TABLE_NAME
```

---

### Component: Layer Adapters (Conditional Deployment Logic)

> **CRITICAL:** The adapters currently do NOT deploy Ingestion/Writer when needed. This is the glue that connects the deployer functions to the deployment flow.

---

#### [MODIFY] [l2_adapter.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/l2_adapter.py)
- **Path:** `src/providers/aws/layers/l2_adapter.py`
- **Description:** Add conditional deployment of Ingestion function when L1 is on a different cloud.

**Change in `deploy_l2()`:**
```python
def deploy_l2(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    # ... existing code ...
    
    # NEW: Deploy Ingestion if L1 is on a different cloud
    l1_provider = context.config.providers.get("layer_1_provider", "aws")
    if l1_provider != "aws":
        from .layer_2_compute import (
            create_ingestion_iam_role,
            create_ingestion_lambda_function,
        )
        logger.info("[L2] Deploying Ingestion function for multi-cloud (L1 is remote)...")
        create_ingestion_iam_role(provider)
        create_ingestion_lambda_function(provider, context.config, tool_root)
```

---

#### [MODIFY] [l3_adapter.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/l3_adapter.py)
- **Path:** `src/providers/aws/layers/l3_adapter.py`
- **Description:** Add conditional deployment of Writer function when L2 is on a different cloud.

**Change in `deploy_l3_hot()`:**
```python
def deploy_l3_hot(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    # ... existing code ...
    
    # NEW: Deploy Writer if L2 is on a different cloud
    l2_provider = context.config.providers.get("layer_2_provider", "aws")
    if l2_provider != "aws":
        from .layer_3_storage import (
            create_writer_iam_role,
            create_writer_lambda_function,
        )
        logger.info("[L3-Hot] Deploying Writer function for multi-cloud (L2 is remote)...")
        create_writer_iam_role(provider)
        create_writer_lambda_function(provider, context.config, project_path)
```

---

### Component: Unit Tests

---

#### [MODIFY] [test_persister.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/lambda_functions/test_persister.py)
- **Path:** `tests/unit/lambda_functions/test_persister.py`
- **Description:** Add comprehensive tests for multi-cloud scenarios.

**New Tests (18 tests):**

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| **Basic Multi-Cloud** | | |
| `test_single_cloud_writes_to_dynamodb` | No `REMOTE_WRITER_URL` | DynamoDB called |
| `test_multi_cloud_posts_to_remote_writer` | URL set, providers differ | HTTP POST, no DynamoDB |
| **Dual Validation Edge Cases** | | |
| `test_empty_url_uses_local_write` | `REMOTE_WRITER_URL=""` | DynamoDB called (local) |
| `test_whitespace_url_uses_local_write` | `REMOTE_WRITER_URL="  "` | DynamoDB called (local) |
| `test_url_set_but_providers_match_uses_local` | URL set, L2=L3=aws | Warning logged, DynamoDB called |
| `test_url_missing_but_providers_differ_uses_local` | No URL, L2≠L3 | DynamoDB called (local) |
| `test_missing_config_providers_raises_error` | `DIGITAL_TWIN_INFO` without `config_providers` | ConfigurationError raised |
| **Token Validation** | | |
| `test_multi_cloud_fails_on_missing_token` | URL set, no token | ValueError raised |
| `test_multi_cloud_fails_on_empty_token` | `INTER_CLOUD_TOKEN=""` | ValueError raised |
| `test_multi_cloud_fails_on_whitespace_token` | `INTER_CLOUD_TOKEN="  "` | ValueError raised |
| **Payload Format** | | |
| `test_payload_uses_source_cloud_field` | Valid POST | `source_cloud` in envelope |
| `test_payload_includes_all_envelope_fields` | Valid POST | All 6 envelope fields present |
| `test_timestamp_is_valid_iso8601` | Valid POST | Timestamp is valid ISO8601 |
| `test_trace_id_is_valid_uuid` | Valid POST | trace_id is valid UUID format |
| **Retry Logic** | | |
| `test_multi_cloud_retry_on_server_error` | Remote returns 500 | 3 retry attempts |
| `test_multi_cloud_client_error_no_retry` | Remote returns 400 | No retry, immediate fail |
| `test_multi_cloud_timeout_handling` | Connection timeout | Retry with backoff |
| `test_multi_cloud_dns_resolution_failure` | Invalid hostname | Proper error message |

---

#### [NEW] [test_ingestion.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/lambda_functions/test_ingestion.py)
- **Path:** `tests/unit/lambda_functions/test_ingestion.py`
- **Description:** Test Ingestion function token validation and processor invocation.

**Tests:**

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_valid_token_invokes_processor` | Valid token | Processor Lambda invoked |
| `test_invalid_token_returns_403` | Wrong token | 403 Unauthorized |
| `test_missing_token_returns_403` | No token header | 403 Unauthorized |
| `test_empty_token_returns_403` | Empty token value | 403 Unauthorized |
| `test_case_insensitive_header` | `X-INTER-CLOUD-TOKEN` | Token validated |
| `test_missing_iot_device_id_returns_400` | No `iotDeviceId` | 400 Bad Request |
| `test_malformed_payload_returns_400` | Invalid JSON | 400 Bad Request |
| `test_missing_body_returns_400` | No request body | 400 Bad Request |
| `test_source_cloud_field_extraction` | Valid request | `source_cloud` field read correctly |
| `test_source_cloud_logging` | Valid request | Source cloud logged |
| `test_processor_invoke_failure` | Lambda invoke fails | 500 Internal Error |
| `test_missing_digital_twin_info_fails` | No DIGITAL_TWIN_INFO env | Graceful error |

---

#### [NEW] [test_writer.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/lambda_functions/test_writer.py)
- **Path:** `tests/unit/lambda_functions/test_writer.py`
- **Description:** Test Writer function token validation and DynamoDB write.

**Tests:**

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_valid_token_writes_to_dynamodb` | Valid token | DynamoDB put_item called |
| `test_invalid_token_returns_403` | Wrong token | 403 Unauthorized |
| `test_missing_token_returns_403` | No token header | 403 Unauthorized |
| `test_empty_token_returns_403` | Empty token value | 403 Unauthorized |
| `test_raw_payload_mode` | Payload without wrapper | Data written directly |
| `test_wrapped_payload_mode` | Payload with `payload` key | Inner data extracted |
| `test_non_dict_payload_returns_400` | Array or string payload | 400 Bad Request |
| `test_missing_body_returns_400` | No request body | 400 Bad Request |
| `test_missing_time_field_fails` | No `time` in payload | Validation error |
| `test_dynamodb_write_failure` | DynamoDB error | 500 Internal Error |
| `test_source_cloud_logging` | Valid request | Source cloud logged |
| `test_missing_table_name_env_fails` | No DYNAMODB_TABLE_NAME | Graceful error |

---

#### [NEW] [test_connector.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/lambda_functions/test_connector.py)
- **Path:** `tests/unit/lambda_functions/test_connector.py`
- **Description:** Test Connector function HTTP POST and retry logic.

**Tests:**

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_successful_post` | Remote returns 200 | Success response |
| `test_retry_on_500` | Remote returns 500 | 3 retries with backoff |
| `test_retry_on_503` | Remote returns 503 ServiceUnavailable | 3 retries with backoff |
| `test_no_retry_on_400` | Remote returns 400 | Immediate failure |
| `test_no_retry_on_401` | Remote returns 401 | Immediate failure |
| `test_missing_url_raises_error` | No `REMOTE_INGESTION_URL` | ValueError |
| `test_empty_url_raises_error` | `REMOTE_INGESTION_URL=""` | ValueError |
| `test_missing_token_raises_error` | No `INTER_CLOUD_TOKEN` | ValueError |
| `test_empty_token_raises_error` | `INTER_CLOUD_TOKEN=""` | ValueError |
| `test_payload_envelope_format` | POST body | Contains `source_cloud`, payload |
| `test_envelope_has_timestamp` | POST body | `timestamp` is valid ISO8601 |
| `test_envelope_has_trace_id` | POST body | `trace_id` is valid UUID |
| `test_exponential_backoff_timing` | Multiple retries | Delay doubles each time |
| `test_connection_timeout_retry` | Network error | Retry with backoff |

---

### Component: Documentation

---

#### [NEW] [docs-multi-cloud.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-multi-cloud.html)
- **Path:** `docs/docs-multi-cloud.html`
- **Description:** New documentation page explaining multi-cloud architecture in detail.

**Content Structure:**
1. Overview of multi-cloud deployment
2. Authentication mechanism (`X-Inter-Cloud-Token`)
3. Gluecode function roles (Connector, Ingestion, Persister, Writer)
4. Data flow diagrams with single-cloud vs multi-cloud comparison
5. Configuration guide (`config_inter_cloud.json`)
6. Detailed flowcharts (ASCII art)

**Example Flowchart (to be included in docs):**
```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                           MULTI-CLOUD DATA FLOW DECISION TREE                               │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  ╔═══════════════════╗                                                                      │
│  ║   IoT Device      ║                                                                      │
│  ║   Publishes Data  ║                                                                      │
│  ╚═════════╦═════════╝                                                                      │
│            │                                                                                │
│            ▼                                                                                │
│  ┌─────────────────────┐                                                                    │
│  │  L1: DISPATCHER     │                                                                    │
│  │  (IoT Core Topic)   │                                                                    │
│  └──────────┬──────────┘                                                                    │
│             │                                                                               │
│             ▼                                                                               │
│  ╔══════════════════════════════════════════════════════════════════════╗                   │
│  ║  IS L2 ON SAME CLOUD AS L1?                                          ║                   │
│  ╚══════════════════════════════════════════════════════════════════════╝                   │
│             │                                                                               │
│     ┌───────┴───────┐                                                                       │
│     │               │                                                                       │
│     ▼ YES           ▼ NO                                                                    │
│  ┌──────────┐    ┌──────────────────────────────────────────────────────────┐               │
│  │ INVOKE   │    │  INVOKE CONNECTOR                                        │               │
│  │ LOCAL    │    │  (wraps event, POSTs to REMOTE_INGESTION_URL)            │               │
│  │ PROCESSOR│    │                                                          │               │
│  └────┬─────┘    │       ┌────────────────────────────────────┐             │               │
│       │          │       │  HTTP POST with X-Inter-Cloud-Token│             │               │
│       │          │       └──────────────┬─────────────────────┘             │               │
│       │          │                      │                                   │               │
│       │          │                      ▼                                   │               │
│       │          │           ┌─────────────────────┐                        │               │
│       │          │           │  L2 INGESTION       │ (on remote cloud)      │               │
│       │          │           │  - Validates token  │                        │               │
│       │          │           │  - Invokes processor│                        │               │
│       │          │           └──────────┬──────────┘                        │               │
│       │          └──────────────────────┼───────────────────────────────────┘               │
│       │                                 │                                                   │
│       └─────────────┬───────────────────┘                                                   │
│                     │                                                                       │
│                     ▼                                                                       │
│          ┌─────────────────────┐                                                            │
│          │  L2: PROCESSOR      │                                                            │
│          │  (validates, cleans)│                                                            │
│          └──────────┬──────────┘                                                            │
│                     │                                                                       │
│                     ▼                                                                       │
│          ┌─────────────────────┐                                                            │
│          │  L2: PERSISTER      │                                                            │
│          └──────────┬──────────┘                                                            │
│                     │                                                                       │
│  ╔══════════════════════════════════════════════════════════════════════╗                   │
│  ║  IS L3 ON SAME CLOUD AS L2?                                          ║                   │
│  ╚══════════════════════════════════════════════════════════════════════╝                   │
│                     │                                                                       │
│     ┌───────────────┴───────────────┐                                                       │
│     │                               │                                                       │
│     ▼ YES                           ▼ NO                                                    │
│  ┌──────────────┐         ┌──────────────────────────────────────────────────┐              │
│  │ WRITE TO     │         │  POST TO REMOTE_WRITER_URL                       │              │
│  │ LOCAL DB     │         │  (with X-Inter-Cloud-Token)                      │              │
│  │ (DynamoDB,   │         │                                                  │              │
│  │  Cosmos,     │         │       ┌────────────────────────────────────┐     │              │
│  │  Firestore)  │         │       │  HTTP POST with X-Inter-Cloud-Token│     │              │
│  └──────┬───────┘         │       └──────────────┬─────────────────────┘     │              │
│         │                 │                      │                           │              │
│         │                 │                      ▼                           │              │
│         │                 │           ┌─────────────────────┐                │              │
│         │                 │           │  L3 WRITER          │ (on L3 cloud)  │              │
│         │                 │           │  - Validates token  │                │              │
│         │                 │           │  - Writes to DB     │                │              │
│         │                 │           └──────────┬──────────┘                │              │
│         │                 └──────────────────────┼───────────────────────────┘              │
│         │                                        │                                          │
│         └────────────────┬───────────────────────┘                                          │
│                          │                                                                  │
│                          ▼                                                                  │
│               ╔════════════════════╗                                                        │
│               ║   DATA PERSISTED   ║                                                        │
│               ║   IN HOT STORAGE   ║                                                        │
│               ╚════════════════════╝                                                        │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

#### [MODIFY] [docs-nav.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-nav.html)
- **Path:** `docs/docs-nav.html`
- **Description:** Add link to new Multi-Cloud Architecture documentation page.

---

## 6. Implementation Phases

### Phase 1: Persister Multi-Cloud Logic

| Step | File | Action |
|------|------|--------|
| 1.1 | `persister/lambda_function.py` | Add `REMOTE_WRITER_URL` check |
| 1.2 | `persister/lambda_function.py` | Add `_post_to_remote_writer()` with retry |

### Phase 2: Update Persister Deployer

| Step | File | Action |
|------|------|--------|
| 2.1 | `layer_2_compute.py` | Update `create_persister_lambda_function()` to inject multi-cloud env vars |

### Phase 3: Add Ingestion Deployer Code

| Step | File | Action |
|------|------|--------|
| 3.1 | `layer_2_compute.py` | Add `create_ingestion_iam_role()` |
| 3.2 | `layer_2_compute.py` | Add `create_ingestion_lambda_function()` with Function URL |
| 3.3 | `layer_2_compute.py` | Add `destroy_ingestion_iam_role()` |
| 3.4 | `layer_2_compute.py` | Add `destroy_ingestion_lambda_function()` |

### Phase 4: Add Writer Deployer Code

| Step | File | Action |
|------|------|--------|
| 4.1 | `layer_3_storage.py` | Add `create_writer_iam_role()` |
| 4.2 | `layer_3_storage.py` | Add `create_writer_lambda_function()` with Function URL |
| 4.3 | `layer_3_storage.py` | Add `destroy_writer_iam_role()` |
| 4.4 | `layer_3_storage.py` | Add `destroy_writer_lambda_function()` |

### Phase 5: Add Source Logging

| Step | File | Action |
|------|------|--------|
| 5.1 | `ingestion/lambda_function.py` | Add source-cloud logging |
| 5.2 | `writer/lambda_function.py` | Add source-cloud logging |

### Phase 6: Add Comprehensive Unit Tests

| Step | File | Action |
|------|------|--------|
| 6.1 | `test_persister.py` | Add 18 new multi-cloud test cases |
| 6.2 | `test_ingestion.py` | Create new file with 12 test cases |
| 6.3 | `test_writer.py` | Create new file with 12 test cases |
| 6.4 | `test_connector.py` | Create new file with 14 test cases |

### Phase 7: Create New Documentation

| Step | File | Action |
|------|------|--------|
| 7.1 | `docs/docs-multi-cloud.html` | Create comprehensive multi-cloud documentation |
| 7.2 | `docs/docs-nav.html` | Add navigation link |

### Phase 8: Update Existing Documentation

| Step | File | Action |
|------|------|--------|
| 8.1 | `docs/docs-aws-deployment.html` | Update Persister status badge from "Todo" to "Implemented" |
| 8.2 | `docs/docs-aws-deployment.html` | Update Ingestion/Writer status badges |
| 8.3 | `docs/docs-aws-deployment.html` | Add reference to new multi-cloud documentation page |
| 8.4 | `docs/docs-azure-deployment.html` | Add cross-reference to multi-cloud architecture |
| 8.5 | `docs/docs-gcp-deployment.html` | Add cross-reference to multi-cloud architecture |
| 8.6 | `docs/docs-architecture.html` | Add section on multi-cloud data flow |

---

## 7. Verification Checklist

### Automated Tests

**Run existing persister tests:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_persister.py -v
```

**Run new ingestion tests:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_ingestion.py -v
```

**Run new writer tests:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_writer.py -v
```

**Run new connector tests:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_connector.py -v
```

**Run ALL tests:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v
```

### Test Summary

| Test File | New Tests | Edge Cases Covered |
|-----------|-----------|-------------------|
| `test_persister.py` | 18 | Dual validation, empty/whitespace URLs, provider match, retry, token, envelope, timestamp, trace_id |
| `test_ingestion.py` | 12 | Token (missing/empty/invalid/case-insensitive), body validation, source_cloud extraction, env config |
| `test_writer.py` | 12 | Token, payload modes, missing body, missing time field, DynamoDB errors, env config |
| `test_connector.py` | 14 | Retry (500/503), no-retry (400/401), empty URL/token, envelope format, timestamp, trace_id |
| **Total** | **56** | Comprehensive coverage of all multi-cloud edge cases |

---

## 8. Design Decisions

### Decision 1: Standardize on X-Inter-Cloud-Token

**Research Summary:**
- AWS Lambda: Supports custom headers via `event["headers"]`
- Azure Functions: Supports custom headers via `req.headers`
- GCP Cloud Functions: Supports custom headers via `request.headers`

**Chosen:** Shared secret token via `X-Inter-Cloud-Token` header.

**Rationale:**
- Works identically on all clouds (validated via research)
- No complex OIDC/IAM federation required
- Token configured at deployment time via environment variable

### Decision 2: Function URLs for Ingestion/Writer

**Chosen:** Use AWS Lambda Function URLs (not API Gateway).

**Rationale:**
- Simpler deployment (no API Gateway setup)
- Built-in HTTPS endpoint
- Lower cost for internal traffic
- Faster to provision

### Decision 3: Reuse Connector Retry Logic

**Rationale:**
- Connector already has well-tested exponential backoff
- Same pattern applied to Persister → Writer calls
- Consistency across all cross-cloud communication

---

## 9. Future Considerations

> **Note:** The following items are out of scope for this implementation but documented for future work:

1. **Azure/GCP Equivalent Functions:** Create equivalent gluecode functions for Azure Functions and GCP Cloud Functions.
2. **Dead Letter Queue (DLQ):** Add DLQ support for failed cross-cloud calls.
3. **Metrics/Observability:** Add CloudWatch metrics for cross-cloud call latency and error rates.
4. **Multi-Cloud Mover Functions:** Analysis of cross-cloud storage lifecycle management (hot-to-cold, cold-to-archive) is deferred to a separate future plan.

---

## 10. Deployer Code Analysis

### Findings

| Function | Deployer Code | Status |
|----------|--------------|--------|
| **Connector** | `create_processor_lambda_function()` | ✅ Already handles multi-cloud |
| **Persister** | `create_persister_lambda_function()` | ⚠️ **Needs update** |
| **Ingestion** | Not implemented | ❌ **Needs new code** |
| **Writer** | Not implemented | ❌ **Needs new code** |

---

## 11. Updated Implementation Scope

### In Scope (This Task)
1. ✅ Add multi-cloud logic to **Persister** Lambda function
2. ✅ Update **Persister deployer code** to set `REMOTE_WRITER_URL` 
3. ✅ Add **Ingestion deployer code** (IAM role, Lambda, Function URL)
4. ✅ Add **Writer deployer code** (IAM role, Lambda, Function URL)
5. ✅ Add source-cloud logging to Ingestion/Writer functions
6. ✅ Add **31 comprehensive unit tests** across 4 test files
7. ✅ Create **Multi-Cloud documentation page** with flowcharts
8. ✅ Update **existing documentation** (AWS/Azure/GCP roadmaps, architecture)

### Out of Scope (Future Work)
1. ❌ Cross-cloud mover functions (separate plan)
2. ❌ Azure/GCP gluecode function implementations

