# E2E Test Progress & Status

**Last Updated:** 2026-02-09 21:40  
**Status:** 🎉 **ALL 11 SCENARIOS CONFIGURED** (8 cross-cloud + 3 same-cloud)

---

## Summary (All 11 Scenarios)

| Scenario | Last Run | Tests Passed | Tests Failed | Tests Skipped | Result |
|----------|----------|--------------|--------------|---------------|--------|
| **AWS→GCP** | Feb 8 (12:48) | 19 | 0 | 2 | ✅ **PASS** |
| **AWS→Azure** | Feb 8 (00:12) | 19 | 0 | 2 | ✅ **PASS** |
| **Azure→AWS** | Feb 8 (07:26) | 19 | 0 | 2 | ✅ **PASS** |
| **Azure→GCP** | Feb 8 (12:13) | 19 | 0 | 2 | ✅ **PASS** |
| **GCP→AWS** | Feb 8 (13:16) | 18 | 0 | 3 | ✅ **PASS** |
| **GCP→Azure** | Feb 8 (13:39) | 18 | 0 | 3 | ✅ **PASS** |
| **Cross-L4** | Feb 8 (09:56) | 19 | 0 | 2 | ✅ **PASS** |
| **Shared-L2-L3** | — | — | — | — | 🆕 **NEW** |
| **AWS** | Feb 7 (22:11) | 18 | 0 | 3 | ✅ **PASS** |
| **Azure** | Feb 8 (00:06) | 19 | 0 | 2 | ✅ **PASS** |
| **GCP** | Feb 7 (22:30) | 13 | 0 | 8 | ✅ **PASS** |

---

## Scenario Provider Configuration

| Scenario | L1 (IoT) | L2 (Process) | L3-Hot | L3-Cold | L3-Archive | L4 (Twins) | L5 (Viz) |
|----------|:--------:|:------------:|:------:|:-------:|:----------:|:----------:|:--------:|
| **aws-azure** | AWS | Azure | GCP | AWS | Azure | Azure | AWS |
| **aws-gcp** | AWS | GCP | Azure | AWS | GCP | AWS | Azure |
| **azure-aws** | Azure | AWS | GCP | Azure | AWS | AWS | Azure |
| **azure-gcp** | Azure | GCP | AWS | Azure | GCP | Azure | AWS |
| **gcp-aws** | GCP | AWS | Azure | GCP | AWS | AWS | Azure |
| **gcp-azure** | GCP | Azure | AWS | GCP | Azure | Azure | AWS |
| **cross-l4** | Azure | **AWS** | GCP | Azure | AWS | **Azure** | Azure |
| **shared-l2-l3** | GCP | **AWS** | GCP | **AWS** | Azure | AWS | AWS |
| **aws** | AWS | AWS | AWS | AWS | AWS | AWS | AWS |
| **azure** | Azure | Azure | Azure | Azure | Azure | Azure | Azure |
| **gcp** | GCP | GCP | GCP | GCP | GCP | none | none |

> **Note:** GCP has no managed L4 (Digital Twins) or L5 (Grafana) services.
> **Note:** `shared-l2-l3` tests **L2 = L3-Cold** (both AWS) with L3-Hot on GCP — catches cold-writer boundary bug.

---

## Cross-Cloud Boundary Coverage

| Boundary | Total Combos | Tested | Coverage |
|----------|:------------:|:------:|:--------:|
| L1→L2 | 6 | 6 | ✅ 100% |
| L2→L3-Hot | 6 | 6 | ✅ 100% |
| L3-Hot→L3-Cold | 6 | 6 | ✅ 100% |
| L3-Cold→L3-Archive | 6 | 6 | ✅ 100% |
| L2→L4 (ADT) | 2 | **2** | ✅ 100% |
| L4→L5 | 2 | 2 | ✅ 100% |
| **L2=L3-Cold edge** | — | **1** | ✅ `shared-l2-l3` |

> **Note:** `cross-l4` specifically tests AWS L2 → Azure L4 (ADT) boundary.  
> **Note:** `shared-l2-l3` specifically tests the cold-writer L0 boundary when L2 shares a provider with L3-Cold.

