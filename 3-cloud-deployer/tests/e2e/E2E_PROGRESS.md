# E2E Test Progress & Status

**Last Updated:** 2026-02-02 09:45  
**ADT Telemetry Fix Session:** AI-0201-9886  
**TwinMaker Fix Session:** AI-0130-5dda

---

## 🔜 Next Steps (Feb 2)

1. ✅ **AWS→Azure PASSING** - All 13 tests pass after ADT Pusher fix
2. **Verify other ADT scenarios** - Azure→GCP, GCP→Azure should also pass now
3. **Investigate test_08 hot storage failure** - Check AWS Lambda logs for `l0-hot-writer` (affects L3-Hot=AWS scenarios)

---

## Summary (All 6 Scenarios)

| Scenario | Last Run | Tests Passed | Tests Failed | Tests Skipped | Result |
|----------|----------|--------------|--------------|---------------|--------|
| **AWS→GCP** | Jan 31 (01:11) | 13 | 0 | 2 | ✅ **PASS** |
| **AWS→Azure** | Feb 2 (08:35) | 13 | 0 | 2 | ✅ **PASS** |
| **Azure→AWS** | Jan 31 (00:29) | 13 | 0 | 2 | ✅ **PASS** |
| **Azure→GCP** | Jan 31 (01:39) | 11 | 2 | 2 | ❌ FAIL |
| **GCP→AWS** | Jan 31 (01:45) | 11 | 1 | 3 | ❌ FAIL |
| **GCP→Azure** | Jan 31 (01:45) | 9 | 3 | 3 | ❌ FAIL |

### AWS→Azure Latest Run (Feb 2, 08:35 → 08:46)
- **Duration**: 10m 21s
- **Result**: `13 passed, 2 skipped, 0 failed` ✅
- **Key tests passing**:
  - `test_08_verify_hot_storage` ✅ (data found in GCP Firestore)
  - `test_11b_adt_twin_telemetry` ✅ (`lastTemperature: 42.5` verified in ADT twin)
  - `test_12_azure_functions_deployed` ✅

---

## ✅ Fixes Applied (Feb 2)

### ADT Pusher JSON Patch Fix (AI-0201-9886)

**Problem:** `test_11b_adt_twin_telemetry` failed with:
```
(JsonPatchInvalid) lastTemperature does not exist on component
```

**Root Cause:** The ADT Pusher used `"op": "replace"` in JSON Patch, which requires the property to already exist. Since twins are created without initial property values, the first telemetry update always failed.

**Fix Applied:**
```python
# Before (adt_helper.py line 122)
patch.append({"op": "replace", "path": f"/{prop_name}", "value": value})

# After
patch.append({"op": "add", "path": f"/{prop_name}", "value": value})
```

The `"add"` operation works as upsert: creates if missing, updates if exists.

**File:** `src/providers/azure/azure_functions/_shared/adt_helper.py`

---

## ❌ Remaining Failures (Feb 2)

### Issue #1: `test_08_verify_hot_storage` - L3-Hot AWS Data Flow

**Affected:** Azure→GCP, GCP→AWS, GCP→Azure (all have L3-Hot = AWS DynamoDB)

**Error:** `[DATAFLOW CRITICAL] No data found in hot storage after 180s.`

**Pattern:** Fails when L3-Hot is AWS DynamoDB. Passes when L3-Hot is GCP Firestore.

**Next Steps:** Check AWS Lambda logs for `l0-hot-writer` and `l3-hot-reader`.

---

### Issue #2: `test_11b_adt_twin_telemetry` - FIXED ✅

**Status:** Fixed on Feb 2 - see "Fixes Applied" above.

**Scenarios to verify:** Azure→GCP, GCP→Azure should now pass with the same fix.


---

### Issue #3: `test_12_azure_functions_deployed` - Naming Mismatch

**Affected:** AWS→Azure, GCP→Azure (L2 = Azure)

**Error:**
```
L2 Processing (sc2-aws-azure-l2-functions): Missing functions 
['processor_wrapper', 'event_feedback_wrapper'], got 
['event-checker', 'event-feedback', 'persister', 'processor']
```

**Root Cause:** **Test logic bug** - Test uses `f.name` from registry but Azure functions register with different names via `@bp.function_name()`:

| Registry Name | Azure Deployed Name | Source |
|---------------|---------------------|--------|
| `processor_wrapper` | `processor` | `@bp.function_name(name="processor")` |
| `event_feedback_wrapper` | `event-feedback` | `@bp.function_name(name="event-feedback")` |

**Fix:** Added `_registry_to_azure_name()` helper in `_base_scenario.py` ✅ (Jan 31 02:23)


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

## ✅ AWS→Azure: Previous Run (Jan 25)

- All 12 tests passed
- Duration: 19m 56s
- **Note:** Current runs (Jan 31) have 2 failures - see "Current Failures" above

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

## ⏳ Tested Scenarios Status

| Scenario | Status | Key Issues |
|----------|--------|------------|
| **AWS→GCP** | ✅ PASS | None |
| **AWS→Azure** | ❌ FAIL | test_11b, test_12 (fix applied) |
| **Azure→AWS** | ✅ PASS | None |
| **Azure→GCP** | ❌ FAIL | test_08, test_11b |
| **GCP→AWS** | ❌ FAIL | test_08 |
| **GCP→Azure** | ❌ FAIL | test_08, test_11b, test_12 (fix applied) |

---

## Notes

Full investigation logs saved to:
```
tests/e2e/multicloud/.build/cloud_logs_investigation.txt
```

---

## Detailed Log File

Full investigation saved to:
```
tests/e2e/multicloud/.build/cloud_logs_investigation.txt
```
