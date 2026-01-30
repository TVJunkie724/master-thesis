# E2E Test Progress & Status

**Last Updated:** 2026-01-30 23:35  
**Cloud Log Investigation:** 2026-01-29 19:22 UTC  
**TwinMaker Fix Session:** AI-0130-5dda

---

## Summary (All 6 Scenarios)

| Scenario | Last Run | Tests Passed | Tests Failed | Tests Skipped | Result |
|----------|----------|--------------|--------------|---------------|--------|
| **AWS→GCP** | Jan 28 | 11 | 0 | 3 | ✅ PASS |
| **AWS→Azure** | Jan 25 | 12 | 0 | 1 | ✅ PASS |
| **Azure→AWS** | Jan 30 (23:31) | 11 | 2 | 2 | ❌ FAIL |
| **Azure→GCP** | - | - | - | - | ⏳ Untested |
| **GCP→AWS** | - | - | - | - | ⏳ Untested |
| **GCP→Azure** | - | - | - | - | ⏳ Untested |

### Azure→AWS Last Run Details (Jan 30, 22:07 → 22:31)
- **Duration**: 24m 21s
- **Result**: `2 failed, 11 passed, 2 skipped`
- **Failed Tests**: 
  1. `test_08_verify_hot_storage` - No data in GCP Firestore after 120s (Status 200, empty)
  2. `test_10b_twinmaker_telemetry` - No telemetry via TwinMaker after 60s

### Azure→AWS Run Comparison
| Run | test_08 | test_10b | Total |
|-----|---------|----------|-------|
| Jan 30 19:19 | ✅ PASS | ❌ FAIL | 1 failed, 12 passed |
| Jan 30 22:07 | ❌ FAIL | ❌ FAIL | 2 failed, 11 passed |

**Key Observation:** test_08 passed in the earlier run but failed in the latest run. This indicates **intermittent data flow issues** in the Azure → AWS → GCP pipeline.

**Investigation Notes:**
- GCP hot-reader was NOT changed in this session
- Our changes (TwinMaker connector fix, timestamp normalization) require **redeployment** to take effect
- The AWS persister correctly adds `id` field (code confirmed)
- test_08 queries by `device_id` only (no timestamp filtering), so timestamp format is not the issue for test_08

---

## 🔧 Fixes Applied (Jan 30)

### Issue 1: TwinMaker ↔ GCP Hot-Reader Incompatibility

**Problem:** AWS TwinMaker data connector couldn't communicate with GCP hot-reader due to:
1. Query format mismatch (JSON body vs URL params)
2. Response format mismatch (`items` vs `propertyValues`)

**Fix Applied:**
- Added `_is_gcp_reader()` - Detects GCP Gen2 URLs (`.run.app`)
- Added `_build_gcp_query_url()` - Translates TwinMaker query to URL params
- Added `_transform_gcp_to_twinmaker()` - Converts GCP response to TwinMaker format

**File:** `aws/lambda_functions/digital-twin-data-connector/lambda_function.py`

---

### Issue 2: Timestamp Format Mismatch

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