---

## Deployed Functions by Layer

| Layer | Functions |
|-------|-----------|
| L0 (Glue) | ingestion, connector, hot-writer, cold-writer, archive-writer, adt-pusher, l0-hot-reader |
| L1 (Acquisition) | dispatcher |
| L2 (Processing) | persister, processor_wrapper, event-checker, event_feedback_wrapper |
| L3 (Storage) | hot-reader, hot-reader-last-entry, hot-to-cold-mover, cold-to-archive-mover |
| L4 (Management) | adt-updater (Azure), digital-twin-data-connector (AWS) |

---

## Event Flow Architecture

```
IoT Device → Dispatcher → Processor → Persister
                                        ↓
              ┌─────────────────────────┴──────────────────────────┐
              ↓                         ↓                          ↓
        Hot Storage               ADT Pusher               Event-Checker
     (DynamoDB/Cosmos)          (Azure L4)             (if USE_EVENT_CHECKING)
                                                              ↓
                                                    ┌─────────┴─────────┐
                                                    ↓                   ↓
                                            Workflow Action      Lambda Action
                                         (Step Fn/Logic App)   (user callback)
                                                    ↓                   ↓
                                                    └─────────┬─────────┘
                                                              ↓
                                                       Feedback Func
                                                      (send to device)
```

**Event Flow Tests:**
- `test_13`: Event-Checker invoked
- `test_14`: Lambda action called  
- `test_15`: Workflow triggered
- `test_16`: Feedback sent

**L3 Mover Deployment Verification:**
- `test_17`: Hot-to-cold mover deployed (checks function + env vars)
- `test_18`: Cold-to-archive mover deployed (checks function + env vars)



## Session References

| Session ID | Focus |
|------------|-------|
| AI-0208-2368 | GCP IAM Soft-Delete Cleanup Fix + Azure→AWS E2E |
| AI-0207-da82 | All 3 Same-Cloud E2E Runs + GCP Archive Bucket Fix |
| AI-0207-5896 | L3 Mover Deployment Fix (Cross-Cloud) |
| AI-0204-3b0e | AWS Same-Cloud E2E: IAM Fixes + CloudWatch Polling |
| AI-0202-fee9 | Hot-Reader DecimalEncoder + Timeout Fix |
| AI-0202-f1ac | GCP Dispatcher Pub/Sub Base64 Fix |
| AI-0201-9886 | ADT Pusher JSON Patch Fix |
| AI-0130-5dda | TwinMaker Data Connector Fix |

---

## Latest Run Details

### AWS Same-Cloud (Feb 7, 22:11 — with cleanup)
- **Duration**: 13m 58s
- **Result**: `18 passed, 3 skipped, 0 failed` ✅
- **Cleanup**: ✅ 87 resources destroyed (TwinMaker SDK fallback used)
- **Key tests**:
  - `test_08_verify_hot_storage` ✅
  - `test_10_twinmaker_entities` ✅ (3 entities)
  - `test_10b_twinmaker_telemetry` ✅
  - `test_13–16_event_flow` ✅ (all 4 passed)
  - `test_17_hot_to_cold_mover` ✅
  - `test_18_cold_to_archive_mover` ✅
- **Skipped**: 3 tests (ADT twins, Azure functions — not applicable)

### GCP Same-Cloud (Feb 7, 22:30 — with cleanup)
- **Duration**: 6m 21s
- **Result**: `13 passed, 8 skipped, 0 failed` ✅
- **Cleanup**: ✅ 64 resources destroyed
- **Fix applied**: GCP archive bucket `Invalid index` on `gcp_storage.tf:343` (see fixes below)
- **Key tests**:
  - `test_08_verify_hot_storage` ✅
  - `test_13–16_event_flow` ✅ (all 4 passed)
  - `test_17_hot_to_cold_mover` ✅
  - `test_18_cold_to_archive_mover` ✅ (`COLD_BUCKET_NAME: digital-twin-dev-481720-sc2-gcp-cold`)
- **Skipped**: 8 tests (L4/L5 not available for GCP, IoT devices, Azure functions)

