# Azure Implementation Gap Analysis

Comparison of deprecated (SDK-only) vs current (Terraform + Python SDK hybrid) Azure implementation.

## Summary

| Category | Deprecated | Hybrid | Status |
|----------|------------|--------|--------|
| Function App Settings | ❌ Wrong settings | ✅ Fixed | **Now Correct** |
| System Functions (L0-L3) | SDK deploy | Terraform zip_deploy | ✅ Implemented |
| User Functions | Per-device deploy | Combined ZIP | ✅ Implemented |
| Processor Wrapper Merging | ✅ | ✅ `_add_processor_to_combined_zip` | ✅ Implemented |
| App Settings Configuration | ✅ Dynamic | ⚠️ Static in Terraform | Partial |
| IoT Device Registration | ✅ | ✅ via `register_azure_iot_devices` | ✅ Implemented |
| DTDL Model Upload | ✅ | ✅ via `upload_dtdl_models` | ✅ Implemented |
| Grafana Config | ✅ | ✅ via `configure_azure_grafana` | ✅ Implemented |

---

## Implemented in Hybrid

### 1. Terraform-Based Deployment
- L0-L3 system functions deployed via `zip_deploy_file`
- App settings configured in Terraform (including ENABLE_ORYX_BUILD fix)
- Infrastructure + functions in single `terraform apply`

### 2. User Functions (`azure_deployer.py`)
- Combined user functions into single ZIP via `build_combined_user_package`
- Processor wrapper merging via `_add_processor_to_combined_zip`
- Deployed to separate `user` Function App via Kudu

### 3. Post-Terraform Steps (`deployer_strategy.py`)
- `_deploy_azure_function_code` → User functions via Kudu
- `upload_dtdl_models` → Azure Digital Twins
- `register_azure_iot_devices` → IoT Hub device registration
- `configure_azure_grafana` → Grafana datasource config

---

## Gaps to Address

### 1. Dynamic App Settings (Medium Priority)
**Deprecated approach:** SDK updates app settings dynamically based on:
- Multi-cloud connections (REMOTE_WRITER_URL, INTER_CLOUD_TOKEN)
- ADT Pusher URL after L4 deployment
- Logic App trigger URL after creation

**Current hybrid approach:** Static settings in Terraform.

**Solution:** Add post-Terraform SDK calls to update dynamic app settings.

---

### 2. Per-Device Processor Functions (Low Priority - Design Change)
**Deprecated:** One processor function per IoT device (`{device_id}-processor`)

**Current:** All processors in single `user` Function App

**Status:** This is a design simplification, not a regression, unless per-device isolation is required.

---

### 3. Logic App Trigger URL Update (Medium Priority)
**Deprecated:** `_update_logic_app_url()` updates Event Checker with Logic App trigger URL.

**Current:** Logic App is in Terraform but URL not propagated to L2 app settings.

**Solution:** Add post-deployment step to update `LOGIC_APP_TRIGGER_URL` in L2 app settings.

---

## No Action Needed

| Feature | Reason |
|---------|--------|
| Processor Wrapper | Already implemented in `package_builder.py` |
| SCM Basic Auth | Enabled in E2E test; Terraform may need `scm_type` |
| Function Sync Wait | Terraform `time_sleep` handles this |

---

## Next Steps

1. ✅ Terraform app settings fixed (ENABLE_ORYX_BUILD, no WEBSITE_RUN_FROM_PACKAGE)
2. ✅ E2E ZIP deploy test passes
3. [ ] Run full Azure E2E test with all layers
4. [ ] Verify dynamic app settings (multi-cloud connections) if needed
