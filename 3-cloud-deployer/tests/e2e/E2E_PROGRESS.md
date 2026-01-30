# E2E Test Progress & Status

**Last Updated:** 2026-01-29 20:22  
**Cloud Log Investigation:** 2026-01-29 19:22 UTC

---

## Summary

| Scenario | test_08 | Full Dataflow | Errors Found |
|----------|---------|---------------|--------------|
| **AWS→GCP** | ✅ PASS | ✅ **YES** | None |
| Azure→AWS | ❌ FAIL | ❌ No | 2 errors |

---

## ✅ AWS→GCP: VERIFIED PASS

**Cloud Logs (Jan 28 23:23):**
- `sc-aws-gcp-l1-dispatcher`: ✅ Dispatch successful
- `sc-aws-gcp-connector`: ✅ 9.4s invocation, completed successfully

**No errors found in any Lambda** - dataflow confirmed working.

---

## ❌ Azure→AWS: TWO ROOT CAUSES

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

## Issues Preventing Full Log Check

| Provider | Issue |
|----------|-------|
| GCP | `CloudFunctionsServiceClient.list_functions()` API error |
| Azure | Terraform state not found in Docker container |

---

## Detailed Log File

Full investigation saved to:
```
tests/e2e/multicloud/.build/cloud_logs_investigation.txt
```
