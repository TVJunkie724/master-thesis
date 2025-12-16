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

### Architecture Notes

GCP implementation will be **Terraform-only** (no SDK layer deployment):
- Cloud Functions will be deployed via Terraform `google_cloudfunctions2_function`
- IoT Core (or Cloud IoT alternatives) via Terraform
- Firestore for hot storage
- Cloud Storage for cold/archive

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

## 5. SDK Managed Resource Validation

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

## 6. Documentation

### Status: Ongoing

- [ ] Update architecture docs with Terraform-first approach
- [ ] Document multi-cloud configuration examples
- [ ] Add troubleshooting guide for common deployment issues
- [ ] Create video walkthrough of deployment process

---

## 7. Performance Improvements

### Ideas

- [ ] Parallel Terraform plan/apply for multi-cloud
- [ ] Cache hot path configs for faster status checks
- [ ] Optimize function package building

---

## 8. Security Enhancements

### Ideas

- [ ] Rotate inter-cloud tokens periodically
- [ ] Support Azure Key Vault for credential storage
- [ ] Support AWS Secrets Manager for credential storage
- [ ] Add certificate-based authentication option

---

## Notes

- **Priority**: E2E testing > Azure init values > SDK validation > GCP
- **Timeline**: To be determined based on thesis requirements