### Azure Same-Cloud (Feb 8, 00:06 — with cleanup)
- **Duration**: 48m 06s
- **Result**: `19 passed, 2 skipped, 0 failed` ✅
- **Cleanup**: ✅ Resources destroyed
- **Key tests**:
  - `test_08_verify_hot_storage` ✅
  - `test_09_iot_devices_registered` ✅ (3 devices)
  - `test_11_adt_twins` ✅ (6 twins)
  - `test_11b_adt_twin_telemetry` ✅
  - `test_13–16_event_flow` ✅ (all 4 passed)
  - `test_17_hot_to_cold_mover` ✅
  - `test_18_cold_to_archive_mover` ✅
- **Skipped**: 2 tests (TwinMaker — not applicable)

### AWS→GCP (Feb 8, 12:48 — with cleanup)
- **Duration**: 21m 03s
- **Result**: `19 passed, 2 skipped, 0 failed` ✅
- **Cleanup**: ✅ Terraform destroy + SDK fallback
- **Key tests**:
  - `test_08_verify_hot_storage` ✅ (data found in attempt 3/300)
  - `test_10_twinmaker_entities` ✅ (3 entities)
  - `test_10b_twinmaker_telemetry` ✅
  - `test_13–16_event_flow` ✅ (all 4 passed)
  - `test_17_hot_to_cold_mover` ✅
  - `test_18_cold_to_archive_mover` ✅
- **Skipped**: 2 tests (ADT — not applicable)

### GCP→AWS (Feb 8, 13:16 — with cleanup)
- **Duration**: 27m 48s
- **Result**: `18 passed, 3 skipped, 0 failed` ✅
- **Cleanup**: ✅ Terraform destroy + SDK fallback
- **Key tests**:
  - `test_08_verify_hot_storage` ✅
  - `test_10_twinmaker_entities` ✅ (3 entities)
  - `test_10b_twinmaker_telemetry` ✅ (verified in 1 attempt!)
  - `test_12_azure_functions_deployed` ✅
  - `test_13–16_event_flow` ✅ (all 4 passed)
  - `test_17_hot_to_cold_mover` ✅
  - `test_18_cold_to_archive_mover` ✅
- **Skipped**: 3 tests (IoT devices, ADT twins, ADT telemetry — not applicable)

### GCP→Azure (Feb 8, 13:39 — with cleanup)
- **Duration**: 22m 01s
- **Result**: `18 passed, 3 skipped, 0 failed` ✅
- **Resources**: 91 deployed, 90 destroyed
- **Cleanup**: ✅ Terraform destroy + SDK
- **Key tests**:
  - `test_08_verify_hot_storage` ✅
  - `test_11_adt_twins` ✅ — 6 ADT twins
  - `test_11b_adt_twin_telemetry` ✅
  - `test_12_azure_functions_deployed` ✅
  - `test_13–16_event_flow` ✅ (Logic App workflow succeeded)
  - `test_17_hot_to_cold_mover` ✅
  - `test_18_cold_to_archive_mover` ✅
- **Skipped**: 3 tests (IoT devices, TwinMaker — not applicable)

### Azure→GCP (Feb 8, 12:13 — with cleanup)
- **Duration**: 15m 46s
- **Result**: `19 passed, 2 skipped, 0 failed` ✅
- **Resources**: 106 deployed
- **Cleanup**: ✅ 106 destroyed via Terraform + SDK
- **Key tests**:
  - `test_11_adt_twins` ✅ — 6 ADT twins
  - `test_11b_adt_twin_telemetry` ✅
  - `test_13–16_event_flow` ✅ (all 4 passed)
  - `test_17_hot_to_cold_mover` ✅
  - `test_18_cold_to_archive_mover` ✅
- **Skipped**: 2 tests (TwinMaker — not applicable)

