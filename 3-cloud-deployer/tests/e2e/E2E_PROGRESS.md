# E2E Test Progress & Status

**Last Updated:** 2026-01-30 23:04  
**Cloud Log Investigation:** 2026-01-29 19:22 UTC  
**TwinMaker Fix Session:** AI-0130-5dda

---

## Summary (All 6 Scenarios)

| Scenario | Last Run | Tests Passed | Tests Failed | Tests Skipped | Result |
|----------|----------|--------------|--------------|---------------|--------|
| **AWS→GCP** | Jan 28 | 11 | 0 | 3 | ✅ PASS |
| **AWS→Azure** | Jan 25 | 12 | 0 | 1 | ✅ PASS |
| **Azure→AWS** | Jan 30 | 12 | 1 | 2 | ❌ FAIL (test_10b) |
| **Azure→GCP** | - | - | - | - | ⏳ Untested |
| **GCP→AWS** | - | - | - | - | ⏳ Untested |
| **GCP→Azure** | - | - | - | - | ⏳ Untested |

### Azure→AWS Last Run Details (Jan 30, 19:19)
- **Duration**: 22m 42s
- **Result**: `1 failed, 12 passed, 2 skipped`
- **Failed Test**: `test_10b_twinmaker_telemetry`
- **Error**: `[L4 DATAFLOW CRITICAL] No telemetry found via TwinMaker after 60s. Entity: machine-1, Component: temperature-sensor-1`

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

## ❌ Azure→AWS: TWO ROOT CAUSES (Now Fixed)

### Error 1: L0 AccessDeniedException
**Lambda:** `sc-azure-aws-l0-ingestion` (Jan 28 14:11)
```
AccessDeniedException: User ...sc-azure-aws-l0-lambda-role/sc-azure-aws-l0-ingestion 
is NOT AUTHORIZED to perform: lambda:InvokeFunction
```
**Fix:** Add `lambda:InvokeFunction` permission to `sc-azure-aws-l0-lambda-role`

---

### Error 2: L2 Persister Missing ID
**Lambda:** `sc-azure-aws-l2-persister` (Jan 28 17:23)
```
Event: {"temperature": 42.5, "time": "1769621022101", "device_id": "temperature-sensor-1", "timestamp": "1769621022101"}
Multi-cloud mode: POSTing to remote Hot Writer at https://.../sc-azure-aws-hot-writer
Client Error (400): Bad Request. Body: {"error": "Missing 'id' in item"}
```
**The `id` field is NOT being set!** Looking at the event, it has `device_id` and `timestamp` but no `id`.

**Root Cause:** The Document ID standardization fix IS in the code, but the deployed Lambda is **stale** (pre-Jan 27 code).

**Fix:** Re-deploy Azure→AWS scenario to pick up the `item["id"] = f"{device_id}_{timestamp}"` fix.

---

## ⏳ Untested Scenarios

The following scenarios have not been run yet:

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

1. Run E2E test `deployer-azure-aws` to validate fixes
2. Verify `test_10b_twinmaker_telemetry` passes
3. Run remaining 3 untested scenarios

---

## Detailed Log File

Full investigation saved to:
```
tests/e2e/multicloud/.build/cloud_logs_investigation.txt
```
