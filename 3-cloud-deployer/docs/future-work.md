# Future Work

This document tracks planned improvements and features for the Digital Twin Multi-Cloud Deployer.

---

## 1. End-to-End Testing

> [!IMPORTANT]
> E2E tests are critical for ensuring the complete deployment pipeline works correctly.

### Status: Not Implemented

### Tasks

- [ ] Create E2E test suite for AWS single-cloud deployment
- [ ] Create E2E test suite for Azure single-cloud deployment
- [ ] Create E2E test suite for AWS↔Azure hybrid combinations
- [ ] Test all provider combination matrix (see below)

### Provider Combination Matrix (All Need E2E Tests)

| L1 | L2 | L3 Hot | L3 Cold | L3 Archive | L4 | L5 |
|----|----|----|----|----|----|----|
| AWS | AWS | AWS | AWS | AWS | AWS | AWS |
| Azure | Azure | Azure | Azure | Azure | Azure | Azure |
| AWS | Azure | Azure | Azure | Azure | Azure | Azure |
| Azure | AWS | AWS | AWS | AWS | AWS | AWS |
| AWS | AWS | Azure | Azure | Azure | Azure | Azure |
| Azure | Azure | AWS | AWS | AWS | AWS | AWS |
| AWS | AWS | AWS | Azure | Azure | Azure | Azure |
| AWS | AWS | AWS | AWS | Azure | Azure | Azure |
| Azure | AWS | Azure | AWS | Azure | AWS | Azure |
| ... and more combinations |

---

## 2. GCP Implementation

> [!NOTE]
> GCP is currently a stub implementation. The provider pattern validates but does not deploy.

### Status: Stub Only

### Files to Implement

- `src/providers/gcp/deployer_strategy.py` - All methods raise `NotImplementedError`
- `src/providers/gcp/provider.py` - Minimal stub
- `src/providers/gcp/layers/*.py` - Need to be created

### Documentation to Add

- [ ] `docs-gcp-deployment.html` - Add Setup Layer section
- [ ] `docs-gcp-deployment.html` - Add L0 Glue Layer section
- [ ] `docs-gcp-deployment.html` - Add IAM Permissions section
- [ ] `docs-credentials-gcp.html` - Create new credentials guide page
- [ ] `gcp_credentials_checker.py` - Create credentials validation

### IoT Device Simulator Note

> [!TIP]
> When implementing the IoT device simulator in `/upload/template/`, add support for GCP Pub/Sub:
> - Primary: HTTP REST API (simplest, use Service Account JSON key)
> - Alternative: gRPC (faster, same auth via ADC)
> - MQTT is NOT required for GCP (no native support)

### Architecture Notes

GCP implementation will be **Terraform-only** (no SDK layer deployment):
- Cloud Functions Gen2 via `google_cloudfunctions2_function`
- Pub/Sub for IoT ingestion (HTTP/gRPC, not MQTT)
- Firestore for hot storage
- Cloud Storage lifecycle policies for cold/archive (custom age days like AWS/Azure)

### Future Enhancement: gRPC Migration

> [!NOTE]
> Initial implementation uses HTTP REST for simplicity. Consider gRPC migration for production:

| Aspect | HTTP REST (Current) | gRPC (Future) |
|--------|---------------------|---------------|
| Speed | Baseline | 7x faster |
| Payload | JSON (text) | Protocol Buffers (binary) |
| Auth | Service Account JSON | Same (ADC) |
| Use case | Development, <1k msg/sec | Production, >1k msg/sec |

**When to migrate**: High-throughput IoT scenarios requiring >1000 messages/second.

---

## 3. Deprecated Code Cleanup

### Status: In Progress

### Items to Remove

- [ ] `deploy_all_sdk()` in `src/providers/deployer.py` (deprecated, use Terraform)
- [ ] `destroy_all_sdk()` in `src/providers/deployer.py` (deprecated)
- [ ] GCP stubs if GCP implementation is not prioritized
- [ ] Legacy `provider.naming` method in `src/providers/azure/provider.py`

---

## 4. Azure API Helper Functions

### Status: Partially Missing

### Context

The `src/api/deployment.py` file has helper dispatcher functions that only support AWS:
- `_deploy_hierarchy()` - AWS only (Azure handled by Terraform L4)
- `_destroy_hierarchy()` - AWS only
- `_deploy_event_actions()` - AWS only (Azure handled by Terraform L2)
- `_destroy_event_actions()` - AWS only
- `_deploy_init_values()` - **Needs Azure implementation**