### Cross-L4 (Feb 8, 09:56 — with cleanup)
- **Duration**: 22m 22s
- **Result**: `19 passed, 2 skipped, 0 failed` ✅
- **Resources**: 109 deployed
- **Cleanup**: ✅ Terraform destroy completed
- **Key tests**:
  - `test_05_l4_twins` ✅ — Azure Digital Twins (cross-L4: AWS L2 → Azure L4)
  - `test_11_adt_twins` ✅ — 6 ADT twins found
  - `test_11b_adt_twin_telemetry` ✅ — telemetry pushed via ADT Pusher
  - `test_12_azure_functions_deployed` ✅ — `adt-pusher`, `cold-writer`, `hot-reader`, `hot-reader-last-entry`
  - `test_13–16_event_flow` ✅ (all 4 passed)
  - `test_17_hot_to_cold_mover` ✅
  - `test_18_cold_to_archive_mover` ✅
- **Skipped**: 2 tests (TwinMaker — not applicable, L4 is Azure ADT)

### Azure→AWS (Feb 8, 07:26 — with cleanup)
- **Duration**: 21m 11s
- **Result**: `19 passed, 2 skipped, 0 failed` ✅
- **Fix verified**: GCP IAM soft-delete cleanup fix (`fd76cc8`)
- **Key tests**:
  - `test_01_l0_setup` ✅ — GCP IAM role created successfully (previously failed)
  - `test_13–16_event_flow` ✅ (all 4 passed)
  - `test_17_hot_to_cold_mover` ✅
  - `test_18_cold_to_archive_mover` ✅
- **Skipped**: 2 tests (TwinMaker — not applicable)
- **Cleanup**: ✅ Terraform destroy completed (minor TwinMaker SDK fallback)

### AWS→Azure (Feb 8, 00:12 — skip-cleanup)
- **Duration**: 17m 08s
- **Result**: `19 passed, 2 skipped, 0 failed` ✅
- **Fix verified**: L3 mover build pipeline fix (`bfb2204`) — `cold-to-archive-mover` now built for cold provider
- **Key tests**:
  - `test_13–16_event_flow` ✅ (all 4 passed)
  - `test_17_hot_to_cold_mover` ✅ (GCP: `FIRESTORE_COLLECTION: sc2-aws-azure-hot-data`)
  - `test_18_cold_to_archive_mover` ✅ (AWS: `sc2-aws-azure-l3-cold-to-archive-mover`)
- **Skipped**: 2 tests (TwinMaker — not applicable)
- **Output**: `tests/e2e/multicloud/.build/e2e_output_deployer-aws-azure_20260207_231212.txt`

---

## Fixes Applied (Feb 9 — L0 Boundary Bug)

### 1. Cold-Writer Registry Boundary Mismatch

**Problem:** `cold-writer.zip` not built → Terraform `filebase64sha256` fails with file not found.

**Root Cause:** Function registry used boundary `(layer_2_provider, layer_3_cold_provider)` but cold-writer bridges **L3-hot → L3-cold**. When production config had `L2 = L3-cold = aws`, the check `L2 ≠ L3-cold` was false → zip skipped. All 10 E2E scenarios accidentally had `L2 ≠ L3-cold`, masking the bug.

**Fix:** Changed boundary to `(layer_3_hot_provider, layer_3_cold_provider)`. Also fixed `l0-hot-reader` and `l0-hot-reader-last-entry` boundaries from `(layer_3_hot_provider, layer_5_provider)` to `(layer_4_provider, layer_3_hot_provider)`.

**File:** `src/function_registry.py` (lines 109, 127, 134)

**Coverage:** Added E2E scenario `shared-l2-l3` + 4 unit tests in `TestL0BoundaryEdgeCases`.

---

## Fixes Applied (Feb 8 — GCP IAM Cleanup)

### 1. GCP Soft-Deleted IAM Role Cleanup (AI-0208-2368)

**Problem:** E2E tests failed with `Cannot add new grants to deleted role` after cleanup.

**Root Cause:** GCP soft-deletes custom IAM roles (kept in DELETED state for 7-44 days). The cleanup script called `roles().list()` without `showDeleted=True`, making it completely blind to soft-deleted roles. Terraform then failed trying to add grants to the invisible deleted role.

**Fix:** Added `showDeleted=True` to `roles().list()`. For roles already in DELETED state, call `roles().undelete()` first, then `roles().delete()`.

**File:** `src/providers/gcp/cleanup.py` (lines 308-345)

---

## Fixes Applied (Feb 7 — GCP Archive Bucket)

