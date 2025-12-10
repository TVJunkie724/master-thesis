# L3 Data Mover Multi-Cloud Adaptations

## 1. Executive Summary

### The Problem
The current L3 data mover functions (`hot-to-cold-mover` and `cold-to-archive-mover`) only work within AWS. When L3 storage tiers span multiple clouds (e.g., L3 Hot on AWS, L3 Cold on Azure, L3 Archive on GCP):

1. **Movers have no multi-cloud awareness**: They write directly to local S3 buckets with no HTTP POST logic
2. **Deployers inject no multi-cloud env vars**: `create_hot_cold_mover_lambda_function` and `create_cold_archive_mover_lambda_function` don't check provider configs
3. **No Cold Writer or Archive Writer functions exist**: Unlike the existing Writer for L3 Hot
4. **No chunking for large payloads**: Cloud function payload limits (AWS=6MB, Azure=100MB, GCP=10-32MB) require chunking
5. **No naming functions for new Writers**: `naming.py` lacks `cold_writer_*` and `archive_writer_*`

### The Solution
1. Add **Cold Writer** and **Archive Writer** Lambda functions (HTTP endpoints)
2. Modify **Hot-to-Cold Mover** with `_is_multi_cloud_cold()` dual validation and 5MB chunking
3. Modify **Cold-to-Archive Mover** with `_is_multi_cloud_archive()` dual validation  
4. Update **deployers** to inject multi-cloud env vars and conditionally deploy Writers
5. Add **naming functions** for Cold Writer and Archive Writer
6. **Optimize chunk size from 1MB to 5MB** for **80% cost reduction** on S3 PUT operations
7. Add **comprehensive tests** covering all edge cases

### Impact
- Enables hybrid L3 deployments: Hot/Cold/Archive can each be on different clouds
- **80% reduction in S3 PUT request costs** (5MB chunks vs 1MB)
- **80% fewer HTTP calls** in cross-cloud transfers
- Consistent fail-fast behavior for incomplete configurations


---

## 2. Current State

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CURRENT L3 MOVER FLOW (AWS Only)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  L3 Hot (DynamoDB)          L3 Cold (S3)          L3 Archive (S3)          │
│  ┌──────────────┐         ┌──────────────┐       ┌──────────────┐          │
│  │   DynamoDB   │         │  S3 Bucket   │       │  S3 Bucket   │          │
│  │  (Hot Data)  │         │ STANDARD_IA  │       │ DEEP_ARCHIVE │          │
│  └──────┬───────┘         └──────┬───────┘       └──────────────┘          │
│         │                        │                      ▲                   │
│         │ EventBridge            │ EventBridge          │                   │
│         │ (Scheduled)            │ (Scheduled)          │                   │
│         ▼                        ▼                      │                   │
│  ┌──────────────┐         ┌──────────────┐             │                   │
│  │ Hot-to-Cold  │ ──S3──▶ │ Cold-to-Arch │ ──S3 copy──┘                   │
│  │    Mover ⚠️  │         │   Mover ⚠️   │                                 │
│  └──────────────┘         └──────────────┘                                 │
│         │                        │                                         │
│         ├── Queries DynamoDB     ├── Lists S3 objects                      │
│         ├── Chunks to S3         ├── Copies to Archive bucket              │
│         └── Deletes from DDB     └── Deletes from Cold bucket              │
│                                                                             │
│  ⚠️ = NO MULTI-CLOUD LOGIC - Always writes to local storage               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Current Files:
| File | Status | Multi-Cloud Logic |
|------|--------|-------------------|
| `hot-to-cold-mover/lambda_function.py` | ⚠️ Incomplete | None - writes directly to S3 |
| `cold-to-archive-mover/lambda_function.py` | ⚠️ Incomplete | None - copies within S3 |
| `layer_3_storage.py` | ⚠️ Incomplete | No env var injection for movers |
| `l3_adapter.py` | ⚠️ Incomplete | No Cold/Archive Writer deployment |
| `naming.py` | ⚠️ Incomplete | Missing Cold/Archive Writer names |

---

## 3. Target State

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                           MULTI-CLOUD L3 MOVER FLOW                                         │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                             │
│  AWS L3 Hot (DynamoDB)         Azure L3 Cold              GCP L3 Archive                   │
│  ┌──────────────┐              ┌──────────────┐          ┌──────────────┐                  │
│  │   DynamoDB   │              │ Blob Storage │          │Cloud Storage │                  │
│  │  (Hot Data)  │              │   (Cool)     │          │ (Coldline)   │                  │
│  └──────┬───────┘              └──────┬───────┘          └──────────────┘                  │
│         │                             ▲                         ▲                          │
│         │ EventBridge                 │                         │                          │
│         │ (Scheduled)       HTTP POST (chunked)       HTTP POST (chunked)                  │
│         ▼                             │                         │                          │
│  ┌───────────────────┐         ┌──────────────┐          ┌──────────────┐                  │
│  │ Hot-to-Cold Mover │──HTTP──▶│ Cold Writer  │          │Archive Writer│                  │
│  │ (AWS Lambda)      │  POST   │ (Azure Func) │          │(GCP CloudFn) │                  │
│  │                   │ ≤5MB    │ - Auth token │          │ - Auth token │                  │
│  │ - Query DynamoDB  │ chunks  │ - Write Blob │          │ - Write GCS  │                  │
│  │ - Chunk ≤5MB      │         └──────────────┘          └──────────────┘                  │
│  │ - POST to Writer  │                │                         ▲                          │
│  │ - Delete from DDB │                │                         │                          │
│  └───────────────────┘                ▼                         │                          │
│                                ┌───────────────────┐            │                          │
│                                │ Cold-to-Arch Mover│──HTTP POST─┘                          │
│                                │ (Azure Function)  │   ≤5MB chunks                         │
│                                │ - List blobs      │                                       │
│                                │ - Read/chunk data │                                       │
│                                │ - POST to Archive │                                       │
│                                │ - Delete blob     │                                       │
│                                └───────────────────┘                                       │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3B. Design Decision: Batched File Storage (Cost-Optimized)

> **User Decision:** Keep the batched/chunked design for cost efficiency.

### Current Storage Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BATCHED FILE STORAGE DESIGN                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  HOT (DynamoDB)              COLD (S3)                 ARCHIVE (S3)         │
│  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐       │
│  │ Individual   │          │ Batch Files  │          │ Batch Files  │       │
│  │ Items (KB)   │          │ (~1MB each)  │          │ (~1MB each)  │       │
│  │              │          │              │          │              │       │
│  │ {deviceId,   │   ───▶   │ [ item1,     │   ───▶   │ [ item1,     │       │
│  │  timestamp,  │  batch   │   item2,     │   copy   │   item2,     │       │
│  │  data... }   │          │   item3,     │          │   item3,     │       │
│  │              │          │   ...itemN ] │          │   ...itemN ] │       │
│  └──────────────┘          └──────────────┘          └──────────────┘       │
│                                                                             │
│  Key Format:                                                                │
│  S3: {device_id}/{start_time}-{end_time}/chunk-00001.json                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Batching Is Cost-Effective

| Aspect | Atomic Items | Batched Files (Current) |
|--------|--------------|-------------------------|
| **S3 Objects** | 1 per event | 1 per batch (~100s of events) |
| **S3 PUT Costs** | $0.005/1K requests | **80-99% cheaper** |
| **S3 GET Costs** | Higher (more objects) | **Much cheaper** |
| **S3 LIST Costs** | Higher (more objects) | **Much cheaper** |
| **Searchability** | Direct by key | Parse batch file |

**Trade-off:** Searching for a specific item requires downloading and parsing the batch file. This is acceptable for archive data that is rarely accessed.

### 5MB Chunk Optimization (Cost Reduction)

> **Optimization Approved:** Modify Hot-to-Cold mover to create 5MB chunks instead of 1MB.
> 
> **Scope:** This optimization applies to **ALL scenarios** (single-cloud AND multi-cloud) for consistent cost savings.

#### Current Behavior (1MB Chunks)
```python
# Current: Each DynamoDB page (~1MB) = 1 S3 object
for page in paginated_query:
    flush_chunk_to_s3(page)  # Creates ~1MB files
```

