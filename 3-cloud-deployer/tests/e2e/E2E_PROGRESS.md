# E2E Test Progress & Status

**Last Updated:** 2026-01-30 23:57  
**Cloud Log Investigation:** 2026-01-29 19:22 UTC  
**TwinMaker Fix Session:** AI-0130-5dda

---

## Summary (All 6 Scenarios)

| Scenario | Last Run | Tests Passed | Tests Failed | Tests Skipped | Result |
|----------|----------|--------------|--------------|---------------|--------|
| **AWS→GCP** | Jan 28 | 11 | 0 | 3 | ✅ PASS |
| **AWS→Azure** | Jan 25 | 12 | 0 | 1 | ✅ PASS |
| **Azure→AWS** | Jan 30 (22:41) | 12 | 1 | 2 | ⚠️ PARTIAL |
| **Azure→GCP** | - | - | - | - | ⏳ Untested |
| **GCP→AWS** | - | - | - | - | ⏳ Untested |
| **GCP→Azure** | - | - | - | - | ⏳ Untested |

### Azure→AWS Latest Run (Jan 30, 22:41 → 22:53)
- **Duration**: 11m 57s
- **Result**: `1 failed, 12 passed, 2 skipped`
- **Failed Test**: `test_10b_twinmaker_telemetry` (TwinMaker → pressure-sensor-1)
- **Passed Test**: `test_08_verify_hot_storage` ✅ (was failing in previous run!)

### Azure→AWS Run Comparison
| Run | test_08 | test_10b | Total |
|-----|---------|----------|-------|
| Jan 30 19:19 | ✅ PASS | ❌ FAIL | 1 failed, 12 passed |
| Jan 30 22:07 | ❌ FAIL | ❌ FAIL | 2 failed, 11 passed |
| Jan 30 22:41 | ✅ PASS | ❌ FAIL | 1 failed, 12 passed |

**Key Finding:** test_08 is **intermittent** (infra timing), test_10b requires fix redeployment.

---

## 🔧 Fixes Applied (Jan 30)

### Issue 1: GCP URL Detection Missing `cloudfunctions.net` (FIXED 23:55)

**Problem:** TwinMaker data connector only detected GCP URLs with `.run.app` pattern.
GCP Cloud Functions Gen2 can use `cloudfunctions.net` URLs (e.g., `europe-west1-project.cloudfunctions.net/...`).
This caused the connector to bypass GCP-specific query translation and response transformation.

**Symptoms:**
- Connector printed "Azure mode" when calling GCP hot-reader
- Raw `{"items": [...]}` response was returned instead of `{"propertyValues": [...]}`
- TwinMaker threw `ConnectorFailureException: expecting propertyValues field to be set`

**Fix Applied:**
```python
# Before: Only detected Cloud Run direct URLs
return ".run.app" in REMOTE_READER_URL

# After: Detects both URL patterns
return ".run.app" in REMOTE_READER_URL or "cloudfunctions.net" in REMOTE_READER_URL
```

**Verification:** Manually updated Lambda and verified TwinMaker successfully retrieved data:
```
GCP mode: Querying https://...cloudfunctions.net/...?device_id=temperature-sensor-1
Transformed to TwinMaker format: {"propertyValues": [...]}
```

**File:** `aws/lambda_functions/digital-twin-data-connector/lambda_function.py`

---

### Issue 2: TwinMaker ↔ GCP Hot-Reader Query/Response Format (Jan 30 morning)

**Problem:** AWS TwinMaker data connector couldn't communicate with GCP hot-reader due to:
1. Query format mismatch (JSON body vs URL params)
2. Response format mismatch (`items` vs `propertyValues`)

**Fix Applied:**
- Added `_is_gcp_reader()` - Detects GCP Gen2 URLs
- Added `_build_gcp_query_url()` - Translates TwinMaker query to URL params
- Added `_transform_gcp_to_twinmaker()` - Converts GCP response to TwinMaker format

**File:** `aws/lambda_functions/digital-twin-data-connector/lambda_function.py`

---

### Issue 3: Timestamp Format Mismatch

**Problem:** Test payloads use epoch milliseconds (`1738267800000`), but TwinMaker queries with ISO8601 (`2026-01-30T18:00:00Z`). String comparison failed.

**Fix Applied:**
- Added `_is_iso8601_like()` - Detects ISO8601 format
- Added `_convert_to_iso8601()` - Converts epoch → ISO8601

**Files:** 
- `aws/_shared/normalize.py`
- `azure/_shared/normalize.py`
- `gcp/_shared/normalize.py`


---

## Unit Tests Added

| Test File | Tests | Status |
|-----------|-------|--------|
| `tests/unit/aws/test_data_connector.py` | 11 | ✅ Pass |
| `tests/unit/shared/test_normalize.py` | 13 | ✅ Pass |

**Total: 24 unit tests passing**

---

## ✅ AWS→GCP: VERIFIED PASS (Jan 28)

**Cloud Logs (Jan 28 23:23):**
- `sc-aws-gcp-l1-dispatcher`: ✅ Dispatch successful
- `sc-aws-gcp-connector`: ✅ 9.4s invocation, completed successfully

**No errors found in any Lambda** - dataflow confirmed working.

---

## ✅ AWS→Azure: VERIFIED PASS (Jan 25)

- All 12 tests passed
- Duration: 19m 56s

---

## ❌ Azure→AWS: ROOT CAUSES

### Error 1: L0 AccessDeniedException (Fixed in Terraform)
**Lambda:** `sc-azure-aws-l0-ingestion` (Jan 28 14:11)
```
AccessDeniedException: User ...sc-azure-aws-l0-lambda-role/sc-azure-aws-l0-ingestion 
is NOT AUTHORIZED to perform: lambda:InvokeFunction
```
**Fix:** `lambda:InvokeFunction` permission added to L0 role.

---

### Error 2: L2 Persister Missing ID (Fixed Jan 27)
**Lambda:** `sc-azure-aws-l2-persister` (Jan 28 17:23)
```
Client Error (400): Bad Request. Body: {"error": "Missing 'id' in item"}
```
**Fix:** `item["id"] = f"{device_id}_{timestamp}"` added.

---

### Error 3: test_08 Intermittent Failure (NEW)
Data sometimes doesn't reach GCP Firestore within 120s timeout. Hot reader returns 200 with empty results.

**Possible causes:**
- Azure → AWS L1 dispatcher not triggering
- AWS → GCP persister failing silently
- GCP Firestore write timing

---

## ⏳ Untested Scenarios

| Scenario | Test File | Notes |
|----------|-----------|-------|
| **Azure→GCP** | `test_scenario_azure_gcp.py` | L1=Azure, L2=GCP |
| **GCP→AWS** | `test_scenario_gcp_aws.py` | L1=GCP, L2=AWS |
| **GCP→Azure** | `test_scenario_gcp_azure.py` | L1=GCP, L2=Azure |

---

## Issues Preventing Full Log Check

| Provider | Issue |
|----------|-------|
| GCP | `CloudFunctionsServiceClient.list_functions()` API error |
| Azure | Terraform state not found in Docker container |

---

## Next Steps

1. Investigate intermittent test_08 failure (data flow Azure→GCP)
2. Check cloud logs for the failing run
3. Run remaining 3 untested scenarios

---

## Detailed Log File

Full investigation saved to:
```
tests/e2e/multicloud/.build/cloud_logs_investigation.txt
```