### Clarification

Most of these are already handled by Terraform for Azure. The only one that might need implementation is `_deploy_init_values()` for Azure IoT device initial twin state.

---

## 5. Event Checker Azure Support

### Status: Not Implemented

The event checker redeployment function only supports AWS. Azure support needs implementation.

**File:** `src/providers/deployer.py:162`

```python
raise NotImplementedError("Event checker redeployment only supported for AWS.")
```

---

## 6. Template Processor Cleanup

### Status: Not Implemented

The processor function in `upload/template/*/processors/default_processor/` already uses the correct minimal `process()` signature. However, the built-in default processors at `src/providers/*/default-processor/` contain full boilerplate code.

**Goal:** Ensure consistency - the default processors should only contain a `process(event)` function like the template, with the system wrapper handling the Lambda/Function boilerplate.

**Files:**
- `src/providers/aws/lambda_functions/default-processor/lambda_function.py`
- `src/providers/azure/azure_functions/default-processor/`
- `src/providers/gcp/cloud_functions/default-processor/`

---

## 7. SDK Managed Resource Validation

### Status: Placeholder

### Current Implementation

`check_sdk_managed()` in `status.py` returns placeholder data:
```python
return {
    "status": "not_checked",
    "note": "SDK managed resources require credentials for live checks",
    ...
}
```

### Implementation Required

Use existing `info_l*` functions from provider strategies:
- AWS: `info_l4()` checks TwinMaker entities
- Azure: `info_l4()` checks ADT twins
- Both: `info_l1()` checks IoT devices

---

## 8. Documentation

### Status: Ongoing

- [x] Update architecture docs with Terraform-first approach
- [ ] Document multi-cloud configuration examples
- [ ] Add troubleshooting guide for common deployment issues
- [ ] Create video walkthrough of deployment process

---

## 9. Performance Improvements

### Ideas

- [ ] Parallel Terraform plan/apply for multi-cloud
- [ ] Cache hot path configs for faster status checks
- [ ] Optimize function package building

---

## 10. Security Enhancements

### Ideas

- [ ] Rotate inter-cloud tokens periodically
- [ ] Support Azure Key Vault for credential storage
- [ ] Support AWS Secrets Manager for credential storage
- [ ] Add certificate-based authentication option

---

## 11. Azure Custom Role: Cosmos DB Permission Investigation

### Status: Needs Investigation

### Issue

During E2E testing with the custom "Digital Twin Deployer" role (`docs/references/azure_custom_role.json`), Terraform fails with:

```
AuthorizationFailed: ... Microsoft.DocumentDB/databaseAccounts/read ... or the scope is invalid
```

This occurs **even though** the custom role includes:
- `Microsoft.DocumentDB/databaseAccounts/read` (line 66)
- `Microsoft.DocumentDB/databaseAccounts/listKeys/action` (line 67)
- `*/read` wildcard (line 11)

### Potential Causes

1. **Missing `readMetadata` permission**: Research indicates `Microsoft.DocumentDB/databaseAccounts/readMetadata` may be required, but it's a **dataAction** (not visible in Portal UI for control plane roles)
2. **Student subscription limitations**: Possible restrictions on custom roles or specific permissions
3. **Role propagation timing**: RBAC changes can take 5-30 minutes to propagate

### Workaround

Assign the built-in **Contributor** role alongside the custom role. If Contributor works, the custom role is missing a permission.

### TODO

- [ ] Identify exact minimum permission set for Cosmos DB Terraform operations
- [ ] Document whether `readMetadata` needs to be in `dataActions` section
- [ ] Consider using Azure CLI to update custom role: `az role definition update --role-definition azure_custom_role.json`
- [ ] Update `azure_custom_role.json` once root cause is confirmed

---

## 12. EventGrid Subscription Deployment Order

### Status: ✅ RESOLVED

### Issue

The EventGrid subscription in `azure_iot.tf` references a specific function endpoint:

```hcl
function_id = "${azurerm_linux_function_app.l1[0].id}/functions/dispatcher"
```

This failed with `Resource should pre-exist before attempting this operation` because:
1. **Terraform** creates the function app container (empty shell)
2. **Python** deploys the actual function code **AFTER** Terraform finishes
3. When EventGrid subscription is created, the `dispatcher` function doesn't exist yet

### Solution Implemented

