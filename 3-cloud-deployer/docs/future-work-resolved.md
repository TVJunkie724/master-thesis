# Resolved Future Work Items

This document contains completed features and improvements that were previously tracked in `future-work.md`.

---

## 1. End-to-End Testing

> [!NOTE]
> Resolved December 2025.

### Status: ✅ Implemented

E2E test suites now exist for all major deployment scenarios:

| Cloud | Test Files |
|-------|-----------|
| AWS | `test_aws_terraform_e2e.py`, `test_aws_lambda_zip_e2e.py` |
| Azure | `test_azure_terraform_e2e.py`, `test_azure_single_cloud_e2e.py`, `test_azure_user_functions_e2e.py` |
| GCP | `test_gcp_terraform_e2e.py`, `test_gcp_function_zip_e2e.py` |
| Multi-cloud | `test_multicloud_e2e.py` |

Tests are run via `tests/e2e/run_e2e_test.py` helper script.

---

## 2. GCP Implementation

> [!NOTE]
> Resolved December 2025. GCP is now fully implemented, not a stub.

### Status: ✅ Fully Implemented

**Provider Implementation:**
- `src/providers/gcp/provider.py` - Full CloudProvider protocol implementation
- `src/providers/gcp/naming.py` - Resource naming utilities
- `src/api/gcp_credentials_checker.py` - Credentials validation

**Cloud Functions (18+ functions):**
- L0 Glue: `ingestion`, `hot-writer`, `cold-writer`, `archive-writer`
- L1 IoT: `dispatcher`
- L2 Compute: `persister`, `connector`, `event-checker`, `processor_wrapper`
- L2 User Functions: `processor` (per-device), `event_action`, `event_feedback`
- L3 Storage: `hot-reader`, `hot-to-cold-mover`  
- L4: `digital-twin-data-connector`

**Terraform Resources:**
- `gcp_iot.tf` - Pub/Sub topics and dispatcher
- `gcp_compute.tf` - All compute functions including user functions
- `gcp_storage.tf` - Firestore, Cloud Storage, movers
- `gcp_glue.tf` - Cross-layer glue functions
- Full multi-cloud environment variable support

---

## 12. EventGrid Subscription Deployment Order

> [!NOTE]
> Resolved November 2024.

### Status: ✅ Resolved

**Issue:** EventGrid subscription referenced function endpoints before functions were deployed.

**Solution:** Used Terraform's `zip_deploy_file` attribute:
1. `tfvars_generator.py` pre-builds function ZIPs
2. ZIP paths passed as terraform variables (`azure_l1_zip_path`, etc.)
3. Each `azurerm_linux_function_app` uses `zip_deploy_file`
4. Function code exists before EventGrid subscription is created

---

## 13. Azure Managed Grafana Version Issue

> [!NOTE]
> Resolved November 2024.

### Status: ✅ Resolved

**Issue:** Azure only supports v11 for Standard SKU, but Terraform provider 3.x only accepted v9/v10.

**Solution:**
1. Upgraded AzureRM provider from `~> 3.85` to `~> 4.0`
2. Changed `grafana_major_version` to `"11"`
3. Updated provider registration syntax

---

## 14. AWS User Functions Terraform Implementation

> [!NOTE]
> Resolved December 2025.

### Status: ✅ Implemented

**AWS Lambda resources now in `aws_compute.tf`:**
- `aws_lambda_function.processor_wrapper` - Routes to user processors
- `aws_lambda_function.user_processor` - Per-device processors via `for_each`
- `event_feedback_wrapper` Lambda function exists in `src/providers/aws/lambda_functions/`

**Variables in `variables.tf`:**
- `aws_processors` - List of processor configurations
- `aws_event_feedback_enabled` / `aws_event_feedback_zip_path`

---

## 15. GCP L2 Compute Layer Implementation

> [!NOTE]
> Resolved December 2025.

### Status: ✅ Fully Implemented

All previously marked "gaps" are now complete:

| Component | Status |
|-----------|--------|
| User Functions Cloud Function | ✅ `google_cloudfunctions2_function.processor_wrapper` |
| Per-device Processors | ✅ `google_cloudfunctions2_function.processor` with `for_each` |
| Event Actions | ✅ `google_cloudfunctions2_function.event_action` |
| Event Feedback | ✅ `google_cloudfunctions2_function.event_feedback` |
| Package Builder | ✅ GCP support in `package_builder.py` |

---

## 16. Multi-Cloud Environment Variables Gap

> [!NOTE]
> Resolved December 2024.

### Status: ✅ Implemented

All multi-cloud environment variables are now in Terraform files:

| Env Variable | Function | Condition |
|-------------|----------|-----------|
| `REMOTE_INGESTION_URL` | Connector (L1) | L1 ≠ L2 |
| `REMOTE_WRITER_URL` | Persister (L2) | L2 ≠ L3 |
| `REMOTE_ADT_PUSHER_URL` | Persister (L2) | L2 ≠ L4 (Azure ADT) |
| `REMOTE_COLD_WRITER_URL` | Hot-to-Cold Mover (L3) | L3 Hot ≠ L3 Cold |
| `REMOTE_ARCHIVE_WRITER_URL` | Cold-to-Archive Mover (L3) | L3 Cold ≠ L3 Archive |
| `REMOTE_HOT_READER_URL` | DT Data Connector (L4) | L4 ≠ L3 |
| `INTER_CLOUD_TOKEN` | All above | Any multi-cloud |

| Provider | Status |
|----------|--------|
| Azure | ✅ Implemented |
| AWS | ✅ Implemented |
| GCP | ✅ Implemented |