#### Optimized Behavior (5MB Chunks)
```python
MAX_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

buffer = []
buffer_size = 0

for page in paginated_query:
    for item in page:
        item_size = len(json.dumps(item, default=str).encode('utf-8'))
        
        if buffer_size + item_size > MAX_CHUNK_SIZE and buffer:
            flush_chunk_to_s3(buffer)
            buffer = []
            buffer_size = 0
        
        buffer.append(item)
        buffer_size += item_size

# Flush remaining items
if buffer:
    flush_chunk_to_s3(buffer)
```

#### Cost Comparison: 1MB vs 5MB Chunks

**Scenario:** Moving 100MB of IoT data through Hot → Cold → Archive

| Metric | 1MB Chunks | 5MB Chunks | Savings |
|--------|------------|------------|---------|
| **# Objects** | 100 | 20 | 80% fewer |
| **PUT Costs (Cold @ $0.01/1K)** | $0.001 | $0.0002 | **80%** |
| **PUT Costs (Archive @ $0.05/1K)** | $0.005 | $0.001 | **80%** |
| **HTTP Calls (cross-cloud)** | 100 | 20 | 80% fewer |
| **Lambda Iterations** | 100 | 20 | 80% faster |

#### S3 Request Pricing Reference

| Storage Class | PUT per 1K | GET per 1K |
|---------------|------------|------------|
| S3 Standard | $0.005 | $0.0004 |
| S3 Standard-IA (Cold) | $0.01 | $0.001 |
| S3 Glacier Deep Archive | $0.05 | $0.0004 |

### Implications for Multi-Cloud Transfer

With 5MB chunks:
- **No additional chunking needed** for cross-cloud transfers
- 5MB fits within all cloud payload limits (AWS 6MB, Azure 100MB, GCP 32MB)
- Hot-to-Cold Mover: POST entire 5MB batch to Cold Writer
- Cold-to-Archive Mover: POST entire 5MB batch file to Archive Writer

### Memory Guard (Safety Check)

```python
MAX_SAFE_BATCH_SIZE = 5 * 1024 * 1024  # 5MB (within all cloud limits)

for obj in objects_to_transfer:
    if obj['Size'] > MAX_SAFE_BATCH_SIZE:
        print(f"WARNING: Skipping {obj['Key']} - size {obj['Size']} exceeds 5MB limit")
        continue
    # Standard transfer...
```

---

## 4. Deep Investigation: Gap Analysis

### A. Lambda Function Code Gaps

| Component | File | Gap | Status |
|-----------|------|-----|--------|
| **Hot-to-Cold Mover** | `hot-to-cold-mover/lambda_function.py` | No 5MB chunk buffering (currently uses 1MB DynamoDB pages) | ❌ Missing |
| **Hot-to-Cold Mover** | `hot-to-cold-mover/lambda_function.py` | No `REMOTE_COLD_WRITER_URL` check | ❌ Missing |
| **Hot-to-Cold Mover** | `hot-to-cold-mover/lambda_function.py` | No `_is_multi_cloud_cold()` dual validation | ❌ Missing |
| **Hot-to-Cold Mover** | `hot-to-cold-mover/lambda_function.py` | No `_post_to_remote_cold_writer()` for cross-cloud | ❌ Missing |
| **Hot-to-Cold Mover** | `hot-to-cold-mover/lambda_function.py` | No `ConfigurationError` for missing config | ❌ Missing |
| **Cold-to-Archive Mover** | `cold-to-archive-mover/lambda_function.py` | No `REMOTE_ARCHIVE_WRITER_URL` check | ❌ Missing |
| **Cold-to-Archive Mover** | `cold-to-archive-mover/lambda_function.py` | No `_is_multi_cloud_archive()` dual validation | ❌ Missing |
| **Cold-to-Archive Mover** | `cold-to-archive-mover/lambda_function.py` | No `_post_to_remote_archive_writer()` for cross-cloud | ❌ Missing |
| **Cold-to-Archive Mover** | `cold-to-archive-mover/lambda_function.py` | No object size guard for memory | ❌ Missing |
| **Cold Writer** | ❌ Does not exist | Need new Lambda function | ❌ Missing |
| **Archive Writer** | ❌ Does not exist | Need new Lambda function | ❌ Missing |

### B. Deployer Code Gaps

| Component | File | Gap | Status |
|-----------|------|-----|--------|
| **Hot-Cold Mover Deployer** | `layer_3_storage.py:350-358` | No multi-cloud env vars: `REMOTE_COLD_WRITER_URL`, `INTER_CLOUD_TOKEN` | ❌ Missing |
| **Cold-Archive Mover Deployer** | `layer_3_storage.py:507-512` | No multi-cloud env vars: `REMOTE_ARCHIVE_WRITER_URL`, `INTER_CLOUD_TOKEN` | ❌ Missing |
| **Cold Writer Deployer** | ❌ Does not exist | Need `create_cold_writer_*` functions | ❌ Missing |
| **Archive Writer Deployer** | ❌ Does not exist | Need `create_archive_writer_*` functions | ❌ Missing |
| **L3 Cold Adapter** | `l3_adapter.py:98-117` | No conditional Cold Writer deployment | ❌ Missing |
| **L3 Archive Adapter** | `l3_adapter.py:140-159` | No conditional Archive Writer deployment | ❌ Missing |

### C. Naming Function Gaps

| Function | File | Status |
|----------|------|--------|
| `cold_writer_lambda_function()` | `naming.py` | ❌ Missing |
| `cold_writer_iam_role()` | `naming.py` | ❌ Missing |
| `archive_writer_lambda_function()` | `naming.py` | ❌ Missing |
| `archive_writer_iam_role()` | `naming.py` | ❌ Missing |

### D. Provider Config Key Usage

> **Confirmed:** Template `config_providers.json` already contains:
> - `layer_3_cold_provider`
> - `layer_3_archive_provider`

| Key | Usage in Codebase | Status |
|-----|-------------------|--------|
| `layer_3_hot_provider` | ✅ Used in L2/L3 adapters, Persister | ✅ Complete |
| `layer_3_cold_provider` | ❌ Not used anywhere | ❌ Need to add |
| `layer_3_archive_provider` | ❌ Not used anywhere | ❌ Need to add |

### E. Pre-Existing Bug: Cold-to-Archive Mover Environment Variables

> [!CAUTION]
> **PRE-EXISTING BUG DISCOVERED** during deep investigation.

| Location | Expected By Lambda | Injected By Deployer | Status |
|----------|-------------------|----------------------|--------|
| `cold-to-archive-mover/lambda_function.py:8-9` | `SOURCE_S3_BUCKET_NAME` | `COLD_S3_BUCKET_NAME` | ❌ **MISMATCH** |
| `cold-to-archive-mover/lambda_function.py:8-9` | `TARGET_S3_BUCKET_NAME` | `ARCHIVE_S3_BUCKET_NAME` | ❌ **MISMATCH** |

**Impact:** The cold-to-archive-mover Lambda will fail at runtime because it reads `SOURCE_S3_BUCKET_NAME` which is never set.

**Fix Required:** Either:
- **Option A**: Update Lambda code to use `COLD_S3_BUCKET_NAME` and `ARCHIVE_S3_BUCKET_NAME` ✅ Recommended (aligns with naming conventions)
- **Option B**: Update deployer to inject `SOURCE_S3_BUCKET_NAME` and `TARGET_S3_BUCKET_NAME`

### F. Config Inter-Cloud File Creation (MISSING)

> [!CAUTION]
> **CRITICAL GAP:** `config_inter_cloud.json` is **never created** during deployment.

#### Investigation Results

| File | Usage | Creates File? |
|------|-------|---------------|
| `config_loader.py:112` | `_load_json_file(..., required=False)` | ❌ Loads only |
| `l3_adapter.py:56` | `# TODO: Store this URL in config_inter_cloud.json` | ❌ TODO only |
| `layer_2_compute.py:150-161` | Reads `inter_cloud.get("connections")` | ❌ Reads only |
| All other files | Error messages referencing the file | ❌ N/A |

#### Current Workflow (Broken for Multi-Cloud)

```
1. User provides config_providers.json with different providers per layer
2. Deploy L3 Hot → Writer Lambda created → URL generated
3. ❌ URL is LOGGED but NOT SAVED to config_inter_cloud.json
4. Deploy L2 → Persister reads config_inter_cloud.json → ❌ FILE DOESN'T EXIST
5. ❌ Persister has no URL to call Writer
```