Used Terraform's `zip_deploy_file` attribute to deploy function code during terraform apply:
1. `tfvars_generator.py` now pre-builds function ZIPs using `function_bundler.py`
2. ZIP paths are passed as terraform variables (`azure_l1_zip_path`, etc.)
3. Each `azurerm_linux_function_app` has `zip_deploy_file = var.azure_lX_zip_path`
4. Function code exists before EventGrid subscription is created
5. No more Kudu deployment needed after terraform apply

---

## 13. Azure Managed Grafana Version Issue

### Status: ✅ RESOLVED

### Issue

Azure Managed Grafana deployment failed with:
- `GrafanaMajorVersionNotSupported: version 'X' is not valid for sku type Standard`

**Root cause:** Azure only supports v11 for Standard SKU, but Terraform provider 3.x only accepted v9/v10.

### Solution Implemented

1. Upgraded AzureRM provider from `~> 3.85` to `~> 4.0` in `versions.tf`
2. Changed `grafana_major_version` from `"10"` to `"11"` in `azure_grafana.tf`
3. Replaced deprecated `skip_provider_registration = true` with `resource_provider_registrations = "none"` in `main.tf`

---

## 14. AWS User Functions Terraform Implementation (GCP as well????)

> [!CAUTION]
> HIGH PRIORITY - This feature gap blocks AWS user function deployment.

### Status: Not Implemented

### Issue

AWS Terraform configuration (`aws_compute.tf`) does not include infrastructure for user-customizable functions:
- **Event Actions**: User-defined Lambda functions triggered by event conditions
- **Event Feedback**: Lambda functions for sending responses to IoT devices
- **Processors**: User logic wrappers for data processing

Currently only system functions (Persister, Event Checker) and Step Functions workflow are implemented.

### Required Implementation