### 1. GCP Archive Bucket Invalid Index (AI-0207-da82)

**Problem:** `Invalid index: google_storage_bucket.archive is empty tuple` — GCP same-cloud E2E test crashed during Terraform apply.

**Root Cause:** `google_storage_bucket.archive` has `count = archive_enabled && !cold_enabled`. In same-cloud GCP (both cold and archive = GCP), the dedicated archive bucket is not created (cold bucket handles archiving via lifecycle rule). But `cold_to_archive_mover` env var referenced `archive[0].name` without accounting for this.

**Fix:** Wrapped in `try()` with cold bucket fallback:
```hcl
# Before:
ARCHIVE_BUCKET_NAME = local.gcp_l3_archive_enabled ? google_storage_bucket.archive[0].name : ""
# After:
ARCHIVE_BUCKET_NAME = local.gcp_l3_archive_enabled ? try(google_storage_bucket.archive[0].name, google_storage_bucket.cold[0].name) : ""
```

**File:** `src/terraform/gcp_storage.tf` (line 343)

---

## Fixes Applied (Feb 6 — GCP Workflow)

### 1. GCP Function Base URL Env Var

**Problem:** `KeyError: FunctionA_URL` — workflow execution failed because function URLs were missing from payload.

**Root Cause:** `GCP_FUNCTION_BASE_URL` env var was not configured for event-checker.

**Fix:** Added `GCP_FUNCTION_BASE_URL` env var to event-checker Terraform config.

**File:** `src/terraform/gcp_compute.tf`

---

### 2. Event-Action URL Pattern Fix

**Problem:** 404 errors — workflow called functions at wrong URL.

**Root Cause:** URL pattern was `{twin}-{func}` but deployed functions are named `{twin}-event-action-{func}`.

**Fix:** Added `event-action-` prefix in `_build_workflow_payload()` and `_trigger_action()`.

**File:** `src/providers/gcp/cloud_functions/event-checker/main.py`

---

### 3. Workflow OIDC Authentication

**Problem:** 403 Forbidden — workflow couldn't invoke Cloud Functions Gen2.

**Root Cause:** User-provided workflow template lacked `auth: {type: OIDC}` on HTTP calls. Cloud Functions Gen2 (backed by Cloud Run) require OIDC tokens even when IAM `roles/run.invoker` is granted.

**Fix:** Added `auth: type: OIDC` to both `callFunctionA` and `callFunctionB` steps in template. Also added validation error in `validator.py` to catch missing auth during upload.

**Files:** `upload/template/state_machines/google_cloud_workflow.yaml`, `src/validator.py`

---

## Fixes Applied (Feb 6 — AWS)

### 1. L4 Connector IAM Policy Fix (AI-0204-3b0e)

**Problem:** `AccessDeniedException: not authorized to perform lambda:InvokeFunction on l3-hot-reader`

**Root Cause:** IAM policy referenced `l0-hot-reader` instead of `l3-hot-reader`.

**Fix:** Changed `Resource` ARN to use `local.aws_l3_hot_reader_name`.

**File:** `src/terraform/aws_twins.tf`

---

### 2. L3 TwinMaker IAM Permission (AI-0204-3b0e)

**Problem:** `AccessDeniedException: not authorized to perform iottwinmaker:GetEntity`

**Root Cause:** L3 Lambda role lacked TwinMaker read permissions needed when L4 connector invokes hot-reader.

**Fix:** Added `aws_iam_role_policy.l3_twinmaker` with `iottwinmaker:GetEntity` and `iottwinmaker:GetWorkspace`.

**File:** `src/terraform/aws_storage.tf`

---

### 3. Step Functions IAM Policy Fix (AI-0204-3b0e)

**Problem:** Step Function failed with `AccessDeniedException` invoking `high-temperature-callback`

**Root Cause:** `l2_sfn_lambda` policy only granted invoke on `event-checker`, not on event action Lambdas.

**Fix:** Used `concat()` to include all `event_action` Lambda ARNs in the Resource list.

**File:** `src/terraform/aws_compute.tf`

---

### 4. CloudWatch Log Polling (AI-0204-3b0e)