#### Options to Fix

**Option A: Manual Configuration (Current State - Document Only)**
- User must manually create `config_inter_cloud.json` with Writer URLs
- Requires deploying L3 first, copying URL, creating file, then deploying L2
- **Pro**: Simple implementation
- **Con**: Error-prone manual process

**Option B: Automatic URL Persistence (Recommended)**
- After creating Writer Function URL, save to `config_inter_cloud.json`
- Need to implement `save_inter_cloud_connection()` helper
- **Pro**: Fully automated multi-cloud deployment
- **Con**: Requires file write logic and re-loading config

**Option C: Return URL and Store in Memory**
- Store connection URLs in `DeploymentContext` during deployment
- Pass to subsequent layer deployments
- **Pro**: No file I/O needed
- **Con**: URLs lost if deployment interrupted

#### Recommended Implementation (Option B) ✅ SELECTED

> [!NOTE]
> Option B selected per user decision. Implement automatic URL persistence.

```python
# New function in config_loader.py
def save_inter_cloud_connection(
    project_path: Path, 
    conn_id: str, 
    url: str, 
    token: str
) -> None:
    """Save inter-cloud connection to config_inter_cloud.json."""
    inter_cloud_path = project_path / CONFIG_INTER_CLOUD_FILE
    
    # Load existing or create new
    if inter_cloud_path.exists():
        with open(inter_cloud_path, 'r') as f:
            inter_cloud = json.load(f)
    else:
        inter_cloud = {"connections": {}}
    
    # Add/update connection
    inter_cloud["connections"][conn_id] = {
        "url": url,
        "token": token
    }
    
    # Save back
    with open(inter_cloud_path, 'w') as f:
        json.dump(inter_cloud, f, indent=2)
    
    logger.info(f"Saved inter-cloud connection '{conn_id}' to config_inter_cloud.json")
```

#### All Callers Needing `save_inter_cloud_connection()`

| Location | Function URL Created | Connection ID Format | TODO Status |
|----------|---------------------|---------------------|-------------|
| `l2_adapter.py:98-100` | Ingestion Lambda URL | `{l1}_l1_to_{l2}_l2` | ❌ TODO only |
| `l3_adapter.py:54-56` | Writer Lambda URL | `{l2}_l2_to_{l3}_l3hot` | ❌ TODO only |
| `l3_adapter.py` (NEW) | Cold Writer URL | `{l3hot}_l3hot_to_{l3cold}_l3cold` | ❌ Need to add |
| `l3_adapter.py` (NEW) | Archive Writer URL | `{l3cold}_l3cold_to_{l3archive}_l3archive` | ❌ Need to add |

**Note:** The existing L2 adapter TODO is from the previous implementation plan and should be addressed as part of this work.

### G. Config Template Gaps

| Template | Gap | Status |
|----------|-----|--------|
| `config_inter_cloud.json` | Missing L3 Hot → L3 Cold connection example | ❌ Need to add |
| `config_inter_cloud.json` | Missing L3 Cold → L3 Archive connection example | ❌ Need to add |

**Required additions to template:**
```json
{
    "connections": {
        "aws_l1_to_azure_l2": { ... },
        "azure_l2_to_aws_l3": { ... },
        "aws_l3hot_to_azure_l3cold": {
            "provider": "azure",
            "function": "cold_writer",
            "token": "generated-secure-token",
            "url": "https://func-cold-writer.azurewebsites.net/api/cold-writer"
        },
        "azure_l3cold_to_gcp_l3archive": {
            "provider": "gcp",
            "function": "archive_writer",
            "token": "generated-secure-token",
            "url": "https://region-project.cloudfunctions.net/archive-writer"
        }
    }
}
```

### G. AWS Function URL Configuration (Verified)

> [!NOTE]
> Existing Writer implementation in `layer_3_storage.py:195-216` already correct.

| Requirement | Current Status | Source |
|-------------|----------------|--------|
| `AuthType: NONE` | ✅ Implemented (line 201) | AWS Lambda Function URL docs |
| Public access policy | ✅ Implemented (lines 207-213) | `FunctionURLPublicAccess` permission |
| CORS handling | ⚠️ Not configured | Lambda handles CORS automatically for `NONE` auth |

Cold Writer and Archive Writer will follow this same pattern.

### H. Azure/GCP Multi-Cloud Planning Status

| Provider | L3 Storage Implementation | Multi-Cloud Support | Status |
|----------|--------------------------|---------------------|--------|
| AWS | ✅ Implemented | ❌ Gaps identified in this plan | ❌ To implement |
| Azure | ❌ Not implemented | N/A | ⏳ Future work |
| GCP | ❌ Not implemented | N/A | ⏳ Future work |

This plan focuses on **AWS implementation only**. Azure and GCP L3 implementations will be addressed in separate plans.

### I. Inter-Cloud Connection ID Format

Per the existing pattern in `layer_2_compute.py`:
```python
conn_id = f"{l1_provider}_l1_to_{l2_provider}_l2"  # e.g., "aws_l1_to_azure_l2"
```

**New patterns needed for L3:**
```python
# Hot → Cold
conn_id = f"{l3_hot}_l3hot_to_{l3_cold}_l3cold"  # e.g., "aws_l3hot_to_azure_l3cold"

# Cold → Archive  
conn_id = f"{l3_cold}_l3cold_to_{l3_archive}_l3archive"  # e.g., "azure_l3cold_to_gcp_l3archive"
```
### K. Silent Error Patterns Discovered (⚠️ Critical)

> [!WARNING]
> These patterns could cause hard-to-debug runtime failures.

#### 1. Environment Variable Fallbacks Without Validation

| Lambda | Line | Pattern | Issue |
|--------|------|---------|-------|
| `hot-to-cold-mover` | 8-10 | `os.environ.get(..., None)` | Uses `None` without checking before use |
| `cold-to-archive-mover` | 7-9 | `os.environ.get(..., None)` | Uses `None` without checking before use |
| `hot-reader` | 7-8 | `os.environ.get(..., None)` | Uses `None` without checking before use |

**Fix Required:** Add startup validation:
```python
# Add at start of lambda_handler
if not DYNAMODB_TABLE_NAME or not S3_BUCKET_NAME:
    raise RuntimeError("Missing required environment variables")
```

#### 2. `json.loads(None)` and Silent Fallback Patterns - FULL AUDIT

> [!CAUTION]
> Comprehensive audit of ALL Lambda functions for env var validation issues.

**Pattern A: `json.loads(..., None)` - CRASH RISK** (7 Lambdas)

| Lambda | Line | Code | Impact |
|--------|------|------|--------|
| `hot-to-cold-mover` | 8 | `json.loads(os.environ.get("DIGITAL_TWIN_INFO", None))` | **TypeError crash** |
| `cold-to-archive-mover` | 7 | Same | **TypeError crash** |
| `hot-reader` | 7 | Same | **TypeError crash** |
| `hot-reader-last-entry` | 7 | Same | **TypeError crash** |
| `event-checker` | 6 | Same | **TypeError crash** |
| `dispatcher` | 6 | Same | **TypeError crash** |
| `default-processor` | 6 | Same | **TypeError crash** |

**Pattern B: `json.loads(..., '{}')` - SILENT FAILURE** (2 Lambdas)

| Lambda | Line | Code | Impact |
|--------|------|------|--------|
| `persister` | 11 | `json.loads(os.environ.get("DIGITAL_TWIN_INFO", "{}"))` | Empty dict, fails later |
| `ingestion` | 7 | Same | Empty dict, fails later |

**Pattern C: `os.environ.get(..., None)` - NO VALIDATION** (17 occurrences)

| Lambda | Env Vars with None fallback |
|--------|----------------------------|
| `hot-to-cold-mover` | `DYNAMODB_TABLE_NAME`, `S3_BUCKET_NAME` |
| `cold-to-archive-mover` | `SOURCE_S3_BUCKET_NAME`, `TARGET_S3_BUCKET_NAME` |
| `hot-reader` | `DYNAMODB_TABLE_NAME` |
| `hot-reader-last-entry` | `DYNAMODB_TABLE_NAME` |
| `event-checker` | `TWINMAKER_WORKSPACE_NAME`, `LAMBDA_CHAIN_STEP_FUNCTION_ARN`, `EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN` |
| `dispatcher` | (none critical) |
| `default-processor` | `PERSISTER_LAMBDA_NAME` |
| `persister` | `DYNAMODB_TABLE_NAME`, `EVENT_CHECKER_LAMBDA_NAME` |
| `writer` | `DYNAMODB_TABLE_NAME` (no fallback at all!) |