1. Add AWS Lambda resources for user functions (similar to Azure's `user-functions` app)
2. Add conditional deployment based on `use_event_checking` and `return_feedback_to_device` flags
3. Implement SDK-based deployment for user function code (already exists for Azure)
4. Integrate with `package_builder.py` for AWS Lambda packaging

### Azure Implementation (Reference)

Azure has:
- `azurerm_linux_function_app.user` - user functions app container
- `build_combined_user_package()` - builds combined ZIP
- `_deploy_user_functions()` - SDK deployment post-Terraform

AWS needs equivalent:
- Lambda functions with `count` conditional on feature flags
- Lambda deployment via package_builder (already has `build_aws_lambda_packages`)

---

## 15. GCP L2 Compute Layer Implementation

> [!CAUTION]
> HIGH PRIORITY - GCP L2 architecture and user functions still missing.

### Status: Partially Implemented

### Completed ✅

- `REMOTE_WRITER_URL` added to `gcp_compute.tf` persister
- `INTER_CLOUD_TOKEN` already present in persister
- Simulator `config_generated.json` via Terraform `local_file` resource in `gcp_iot.tf`
- `iot_devices` variable added to `variables.tf`

### Remaining Gaps ❌

1. **User Functions Cloud Function** - No user-customizable functions (processors, event_actions, event-feedback)
2. **GCP L2 Deployer** - No SDK post-Terraform deployment for user functions (unlike Azure's `azure_deployer.py`)
3. **User Function Terraform Resource** - Need `google_cloudfunctions2_function.user_functions` in `gcp_compute.tf`
4. **Package Builder** - Need GCP support in `package_builder.py` for user function bundling

### Required Implementation

```hcl
# gcp_compute.tf - Add user functions Cloud Function
resource "google_cloudfunctions2_function" "user_functions" {
  count    = local.gcp_l2_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-user-functions"
  location = var.gcp_region
  # ... similar config to processor
}
```

---

## 16. Multi-Cloud Environment Variables Gap

> [!NOTE]
> Phase 1 implemented - all env vars added to Terraform files.

### Status: Implemented ✅

### What Was Done

Multi-cloud environment variables now in all Terraform files.

### Complete List of Multi-Cloud Environment Variables

| Env Variable | Function | Condition |
|-------------|----------|-----------|
| `REMOTE_INGESTION_URL` | Connector (L1) | L1 ≠ L2 |
| `REMOTE_WRITER_URL` | Persister (L2) | L2 ≠ L3 |
| `REMOTE_ADT_PUSHER_URL` | Persister (L2) | L2 ≠ L4 (Azure ADT) |
| `ADT_PUSHER_TOKEN` | Persister (L2) | L2 ≠ L4 (Azure ADT) |
| `REMOTE_COLD_WRITER_URL` | Hot-to-Cold Mover (L3) | L3 Hot ≠ L3 Cold |
| `REMOTE_ARCHIVE_WRITER_URL` | Cold-to-Archive Mover (L3) | L3 Cold ≠ L3 Archive |
| `REMOTE_HOT_READER_URL` | DT Data Connector (L4) | L4 ≠ L3 |
| `EVENT_CHECKER_FUNCTION_URL` | Persister (L2) | Azure only, when using event checking |
| `INTER_CLOUD_TOKEN` | All above | Any multi-cloud |

### Current State

| Provider | All Multi-Cloud Env Vars |
|----------|--------------------------|
| Azure | ✅ Implemented |
| AWS | ✅ Implemented |
| GCP | ✅ Implemented (except GCP Layer 2?) |

### Solution (Per Function)

Add to Terraform:

**Connector (L1) - `*_iot.tf`:**
```hcl
REMOTE_INGESTION_URL = var.layer_1_provider != var.layer_2_provider ? <L0_ingestion_url_from_L2_provider> : ""
```

**Persister (L2) - `*_compute.tf`:**
```hcl
REMOTE_WRITER_URL = var.layer_2_provider != var.layer_3_hot_provider ? <L0_hot_writer_url_from_L3_provider> : ""
```

**Hot-to-Cold Mover (L3) - `*_storage.tf`:**
```hcl
REMOTE_COLD_WRITER_URL = var.layer_3_hot_provider != var.layer_3_cold_provider ? <L0_cold_writer_url> : ""
```

**Cold-to-Archive Mover (L3) - `*_storage.tf`:**
```hcl
REMOTE_ARCHIVE_WRITER_URL = var.layer_3_cold_provider != var.layer_3_archive_provider ? <L0_archive_writer_url> : ""
```

**DT Data Connector (L4) - `*_digital_twin.tf`:**
```hcl
REMOTE_HOT_READER_URL = var.layer_4_provider != var.layer_3_hot_provider ? <L3_hot_reader_url> : ""
```

---

## 17. Grafana Dashboard & Datasource Automation via Terraform

> [!NOTE]
> Research completed December 2024. Implementation deferred.

### Status: Research Complete, Not Implemented

### Background

AWS Managed Grafana now supports automated user provisioning (implemented December 2024). However, dashboard creation and datasource configuration still require manual steps or SDK post-deployment.

### Research Findings

**Terraform Grafana Provider** can manage dashboards/datasources in AWS Managed Grafana:

```hcl
# Configure Grafana provider using API key from AWS workspace
provider "grafana" {
  url  = aws_grafana_workspace.main[0].endpoint
  auth = aws_grafana_workspace_api_key.admin[0].key
}

# Create datasource (JSON API to Hot Reader)
resource "grafana_data_source" "hot_reader" {
  type = "marcusolsson-json-datasource"
  name = "Hot Reader API"
  url  = aws_lambda_function_url.l3_hot_reader[0].function_url
}

# Create dashboard from JSON template
resource "grafana_dashboard" "main" {
  config_json = file("${path.module}/dashboard.json")
}
```

### Requirements

| Requirement | Details |
|-------------|---------|
| Provider | `grafana/grafana` (separate from hashicorp/aws) |
| Authentication | Uses API key already created by `aws_grafana_workspace_api_key` |
| Dashboard JSON | Can export from Grafana UI or create template |
| Plugin | JSON API datasource needs `marcusolsson-json-datasource` plugin |

### Data Flow Architecture

```
IoT Device → L1 Dispatcher → L2 Persister → L3 DynamoDB
                                               ↓
                                    L3 Hot Reader (Lambda)
                                               ↓
                         L5 Grafana (polls Hot Reader via JSON API datasource)
```

Grafana does **not** receive real-time data - it queries the Hot Reader on dashboard refresh.

### E2E Validation Options

1. **Existing coverage sufficient**: `test_08_verify_hot_reader` validates data accessibility
2. **Grafana API query**: Use API key to query `/api/search` for dashboards, `/api/datasources` for datasources
3. **Full data flow**: Send IoT message → wait → query Grafana dashboard panel API for data

### Implementation Tasks (If Prioritized)

- [ ] Add `grafana` provider to `versions.tf`
- [ ] Create `aws_grafana_config.tf` for datasource + dashboard resources
- [ ] Create dashboard JSON template (`src/terraform/templates/grafana_dashboard.json`)
- [ ] Add E2E test to verify datasource connectivity
- [ ] Document JSON API datasource configuration in docs

---

## Notes

- **Priority**: E2E testing > Azure init values > SDK validation > GCP
- **Timeline**: To be determined based on thesis requirements


