# Multi-Cloud Implementation Gap Analysis

## Feature Comparison by Provider

| Feature | Azure | AWS | GCP |
|---------|-------|-----|-----|
| Build Settings | ✅ ENABLE_ORYX_BUILD | N/A (pre-packaged) | ✅ Cloud Build auto |
| System Functions | ✅ Terraform ZIP | ✅ Terraform filename | ✅ Terraform ZIP |
| User Functions | ✅ Kudu deploy | ✅ SDK deploy | ❌ Not implemented |
| Processor Wrapper | ✅ | ✅ | ❌ Not implemented |
| IoT Simulator Config | ✅ | ✅ | ❌ Not implemented |
| IoT Device Registration | ✅ SDK | ✅ SDK | ❌ (uses Pub/Sub) |
| Optional Resources (count) | ✅ | ✅ | ❌ L2 not full |
| `REMOTE_WRITER_URL` | ❌ **Gap** | ❌ **Gap** | ❌ Gap |
| `INTER_CLOUD_TOKEN` | ✅ Set | ❌ **Gap** | ❌ Gap |

---

## ✅ Azure & AWS: Verified Implementations

| Feature | Azure | AWS | Location |
|---------|-------|-----|----------|
| System Functions | Terraform ZIP | Terraform filename | `*_compute.tf` |
| User Functions | Kudu deploy | SDK deploy | `*_deployer.py` |
| Processor Wrapper | ✅ | ✅ | `package_builder.py` |
| IoT Simulator Config | ✅ | ✅ | `layer_1_iot.py` |

---

## ⚠️ GCP: Missing Features

| Gap | Status | Notes |
|-----|--------|-------|
| L2/L4/L5 layers | ❌ | Not implemented (Terraform only for L0/L1/L3) |
| User functions | ❌ | No SDK deployment for user-customizable functions |
| IoT simulator config | ❌ | No `config_generated.json` (uses Pub/Sub, not IoT Core) |
| Optional resources | ❌ | No `use_event_checking` / `trigger_notification_workflow` |
| `REMOTE_WRITER_URL` | ❌ | Not in GCP persister env vars |

> **Note:** GCP uses Pub/Sub instead of IoT Hub/Core. Device registration is different.

---

## ⚠️ Multi-Cloud Gaps (ALL Providers)

### Complete Env Var List (All Missing in Terraform!)

| Env Variable | Used By | Condition | Azure | AWS | GCP |
|-------------|---------|-----------|-------|-----|-----|
| `REMOTE_INGESTION_URL` | Connector (L1) | L1≠L2 | ❌ | ❌ | ❌ |
| `REMOTE_WRITER_URL` | Persister (L2) | L2≠L3 | ❌ | ❌ | ❌ |
| `REMOTE_COLD_WRITER_URL` | Hot-to-Cold Mover | Hot≠Cold | ❌ | ❌ | ❌ |
| `REMOTE_ARCHIVE_WRITER_URL` | Cold-to-Archive Mover | Cold≠Archive | ❌ | ❌ | ❌ |
| `REMOTE_HOT_READER_URL` | DT Data Connector (L4) | L4≠L3 | ❌ | ❌ | ❌ |
| `INTER_CLOUD_TOKEN` | All above | Any multi-cloud | ✅ | ❌ | ❌ |

### Logic App Trigger URL (Azure only)

| Env Variable | Used By | Status |
|-------------|---------|--------|
| `LOGIC_APP_TRIGGER_URL` | Event Checker (L2) | ❌ Missing |

**Solution:** Add to `azure_compute.tf`:
```hcl
LOGIC_APP_TRIGGER_URL = var.trigger_notification_workflow ? azurerm_logic_app_trigger_http_request.event_trigger[0].callback_url : ""
```

---

## Next Steps

1. ✅ Terraform settings fixed (`ENABLE_ORYX_BUILD`)
2. ✅ E2E ZIP deploy test passes
3. ⏳ Run full Azure E2E test
4. 📋 Add `REMOTE_WRITER_URL` to Terraform app_settings (if multi-cloud needed)
5. 📋 Add `LOGIC_APP_TRIGGER_URL` to Terraform app_settings (if workflow enabled)