**Pattern D: `os.environ.get(...)` - NO FALLBACK** (Worst)

| Lambda | Line | Code | Impact |
|--------|------|------|--------|
| `writer` | 6 | `DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")` | `None`, then `dynamodb.Table(None)` fails cryptically |
| `writer` | 11 | `expected_token = os.environ.get("INTER_CLOUD_TOKEN")` | `None` allows all requests if token check compares `incoming != None` |
| `connector` | 11-12 | `remote_url` and `token` | Checked at line 14, but only inside function |

**Fix Required:** Standardize ALL Lambdas to validate env vars at startup:
```python
def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable '{name}' is not set")
    return value

DIGITAL_TWIN_INFO = json.loads(_require_env("DIGITAL_TWIN_INFO"))
DYNAMODB_TABLE_NAME = _require_env("DYNAMODB_TABLE_NAME")
```

#### 3. No Retry Logic for Cross-Cloud HTTP POST

The new multi-cloud movers will POST to remote Writers. Currently:
- No retry on 5xx server errors
- No exponential backoff
- No timeout handling

**Fix Required:** Implement retry with exponential backoff (max 3 retries, 5xx only).

#### 4. No Idempotency Key for POST Requests

POST requests are not idempotent. If a chunk is POSTed twice due to retry:
- Could create duplicate data in Cold/Archive storage

**Current Behavior on Receiver (Writer Lambda):**
```python
# writer/lambda_function.py line 42
table.put_item(Item=data_to_write)  # ← Just writes, NO duplicate check!
```
The existing Writer Lambda writes directly to DynamoDB without any idempotency check.

**Fix Required - BOTH SIDES:**

**Sender Side (Movers):**
- Include unique `chunk_id` (e.g., `{device_id}/{timestamp_range}/chunk-{index}`)
- Include `idempotency_key` header in HTTP request

**Receiver Side (All Writers):**

**Hot Writer (writes to DynamoDB - ALREADY IDEMPOTENT):**
```python
# writer/lambda_function.py line 42
table.put_item(Item=data_to_write)
```
DynamoDB `put_item` is naturally idempotent:
- Same primary key (iotDeviceId + timestamp id) = overwrites existing item
- ✅ No duplicate data created, just re-writes same item
- **Conclusion: Hot Writer needs NO changes for idempotency**

**Cold Writer and Archive Writer (write to S3 - ALSO IDEMPOTENT):**

```python
# Cold Writer - use S3 key for idempotency
key = f"{device_id}/{timestamp_range}/chunk-{chunk_index}.json"

# Check if already exists (optional - S3 PutObject is naturally overwrite)
# For archive, existence check is expensive, so accept duplicate writes
# OR use DynamoDB to track written chunks

s3_client.put_object(
    Bucket=COLD_S3_BUCKET_NAME,
    Key=key,  # Same key = same chunk = no duplicate
    Body=data,
    StorageClass="STANDARD_IA"
)
```

> [!NOTE]
> S3 `put_object` is naturally idempotent for same key - it overwrites. 
> For Cold/Archive, using the same key format ensures no duplicates.

### L. Additional Edge Case Tests (From Silent Error Analysis)

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_mover_missing_env_var_raises` | `DYNAMODB_TABLE_NAME=None` | `RuntimeError` at startup |
| `test_mover_missing_digital_twin_info_raises` | `DIGITAL_TWIN_INFO` not set | `RuntimeError` at startup |
| `test_post_remote_retry_on_5xx` | Remote returns 503 | Retry up to 3 times |
| `test_post_remote_no_retry_on_4xx` | Remote returns 400 | Fail immediately |
| `test_post_remote_timeout_handling` | Remote hangs | Timeout after 30s |
| `test_chunk_id_prevents_duplicate` | Same chunk_id POSTed twice | S3/DynamoDB overwrites, no duplicate |

### M. Additional Edge Case Tests (From ENV VAR Audit)

> [!NOTE]
> Tests based on the comprehensive env var audit in Section K.2.

#### Pattern A Tests: `json.loads(None)` Crash Prevention

| Test Name | Lambda | Expected Result |
|-----------|--------|-----------------|
| `test_hot_cold_mover_missing_digital_twin_crashes` | hot-to-cold-mover | RuntimeError, not TypeError |
| `test_cold_archive_mover_missing_digital_twin_crashes` | cold-to-archive-mover | RuntimeError, not TypeError |
| `test_dispatcher_missing_digital_twin_crashes` | dispatcher | RuntimeError, not TypeError |
| `test_event_checker_missing_digital_twin_crashes` | event-checker | RuntimeError, not TypeError |
| `test_hot_reader_missing_digital_twin_crashes` | hot-reader | RuntimeError, not TypeError |

#### Pattern B Tests: Silent Empty Dict Fallback

| Test Name | Lambda | Expected Result |
|-----------|--------|-----------------|
| `test_persister_empty_digital_twin_fails` | persister | ConfigurationError, not silent failure |
| `test_ingestion_empty_digital_twin_fails` | ingestion | ConfigurationError, not silent failure |

#### Pattern C Tests: None Fallback Without Validation

| Test Name | Lambda | Expected Result |
|-----------|--------|-----------------|
| `test_hot_cold_mover_missing_dynamodb_table_raises` | hot-to-cold-mover | RuntimeError at startup |
| `test_hot_cold_mover_missing_s3_bucket_raises` | hot-to-cold-mover | RuntimeError at startup |
| `test_cold_archive_mover_missing_source_bucket_raises` | cold-to-archive-mover | RuntimeError at startup |
| `test_cold_archive_mover_missing_target_bucket_raises` | cold-to-archive-mover | RuntimeError at startup |

#### Pattern D Tests: No Fallback At All

| Test Name | Lambda | Expected Result |
|-----------|--------|-----------------|
| `test_writer_missing_dynamodb_table_raises` | writer | RuntimeError at startup |
| `test_writer_missing_token_rejects_all` | writer | 403 for all requests (not bypass) |

#### Idempotency Tests

| Test Name | Writer | Expected Result |
|-----------|--------|-----------------|
| `test_hot_writer_duplicate_put_overwrites` | writer | DynamoDB put_item overwrites, 200 |
| `test_cold_writer_duplicate_key_overwrites` | cold-writer | S3 put_object overwrites, 200 |
| `test_archive_writer_duplicate_key_overwrites` | archive-writer | S3 put_object overwrites, 200 |

#### Retry and Error Handling Tests

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_retry_exponential_backoff_timing` | 3 retries | Delays: 1s, 2s, 4s (exponential) |
| `test_retry_respects_max_attempts` | Always fails | Stops after 3 attempts |
| `test_retry_includes_jitter` | Multiple retries | Delays have random jitter component |
| `test_http_timeout_30_seconds` | Slow remote | Timeout after 30s, not hang |

---

### F. Payload Limits (From Cloud Documentation)