**Problem:** Tests 13, 14, 16 failed due to CloudWatch log indexing delay (~30-60s).

**Fix:** Added active polling (12 attempts × 5s) to all CloudWatch-based log assertions.

**File:** `tests/e2e/multicloud/_base_scenario.py`

---

### 5. CloudWatch Filter Pattern Syntax (AI-0204-3b0e)

**Problem:** `filterPattern="Hello from Event-Checker"` returned 0 results.

**Root Cause:** CloudWatch filter patterns need double quotes for exact phrase matching.

**Fix:** `filterPattern='"Hello from Event-Checker"'`

**File:** `tests/e2e/multicloud/_base_scenario.py`

---

### 6. TwinMaker Response Format Fix (AI-0204-3b0e)

**Problem:** `ConnectorFailureException: PropertyValue missed timestamp or time property` + `expecting propertyValues field to be set`

**Root Cause:** Hot-reader's `_query_dynamodb()` used `item["id"]` (composite `device_timestamp`) instead of `item["timestamp"]` (ISO 8601) for the `time` field. Also crashed with `KeyError` when a requested property was missing from a DynamoDB record.

**Fix:** Changed `time` to use `item.get("timestamp", "")` and added `if property_name not in item: continue`.

**File:** `src/providers/aws/lambda_functions/hot-reader/lambda_function.py`

---

## Fixes Applied (Feb 2)

### 1. AWS Hot-Reader DecimalEncoder Fix (AI-0202-fee9)

**Problem:** `Object of type Decimal is not JSON serializable`

**Root Cause:** AWS DynamoDB stores numbers as `Decimal`. The hot-reader's `json.dumps()` couldn't serialize `Decimal` back to JSON.

**Fix:**
```python
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)
```

**File:** `src/providers/aws/lambda_functions/hot-reader/lambda_function.py`

---

### 2. Test Timeout Increase (AI-0202-fee9)

**Problem:** Data arrived ~7 minutes after IoT message sent due to cold start chain.

**Fix:** `max_retries = 90` → `max_retries = 300` (180s → 600s)

**File:** `tests/e2e/multicloud/_base_scenario.py`

---

### 3. ADT Pusher JSON Patch Fix (AI-0201-9886)

**Problem:** `(JsonPatchInvalid) lastTemperature does not exist on component`

**Root Cause:** Used `"op": "replace"` which requires property to exist. First telemetry update always failed.

**Fix:** `"op": "replace"` → `"op": "add"` (works as upsert)

**File:** `src/providers/azure/azure_functions/_shared/adt_helper.py`

---

### 4. GCP Dispatcher Pub/Sub Base64 Fix (AI-0202-f1ac)

**Problem:** `'device_id' missing in event`

**Root Cause:** GCP Pub/Sub via Eventarc wraps messages in CloudEvents envelope with base64-encoded data. Dispatcher was normalizing wrapper instead of payload.

**Fix:**
```python
def _extract_pubsub_payload(envelope: dict) -> dict:
    if "message" in envelope and "data" in envelope.get("message", {}):
        encoded = envelope["message"]["data"]
        decoded = base64.b64decode(encoded).decode("utf-8")
        return json.loads(decoded)
    return envelope
```

**File:** `src/providers/gcp/cloud_functions/dispatcher/main.py`

---

## Fixes Applied (Jan 30)

### TwinMaker Data Connector Fixes

1. **GCP URL Detection** - Added `cloudfunctions.net` pattern detection
2. **Query/Response Format** - Added GCP-specific query translation and response transformation
3. **Timestamp Format** - Added epoch → ISO8601 conversion

**File:** `aws/lambda_functions/digital-twin-data-connector/lambda_function.py`

---

## Unit Tests

| Test File | Tests | Status |
|-----------|-------|--------|
| `tests/unit/aws/test_data_connector.py` | 11 | ✅ Pass |
| `tests/unit/shared/test_normalize.py` | 13 | ✅ Pass |
| `tests/unit/azure/test_adt_helper.py` | Multiple | ✅ Pass |

---

## Notes

Full investigation logs saved to:
```
tests/e2e/multicloud/.build/cloud_logs_investigation.txt
```
