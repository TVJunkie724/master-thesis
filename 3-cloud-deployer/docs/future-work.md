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

## Notes

- **Priority**: E2E testing > Azure init values > SDK validation > GCP
- **Timeline**: To be determined based on thesis requirements