| Cloud | Service | Max Payload | Source |
|-------|---------|-------------|--------|
| AWS | Lambda (sync) | 6 MB | [AWS Lambda Quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html) |
| Azure | Functions HTTP | 100 MB | [Azure Functions Limits](https://learn.microsoft.com/en-us/azure/azure-functions/functions-scale) |
| GCP | Cloud Functions (Gen2) | 32 MB | [GCP Limits](https://cloud.google.com/functions/quotas) |

**Decision:** Use **5 MB chunk size** (conservative for AWS limit).

---

### G. IAM Roles and Account Permissions Gap Analysis

> **Investigation:** Reviewed `src/api/credentials_checker.py` and existing IAM role patterns in `layer_3_storage.py`.

#### Account-Level Permissions (credentials_checker.py)

| Permission | Layer | Current Status | Required Change |
|------------|-------|----------------|-----------------|
| `lambda:CreateFunctionUrlConfig` | layer_3 | ✅ Already exists (line 114) | None |
| `lambda:DeleteFunctionUrlConfig` | layer_3 | ✅ Already exists (line 115) | None |
| `lambda:GetFunctionUrlConfig` | layer_3 | ✅ Already exists (line 116) | None |
| `s3:PutObject` | layer_3 | ✅ Covered by `s3:*` in L1 execution | None |
| `iam:PutRolePolicy` | layer_3 | ⚠️ Only in layer_2 | ❌ Need to add |

**Required Change to `credentials_checker.py`:**
```python
# In REQUIRED_AWS_PERMISSIONS["layer_3"]:
"iam": [
    "iam:PutRolePolicy",  # NEW: For Cold/Archive Writer inline S3 policies
],
```

#### New IAM Role Requirements

| Role | Purpose | Required Policies |
|------|---------|-------------------|
| **Cold Writer IAM Role** | HTTP endpoint that writes to Cold S3 | Lambda basic execution + S3 PutObject |
| **Archive Writer IAM Role** | HTTP endpoint that writes to Archive S3 | Lambda basic execution + S3 PutObject |

#### Cold Writer IAM Role Policy Document

```python
# Create IAM role for Cold Writer
def create_cold_writer_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Cold Writer Lambda (multi-cloud only).
    
    Cold Writer needs:
    - S3 PutObject to cold bucket (STANDARD_IA storage class)
    - Basic execution role (CloudWatch Logs)
    """
    role_name = provider.naming.cold_writer_iam_role()
    iam_client = provider.clients["iam"]

    # Create role with Lambda execution trust
    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )

    # Attach basic execution policy
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION
    )

    # Add inline policy for S3 Cold bucket write access
    bucket_name = provider.naming.cold_s3_bucket()
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="S3ColdWriteAccess",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject"
                ],
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }]
        })
    )
```

#### Archive Writer IAM Role Policy Document

```python
def create_archive_writer_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Archive Writer Lambda (multi-cloud only).
    
    Archive Writer needs:
    - S3 PutObject to archive bucket (DEEP_ARCHIVE storage class)
    - Basic execution role (CloudWatch Logs)
    """
    role_name = provider.naming.archive_writer_iam_role()
    iam_client = provider.clients["iam"]

    # Create role with Lambda execution trust
    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        })
    )

    # Attach basic execution policy
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn=CONSTANTS.AWS_POLICY_LAMBDA_BASIC_EXECUTION
    )

    # Add inline policy for S3 Archive bucket write access
    bucket_name = provider.naming.archive_s3_bucket()
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="S3ArchiveWriteAccess",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject"
                ],
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }]
        })
    )
```

#### Existing IAM Patterns Used as Reference

| Existing Role | File | Pattern Used |
|---------------|------|--------------|
| `writer_iam_role` | `layer_3_storage.py:90-138` | Basic execution + inline DynamoDB policy |
| `hot_cold_mover_iam_role` | `layer_3_storage.py` | Basic execution + S3 + DynamoDB |
| `cold_archive_mover_iam_role` | `layer_3_storage.py` | Basic execution + S3 full access |

#### IAM Destroy Functions Required

| Function | File | Status |
|----------|------|--------|
| `destroy_cold_writer_iam_role()` | `layer_3_storage.py` | ❌ Need to add |
| `destroy_archive_writer_iam_role()` | `layer_3_storage.py` | ❌ Need to add |

Both will use existing `_destroy_iam_role()` helper function.

#### Summary of IAM Changes

| File | Change |
|------|--------|
| `credentials_checker.py` | Add `iam:PutRolePolicy` to `layer_3["iam"]` |
| `layer_3_storage.py` | Add `create_cold_writer_iam_role()` |
| `layer_3_storage.py` | Add `destroy_cold_writer_iam_role()` |
| `layer_3_storage.py` | Add `create_archive_writer_iam_role()` |
| `layer_3_storage.py` | Add `destroy_archive_writer_iam_role()` |

---

## 5. Proposed Changes

### Component: Naming Functions

---

#### [MODIFY] [naming.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/naming.py)
- **Path:** `src/providers/aws/naming.py`
- **Description:** Add naming functions for Cold Writer and Archive Writer.

**Add after line 193 (after `writer_iam_role`):**
```python
def cold_writer_lambda_function(self) -> str:
    """Lambda function name for the cold writer (multi-cloud)."""
    return f"{self._twin_name}-cold-writer"

def cold_writer_iam_role(self) -> str:
    """IAM role name for the cold writer Lambda (multi-cloud)."""
    return f"{self._twin_name}-cold-writer"

def archive_writer_lambda_function(self) -> str:
    """Lambda function name for the archive writer (multi-cloud)."""
    return f"{self._twin_name}-archive-writer"

def archive_writer_iam_role(self) -> str:
    """IAM role name for the archive writer Lambda (multi-cloud)."""
    return f"{self._twin_name}-archive-writer"
```

---

### Component: New Lambda Functions

---

#### [NEW] [cold-writer/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/cold-writer/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/cold-writer/lambda_function.py`
- **Description:** Receives chunked data from remote Hot-to-Cold Mover, writes to S3 Cold bucket.

**Key Features:**
- Token validation via `X-Inter-Cloud-Token` header
- Accepts payload: `{iot_device_id, chunk_index, start_timestamp, end_timestamp, items[]}`
- Writes to S3 with `STANDARD_IA` storage class
- Returns `{statusCode, written, key}`

---

#### [NEW] [archive-writer/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/archive-writer/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/archive-writer/lambda_function.py`
- **Description:** Receives data from remote Cold-to-Archive Mover, writes to S3 Archive bucket.

**Key Features:**
- Token validation via `X-Inter-Cloud-Token` header
- Accepts payload: `{object_key, data, is_multipart, part_number, total_parts}`
- Writes to S3 with `DEEP_ARCHIVE` storage class
- Handles multipart reassembly if needed

---

#### [MODIFY] [hot-to-cold-mover/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/hot-to-cold-mover/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/hot-to-cold-mover/lambda_function.py`
- **Description:** Add multi-cloud logic with chunking.

**Changes:**
1. Add `ConfigurationError` class
2. Add `_is_multi_cloud_cold()` dual validation function
3. Add `MAX_CHUNK_SIZE_BYTES = 5 * 1024 * 1024`
4. Add `_chunk_items()` helper
5. Add `_post_to_remote_cold_writer()` with retry logic
6. Modify `flush_chunk_to_s3()` to conditionally call remote writer

**Key Code:**
```python
REMOTE_COLD_WRITER_URL = os.environ.get("REMOTE_COLD_WRITER_URL", "")
INTER_CLOUD_TOKEN = os.environ.get("INTER_CLOUD_TOKEN", "")

class ConfigurationError(Exception):
    """Raised when multi-cloud configuration is incomplete."""
    pass

def _is_multi_cloud_cold() -> bool:
    """Check if L3 Cold is on a different cloud than L3 Hot."""
    if not REMOTE_COLD_WRITER_URL:
        return False
    
    providers = DIGITAL_TWIN_INFO.get("config_providers")
    if not providers:
        raise ConfigurationError("config_providers missing from DIGITAL_TWIN_INFO")
    
    l3_hot = providers.get("layer_3_hot_provider")
    l3_cold = providers.get("layer_3_cold_provider")
    
    if not l3_hot or not l3_cold:
        raise ConfigurationError(f"Missing provider: l3_hot={l3_hot}, l3_cold={l3_cold}")
    
    return l3_hot != l3_cold
```

---

#### [MODIFY] [cold-to-archive-mover/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/lambda_functions/cold-to-archive-mover/lambda_function.py)
- **Path:** `src/providers/aws/lambda_functions/cold-to-archive-mover/lambda_function.py`
- **Description:** Add multi-cloud logic with memory guard.

**Changes:**
1. Add `ConfigurationError` class
2. Add `_is_multi_cloud_archive()` dual validation function
3. Add `MAX_SAFE_OBJECT_SIZE = 200 * 1024 * 1024`
4. Add `_post_to_remote_archive_writer()` with chunking
5. Modify main loop to conditionally call remote writer

---

### Component: Deployer Functions

---

#### [MODIFY] [layer_3_storage.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/layer_3_storage.py)
- **Path:** `src/providers/aws/layers/layer_3_storage.py`

**Changes:**

**1. Update `create_hot_cold_mover_lambda_function()` (~line 350):**
```python
env_vars = {
    "DIGITAL_TWIN_INFO": json.dumps(_get_digital_twin_info(config)),
    "DYNAMODB_TABLE_NAME": provider.naming.hot_dynamodb_table(),
    "S3_BUCKET_NAME": provider.naming.cold_s3_bucket()
}

# Multi-cloud: Add remote Cold Writer URL if L3 Cold is on different cloud
l3_hot = config.providers["layer_3_hot_provider"]
l3_cold = config.providers["layer_3_cold_provider"]

if l3_hot != l3_cold:
    conn_id = f"{l3_hot}_l3hot_to_{l3_cold}_l3cold"
    connections = getattr(config, 'inter_cloud', {}).get("connections", {})
    conn = connections.get(conn_id, {})
    url = conn.get("url", "")
    token = conn.get("token", "")
    
    if not url or not token:
        raise ValueError(
            f"Multi-cloud config incomplete for {conn_id}: url={bool(url)}, token={bool(token)}"
        )
    
    env_vars["REMOTE_COLD_WRITER_URL"] = url
    env_vars["INTER_CLOUD_TOKEN"] = token
```

**2. Update `create_cold_archive_mover_lambda_function()` (~line 507):**
```python
# Similar pattern for L3 Cold → L3 Archive
l3_cold = config.providers["layer_3_cold_provider"]
l3_archive = config.providers["layer_3_archive_provider"]

if l3_cold != l3_archive:
    conn_id = f"{l3_cold}_l3cold_to_{l3_archive}_l3archive"
    # ... same pattern ...
```

**3. Add Cold Writer functions (new section after Writer section ~line 230):**
```python
# ==========================================
# 1.6. Cold Writer Lambda (Multi-Cloud Only)
# ==========================================

def create_cold_writer_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Cold Writer Lambda (multi-cloud only)."""
    # ... similar to writer_iam_role but with S3 write access ...

def create_cold_writer_lambda_function(
    provider: 'AWSProvider',
    config: 'ProjectConfig',
    project_path: str
) -> str:
    """Creates the Cold Writer Lambda Function with Function URL."""
    # ... create Lambda with Function URL ...
```

**4. Add Archive Writer functions (new section):**
```python
# ==========================================
# 1.7. Archive Writer Lambda (Multi-Cloud Only)
# ==========================================

def create_archive_writer_iam_role(provider: 'AWSProvider') -> None:
    """Creates IAM Role for the Archive Writer Lambda (multi-cloud only)."""
    # ... S3 write access to archive bucket ...

def create_archive_writer_lambda_function(...) -> str:
    """Creates the Archive Writer Lambda Function with Function URL."""
    # ...
```

---

#### [MODIFY] [l3_adapter.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/providers/aws/layers/l3_adapter.py)
- **Path:** `src/providers/aws/layers/l3_adapter.py`

**Update `deploy_l3_cold()` (~line 98):**
```python
def deploy_l3_cold(context: 'DeploymentContext', provider: 'AWSProvider') -> None:
    from .layer_3_storage import (
        create_cold_s3_bucket,
        create_hot_cold_mover_iam_role,
        create_hot_cold_mover_lambda_function,
        create_hot_cold_mover_event_rule,
        # Multi-cloud: Cold Writer
        create_cold_writer_iam_role,
        create_cold_writer_lambda_function,
    )
    
    # ... existing code ...
    
    # Multi-cloud: Deploy Cold Writer if L3 Hot != L3 Cold
    l3_hot = context.config.providers["layer_3_hot_provider"]
    l3_cold = context.config.providers["layer_3_cold_provider"]
    
    if l3_hot != l3_cold:
        import time
        logger.info(f"[L3-Cold] Multi-cloud: Deploying Cold Writer (L3 Hot on {l3_hot})")
        create_cold_writer_iam_role(provider)
        time.sleep(10)
        cold_writer_url = create_cold_writer_lambda_function(provider, context.config, project_path)
        logger.info(f"[L3-Cold] Multi-cloud: Cold Writer URL: {cold_writer_url}")
```

**Update `deploy_l3_archive()` (~line 140):**
```python
# Similar pattern for Archive Writer when L3 Cold != L3 Archive
```

---

### Component: Documentation

---

#### [MODIFY] [docs-multi-cloud.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-multi-cloud.html)
- **Path:** `docs/docs-multi-cloud.html`
- **Description:** Add new section for L3 Mover Multi-Cloud Flow.

**Add new section with ASCII flowchart after existing "Cross-Cloud Data Flow" section:**
```html
<!-- L3 Storage Tier Flow -->
<div class="card mb-4">
    <h2>L3 Storage Tier Data Flow</h2>
    <p>When L3 storage tiers (Hot/Cold/Archive) span different clouds:</p>
    
    <pre class="bg-dark text-light p-3 rounded">
        <!-- ASCII flowchart similar to #3 Target State above -->
    </pre>
    
    <h3>Chunking Strategy</h3>
    <p>Cross-cloud transfers chunk data to stay within payload limits:</p>
    <ul>
        <li>AWS Lambda: 6 MB limit</li>
        <li>Azure Functions: 100 MB limit</li>
        <li>GCP Cloud Functions: 32 MB limit</li>
        <li><strong>Universal chunk size: 5 MB</strong> (conservative for AWS)</li>
    </ul>
</div>
```

---

#### [MODIFY] [docs-aws-deployment.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-aws-deployment.html)
- **Description:** Update L3 section to mention Cold Writer and Archive Writer.

---

#### [MODIFY] [docs-testing.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-testing.html)
- **Description:** Add new test file entries.

---

## 6. Implementation Phases

### Phase 0: Pre-Requisite Fixes (Bug Fixes & Templates)

> [!IMPORTANT]
> These fixes must be completed before proceeding with multi-cloud implementation.

| Step | File | Action |
|------|------|--------|
| 0.1 | `cold-to-archive-mover/lambda_function.py` | **BUG FIX:** Change `SOURCE_S3_BUCKET_NAME` → `COLD_S3_BUCKET_NAME` |
| 0.2 | `cold-to-archive-mover/lambda_function.py` | **BUG FIX:** Change `TARGET_S3_BUCKET_NAME` → `ARCHIVE_S3_BUCKET_NAME` |
| 0.3 | `upload/template/config_inter_cloud.json` | Add L3 Hot → L3 Cold connection example |
| 0.4 | `upload/template/config_inter_cloud.json` | Add L3 Cold → L3 Archive connection example |

### Phase 1: Core Infrastructure (Naming, Constants, Helpers, URL Persistence)

| Step | File | Action |
|------|------|--------|
| 1.1 | `src/providers/aws/naming.py` | Add `cold_writer_*` and `archive_writer_*` methods |
| 1.2 | `src/constants.py` | Add `COLD_WRITER_LAMBDA_DIR_NAME`, `ARCHIVE_WRITER_LAMBDA_DIR_NAME` |
| 1.3 | `src/api/credentials_checker.py` | Add `iam:PutRolePolicy` to `layer_3["iam"]` |
| 1.4 | `src/core/config_loader.py` | **NEW:** Add `save_inter_cloud_connection()` helper function |
| 1.5 | `src/providers/aws/layers/l2_adapter.py` | **FIX TODO:** Call `save_inter_cloud_connection()` after creating Ingestion URL |
| 1.6 | `src/providers/aws/layers/l3_adapter.py` | **FIX TODO:** Call `save_inter_cloud_connection()` after creating Writer URL |
| 1.7 | `src/providers/aws/layers/l3_adapter.py` | **NEW:** Call `save_inter_cloud_connection()` after creating Cold Writer URL |
| 1.8 | `src/providers/aws/layers/l3_adapter.py` | **NEW:** Call `save_inter_cloud_connection()` after creating Archive Writer URL |

### Phase 2: New Lambda Functions (Writers)

| Step | File | Action |
|------|------|--------|
| 2.1 | `lambda_functions/cold-writer/__init__.py` | Create empty init |
| 2.2 | `lambda_functions/cold-writer/lambda_function.py` | Create Cold Writer Lambda |
| 2.3 | `lambda_functions/archive-writer/__init__.py` | Create empty init |
| 2.4 | `lambda_functions/archive-writer/lambda_function.py` | Create Archive Writer Lambda |

### Phase 3: Modify Existing Movers

| Step | File | Action |
|------|------|--------|
| 3.1 | `hot-to-cold-mover/lambda_function.py` | Add `_is_multi_cloud_cold()`, chunking, HTTP POST |
| 3.2 | `cold-to-archive-mover/lambda_function.py` | Add `_is_multi_cloud_archive()`, memory guard, HTTP POST |

### Phase 4: Deployer Functions

| Step | File | Action |
|------|------|--------|
| 4.1 | `layer_3_storage.py` | Add `create_cold_writer_*` functions |
| 4.2 | `layer_3_storage.py` | Add `create_archive_writer_*` functions |
| 4.3 | `layer_3_storage.py` | Update `create_hot_cold_mover_lambda_function()` with multi-cloud env vars |
| 4.4 | `layer_3_storage.py` | Update `create_cold_archive_mover_lambda_function()` with multi-cloud env vars |
| 4.5 | `l3_adapter.py` | Update `deploy_l3_cold()` with Cold Writer deployment |
| 4.6 | `l3_adapter.py` | Update `destroy_l3_cold()` with Cold Writer destruction |
| 4.7 | `l3_adapter.py` | Update `deploy_l3_archive()` with Archive Writer deployment |
| 4.8 | `l3_adapter.py` | Update `destroy_l3_archive()` with Archive Writer destruction |

### Phase 5: Tests

| Step | File | Action |
|------|------|--------|
| 5.1 | `tests/unit/test_config_loader.py` | Add `save_inter_cloud_connection()` tests (6 tests) |
| 5.2 | `tests/unit/lambda_functions/test_mover_multi_cloud.py` | Create comprehensive mover unit tests (~37 tests) |
| 5.3 | `tests/unit/lambda_functions/test_lambda_multi_cloud.py` | Add Cold Writer and Archive Writer tests (~16 tests) |
| 5.4 | `tests/integration/aws/test_aws_multi_cloud_config.py` | Add L3 Cold/Archive deployment tests (~14 tests) |
| 5.5 | Verify existing env var bug fix | Add test `test_cold_archive_mover_uses_correct_env_vars` |

### Phase 6: Documentation

| Step | File | Action |
|------|------|--------|
| 6.1 | `docs/docs-multi-cloud.html` | Add L3 Mover section with flowchart, 5MB chunking explanation |
| 6.2 | `docs/docs-multi-cloud.html` | Add `save_inter_cloud_connection` workflow diagram |
| 6.3 | `docs/docs-aws-deployment.html` | Update L3 section: Cold Writer, Archive Writer, multi-cloud env vars |
| 6.4 | `docs/docs-configuration.html` | Document `config_inter_cloud.json` structure and auto-generation |
| 6.5 | `docs/docs-testing.html` | Add new test files and test count update |

---

## 7. Comprehensive Test Plan

### 7.0 Tests for `save_inter_cloud_connection()` (NEW)

**File:** `tests/unit/test_config_loader.py` (new tests to add)

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_save_inter_cloud_connection_creates_file` | File doesn't exist | Creates new file with connection |
| `test_save_inter_cloud_connection_updates_existing` | File exists with other connections | Adds new connection, preserves others |
| `test_save_inter_cloud_connection_overwrites_same_conn` | Connection ID already exists | Updates URL and token |
| `test_save_inter_cloud_connection_preserves_json_format` | Any save | Valid JSON with `connections` key |
| `test_save_inter_cloud_connection_handles_empty_token` | `token=""` | Saves empty token (warning logged) |
| `test_save_inter_cloud_connection_invalid_path` | Non-existent directory | Raises appropriate error |

### 7.0.1 Existing Test Updates Required

| Existing Test File | Update Required | Reason |
|-------------------|-----------------|--------|
| `tests/integration/aws/test_aws_multi_cloud_config.py` | Add L3 Cold/Archive provider validation tests | Currently only tests L3 Hot provider |
| `tests/unit/lambda_functions/test_lambda_multi_cloud.py` | Add Cold Writer and Archive Writer tests | Follow existing Writer test patterns |

### 7.0.2 Bug Fix Verification Tests

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_cold_archive_mover_uses_correct_env_vars` | Lambda deployed | Uses `COLD_S3_BUCKET_NAME` not `SOURCE_S3_BUCKET_NAME` |
| `test_cold_archive_mover_env_vars_match_deployer` | Deployer vs Lambda | Env var names match between deployer and Lambda code |

### 7.1 Unit Tests: Hot-to-Cold Mover Multi-Cloud

**File:** `tests/unit/lambda_functions/test_mover_multi_cloud.py`

#### `_is_multi_cloud_cold()` Tests (10 tests)

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_is_multi_cloud_cold_no_url_returns_false` | `REMOTE_COLD_WRITER_URL=""` | `False` |
| `test_is_multi_cloud_cold_whitespace_url_returns_false` | `REMOTE_COLD_WRITER_URL="  "` | `False` |
| `test_is_multi_cloud_cold_url_set_same_provider_returns_false` | URL set, L3 Hot == L3 Cold | `False` |
| `test_is_multi_cloud_cold_url_set_different_provider_returns_true` | URL set, L3 Hot != L3 Cold | `True` |
| `test_is_multi_cloud_cold_missing_config_providers_raises` | `config_providers` missing | `ConfigurationError` |
| `test_is_multi_cloud_cold_missing_l3_hot_provider_raises` | `layer_3_hot_provider` missing | `ConfigurationError` |
| `test_is_multi_cloud_cold_missing_l3_cold_provider_raises` | `layer_3_cold_provider` missing | `ConfigurationError` |
| `test_is_multi_cloud_cold_null_provider_raises` | `layer_3_cold_provider=null` | `ConfigurationError` |
| `test_is_multi_cloud_cold_empty_provider_raises` | `layer_3_cold_provider=""` | `ConfigurationError` |
| `test_is_multi_cloud_cold_case_sensitivity` | `layer_3_hot_provider="AWS"` vs `"aws"` | Case-sensitive comparison |

#### Chunking Logic Tests (12 tests)

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_chunk_items_empty_list` | Empty items list | Empty chunks list |
| `test_chunk_items_single_small_item` | 1 item < 5MB | 1 chunk with 1 item |
| `test_chunk_items_multiple_small_items` | 100 items < 5MB total | 1 chunk with 100 items |
| `test_chunk_items_exceeds_limit` | Items total > 5MB | Multiple chunks |
| `test_chunk_items_exact_boundary` | Exactly 5MB | 1 chunk |
| `test_chunk_items_one_byte_over` | 5MB + 1 byte | 2 chunks |
| `test_chunk_items_single_large_item` | 1 item = 4.9MB | 1 chunk |
| `test_chunk_items_single_oversized_item` | 1 item > 5MB | Error or split handling |
| `test_estimate_payload_size_accuracy` | Various items | Within 5% of actual JSON size |
| `test_chunk_preserves_item_order` | Items 1,2,3,4,5 | Order preserved in chunks |
| `test_chunk_unicode_items` | Items with unicode | Correct byte calculation |
| `test_chunk_nested_objects` | Deeply nested items | Correct handling |

#### `_post_to_remote_cold_writer()` Tests (15 tests)

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_post_cold_writer_success` | Remote returns 200 | Items sent, no error |
| `test_post_cold_writer_missing_token_raises` | `INTER_CLOUD_TOKEN=""` | `ValueError` |
| `test_post_cold_writer_whitespace_token_raises` | `INTER_CLOUD_TOKEN="  "` | `ValueError` |
| `test_post_cold_writer_sends_auth_header` | Valid request | `X-Inter-Cloud-Token` header sent |
| `test_post_cold_writer_payload_structure` | Valid request | Correct envelope fields |
| `test_post_cold_writer_retry_on_500` | Remote returns 500 | 3 retries |
| `test_post_cold_writer_retry_on_503` | Remote returns 503 | 3 retries |
| `test_post_cold_writer_no_retry_on_400` | Remote returns 400 | Immediate failure |
| `test_post_cold_writer_no_retry_on_403` | Remote returns 403 | Immediate failure |
| `test_post_cold_writer_timeout_retry` | Connection timeout | Retry with backoff |
| `test_post_cold_writer_dns_failure` | Invalid hostname | Descriptive error |
| `test_post_cold_writer_connection_refused` | Connection refused | Descriptive error |
| `test_post_cold_writer_exponential_backoff` | Multiple failures | Delay doubles |
| `test_post_cold_writer_max_retries_exceeded` | 4th attempt | Raises exception |
| `test_post_cold_writer_partial_success` | Chunk 2/3 fails | Appropriate error handling |

### 7.2 Unit Tests: Cold Writer Lambda (10 tests)

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_cold_writer_valid_token_writes_to_s3` | Valid token, valid data | S3 `put_object` called |
| `test_cold_writer_invalid_token_returns_403` | Wrong token | 403 Unauthorized |
| `test_cold_writer_missing_token_returns_403` | No header | 403 Unauthorized |
| `test_cold_writer_empty_token_returns_403` | Empty token value | 403 Unauthorized |
| `test_cold_writer_missing_iot_device_id_returns_400` | No `iot_device_id` | 400 Bad Request |
| `test_cold_writer_missing_items_returns_400` | No `items` | 400 Bad Request |
| `test_cold_writer_empty_items_returns_400` | `items: []` | 400 Bad Request |
| `test_cold_writer_s3_key_format` | Valid write | Key: `{device_id}/{start}-{end}/chunk-{idx}.json` |
| `test_cold_writer_s3_storage_class` | Valid write | `StorageClass='STANDARD_IA'` |
| `test_cold_writer_s3_error_returns_500` | S3 error | 500 Internal Server Error |

### 7.3 Unit Tests: Cold-to-Archive Mover Multi-Cloud (12 tests)

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_is_multi_cloud_archive_no_url_returns_false` | No env var | `False` |
| `test_is_multi_cloud_archive_different_providers` | L3 Cold != L3 Archive | `True` |
| `test_is_multi_cloud_archive_same_providers` | L3 Cold == L3 Archive | `False` |
| `test_archive_mover_memory_guard_skips_large` | Object > 200MB | Skipped with warning |
| `test_archive_mover_memory_guard_processes_normal` | Object < 200MB | Processed normally |
| `test_archive_mover_single_cloud_copies_s3` | Same cloud | `s3.copy_object` called |
| `test_archive_mover_multi_cloud_posts_http` | Different cloud | HTTP POST called |
| `test_archive_mover_deletes_after_success` | Transfer success | Source object deleted |
| `test_archive_mover_no_delete_on_failure` | Transfer fails | Source NOT deleted |
| `test_post_archive_writer_success` | Remote returns 200 | Success |
| `test_post_archive_writer_chunking` | Object > 5MB | Multiple chunks sent |
| `test_post_archive_writer_metadata` | Valid request | Includes `object_key`, `source_cloud` |

### 7.4 Unit Tests: Archive Writer Lambda (8 tests)

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_archive_writer_valid_token_writes` | Valid token | S3 `put_object` called |
| `test_archive_writer_invalid_token_403` | Wrong token | 403 |
| `test_archive_writer_s3_storage_class` | Valid write | `StorageClass='DEEP_ARCHIVE'` |
| `test_archive_writer_missing_object_key_400` | No `object_key` | 400 |
| `test_archive_writer_missing_data_400` | No `data` | 400 |
| `test_archive_writer_multipart_handling` | `is_multipart=True` | Reassembles parts |
| `test_archive_writer_multipart_incomplete` | Missing part | 400 or pending state |
| `test_archive_writer_s3_error_500` | S3 error | 500 |

### 7.5 Integration Tests: Deployer Functions (14 tests)

**File:** `tests/integration/aws/test_aws_multi_cloud_config.py`

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_deploy_l3_cold_creates_cold_writer_when_different` | L3 Hot != L3 Cold | Cold Writer deployed |
| `test_deploy_l3_cold_skips_cold_writer_when_same` | L3 Hot == L3 Cold | Cold Writer NOT deployed |
| `test_deploy_l3_archive_creates_archive_writer_when_different` | L3 Cold != L3 Archive | Archive Writer deployed |
| `test_deploy_l3_archive_skips_archive_writer_when_same` | L3 Cold == L3 Archive | Archive Writer NOT deployed |
| `test_create_cold_writer_function_url` | Multi-cloud | Function URL created |
| `test_create_archive_writer_function_url` | Multi-cloud | Function URL created |
| `test_create_hot_cold_mover_injects_env_vars` | L3 Hot != L3 Cold | `REMOTE_COLD_WRITER_URL` injected |
| `test_create_hot_cold_mover_no_env_vars_same_cloud` | L3 Hot == L3 Cold | No multi-cloud env vars |
| `test_create_cold_archive_mover_injects_env_vars` | L3 Cold != L3 Archive | `REMOTE_ARCHIVE_WRITER_URL` injected |
| `test_create_cold_writer_missing_token_fails` | No `expected_token` | `ValueError` |
| `test_create_archive_writer_missing_token_fails` | No `expected_token` | `ValueError` |
| `test_destroy_l3_cold_destroys_cold_writer` | Multi-cloud | Cold Writer destroyed |
| `test_destroy_l3_archive_destroys_archive_writer` | Multi-cloud | Archive Writer destroyed |
| `test_hot_cold_mover_missing_connection_fails` | No connection config | `ValueError` |

### 7.6 Edge Case Tests: Boundary Conditions (8 tests)

| Test Name | Scenario | Expected Result |
|-----------|----------|-----------------|
| `test_chunk_exactly_5mb` | Payload exactly 5,242,880 bytes | 1 chunk |
| `test_chunk_5mb_plus_1_byte` | Payload 5,242,881 bytes | 2 chunks |
| `test_empty_dynamodb_query` | No items to move | No HTTP calls, no errors |
| `test_s3_object_exactly_200mb` | Object at memory limit | Processed normally |
| `test_s3_object_200mb_plus_1` | Object 1 byte over limit | Skipped with warning |
| `test_unicode_device_id` | `iot_device_id="传感器-1"` | Correct S3 key encoding |
| `test_special_chars_in_timestamps` | Timestamps with `+` | URL encoding handled |
| `test_concurrent_chunk_sends` | Multiple items same batch | Sequential sends (no race) |

**Total Tests: 89 tests**

---

## 8. Running Tests

```bash
# Run all tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -q

# Run only mover multi-cloud unit tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit/lambda_functions/test_mover_multi_cloud.py -v

# Run only new integration tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/integration/aws/test_aws_multi_cloud_config.py -k "cold_writer or archive_writer" -v

# Run with coverage
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --cov=src --cov-report=term-missing
```

---

## 9. Verification Checklist

- [ ] All 417+ existing tests still pass
- [ ] Naming functions added: `cold_writer_*`, `archive_writer_*`
- [ ] Cold Writer Lambda created with token validation
- [ ] Archive Writer Lambda created with token validation
- [ ] Hot-to-Cold Mover has `_is_multi_cloud_cold()` and chunking
- [ ] Cold-to-Archive Mover has `_is_multi_cloud_archive()` and memory guard
- [ ] `create_hot_cold_mover_lambda_function()` injects multi-cloud env vars
- [ ] `create_cold_archive_mover_lambda_function()` injects multi-cloud env vars
- [ ] `deploy_l3_cold()` conditionally deploys Cold Writer
- [ ] `deploy_l3_archive()` conditionally deploys Archive Writer
- [ ] All 89 new tests pass
- [ ] `docs-multi-cloud.html` updated with L3 flowchart
- [ ] `docs-aws-deployment.html` updated
- [ ] `docs-testing.html` updated
- [ ] No silent fallbacks (all missing config raises errors)
- [ ] No silent passes (all skips logged with warnings)

---

## 10. Design Decisions

### Decision 1: 5MB Universal Chunk Size
**Rationale:** AWS Lambda's 6MB limit is the smallest. Using 5MB provides safety margin for JSON overhead and is consistent across all cloud combinations.

### Decision 2: Option A (Read-Chunk-POST) for Cold-to-Archive
**Rationale:** Archive data is typically already chunked at ~5MB from Hot-to-Cold mover. Memory-based approach is simpler and aligns with existing patterns. Memory guard skips objects exceeding safe threshold.

### Decision 3: Separate Cold Writer and Archive Writer
**Rationale:** Allows maximum flexibility. L3 Hot, Cold, and Archive can each be on different clouds.

### Decision 4: Dual Validation (URL + Provider Check)
**Rationale:** Prevents misconfiguration. Both env var AND provider mapping must indicate multi-cloud mode, catching deployment errors early.

### Decision 5: Use Existing `layer_3_cold_provider` and `layer_3_archive_provider` Keys
**Rationale:** Already present in template `config_providers.json`. No schema changes needed.
