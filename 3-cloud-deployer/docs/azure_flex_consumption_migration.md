# Azure Flex Consumption (FC1) Migration Guide

## ⚠️ CRITICAL: Do Not Migrate Yet

This document outlines the issues and requirements for migrating from traditional Consumption Plan (Y1) to Flex Consumption (FC1). **Migration is NOT recommended at this time** due to significant breaking changes.

**Current Status**: Using Y1 + westeurope (working solution)  
**Future Work**: FC1 migration (estimated 12-18 hours)

---

## Why This Document Exists

During investigation of the Italy North region issue, we discovered that migrating to Flex Consumption would require extensive changes. This document preserves that research for future reference.

---

## 🚨 Critical Issues with FC1 Migration

### Issue #1: `zip_deploy_file` NOT SUPPORTED ⚠️⚠️⚠️

**Severity**: CRITICAL - BLOCKS ENTIRE MIGRATION

**Problem**:
- Our current deployment uses `zip_deploy_file` in ALL 4 Terraform files
- **Flex Consumption does NOT support `zip_deploy_file`**
- FC1 uses a completely different deployment mechanism

**Current Code** (ALL 4 files):
```hcl
resource "azurerm_linux_function_app" "l0_glue" {
  zip_deploy_file = var.azure_l0_zip_path  # ← WILL NOT WORK WITH FC1!
  ...
}
```

**Impact**:
- ❌ Terraform apply will succeed (infrastructure created)
- ❌ But functions will have NO CODE deployed
- ❌ All functions will fail to execute
- ❌ Tests will fail completely

**Required Changes**:
1. Remove all `zip_deploy_file` references
2. Create blob storage container for deployments
3. Upload ZIPs to blob storage
4. Configure function apps to use blob storage
5. Update deployment pipeline

---

### Issue #2: Deprecated ARM/Bicep Settings

**Severity**: HIGH - May cause deployment failures

**Problem**:
- Many standard app settings are deprecated in FC1
- Must use new `function_app_config` section instead
- Our Terraform uses old-style `app_settings` block

**Deprecated Settings**:
- `FUNCTIONS_EXTENSION_VERSION` - Still needed despite docs saying otherwise!
- `SCM_DO_BUILD_DURING_DEPLOYMENT` - Deprecated
- `ENABLE_ORYX_BUILD` - Deprecated
- `WEBSITE_CONTENTAZUREFILECONNECTIONSTRING` - Deprecated
- `WEBSITE_CONTENTSHARE` - Deprecated

**Required New Format**:
```hcl
resource "azurerm_linux_function_app" "l0" {
  # NEW WAY (required for FC1):
  function_app_config {
    runtime {
      name    = "python"
      version = "3.11"
    }
    deployment {
      storage_account_connection_string = ...
    }
    scaling {
      maximum_instance_count = 100
      instance_memory_mb     = 512
    }
  }
}
```

---

### Issue #3: EventGrid Subscription Timing

**Severity**: MEDIUM - May cause deployment failures

**Problem**:
- L1 uses EventGrid subscription to IoT Hub
- Subscription depends on function code being deployed
- With FC1, code deployment is SEPARATE from Terraform
- EventGrid subscription will fail if function doesn't exist yet

**Current Code** (azure_iot.tf:166-183):
```hcl
resource "azurerm_eventgrid_system_topic_event_subscription" "iothub_to_dispatcher" {
  count = var.layer_1_provider == "azure" && var.azure_l1_zip_path != "" ? 1 : 0
  
  azure_function_endpoint {
    function_id = "${azurerm_linux_function_app.l1[0].id}/functions/dispatcher"
  }
  
  depends_on = [time_sleep.wait_for_function_sync]  # ← Won't work with FC1!
}
```

**Impact**:
- EventGrid subscription may fail
- Or succeed but not route events (function doesn't exist)
- L1 → L2 data flow broken

---

### Issue #4: One App Per Plan

**Severity**: HIGH - Requires architectural changes

**Problem**:
- **Y1**: Multiple function apps can share one plan
- **FC1**: **Only ONE function app per plan**

**Current Architecture**:
- L2 plan hosts **2 apps**: `l2-functions` + `user-functions`

**Required Change**:
- L2 needs **2 separate plans**: `l2-plan` + `l2-user-plan`

**Terraform Changes**:
```hcl
# L2 Main Functions Plan
resource "azurerm_service_plan" "l2" {
  name     = "${var.digital_twin_name}-l2-plan"
  sku_name = "FC1"
  maximum_instance_count = 100
  instance_memory_mb     = 512
}

# L2 User Functions Plan (NEW!)
resource "azurerm_service_plan" "l2_user" {
  name     = "${var.digital_twin_name}-l2-user-plan"
  sku_name = "FC1"
  maximum_instance_count = 50
  instance_memory_mb     = 512
}
```

---

## Regional Availability

### Traditional Consumption (Y1) + Linux
- ✅ **westeurope**: Supported
- ✅ **northeurope**: Supported
- ✅ **francecentral**: Supported
- ❌ **italynorth**: NOT supported

### Flex Consumption (FC1)
- ✅ **italynorth**: Supported (since May 2025)
- ✅ **westeurope**: Supported
- ✅ Most other regions: Supported

**Query Command**:
```bash
az functionapp list-flexconsumption-locations
```

---

## Configuration Comparison

| Feature | Y1 (Current) | FC1 (Future) |
|---------|--------------|--------------|
| **SKU** | `"Y1"` | `"FC1"` |
| **Memory** | 1.5 GB (fixed) | 512 MB / 2 GB / 4 GB (configurable) |
| **Max Instances** | 200 | 1000 |
| **Apps per Plan** | Multiple | **1 only** |
| **Deployment** | `zip_deploy_file` | Blob storage |
| **VNet Support** | ❌ No | ✅ Yes |
| **Always Ready** | ❌ No | ✅ Yes (optional) |
| **Cold Start** | Slower | Faster |
| **Retirement** | Sep 30, 2028 | N/A (current) |

---

## Recommended Hardcoded Values for FC1

Based on user feedback during planning:

| Configuration | Value | Rationale |
|---------------|-------|-----------|
| `instance_memory_mb` | `512` | Sufficient for minimal workload, reduces cost |
| `maximum_instance_count` | `100` | Balance between scale and quota (may need to reduce to 40 due to regional quota) |
| `always_ready_instances` | `0` | Pay-as-you-go, no extra cost |

---

## Migration Effort Estimate

| Phase | Original Estimate | Actual Estimate | Reason |
|-------|-------------------|-----------------|--------|
| Planning | 30 min | 2-4 hours | Need prototype |
| Implementation | 1 hour | 4-6 hours | Complete rework |
| Deployment Automation | N/A | 3-4 hours | NEW requirement |
| Testing | 1 hour | 2-3 hours | More complex |
| Documentation | N/A | 1 hour | User requested |
| **TOTAL** | **3 hours** | **12-18 hours** | **4-6x longer** |

---

## Files Requiring Changes

### Terraform Files (4 files)
1. `src/terraform/azure_glue.tf` - L0 plan
2. `src/terraform/azure_iot.tf` - L1 plan
3. `src/terraform/azure_compute.tf` - L2 plan (split into 2)
4. `src/terraform/azure_storage.tf` - L3 plan

### Deployment Pipeline
1. Create blob storage deployment mechanism
2. Update ZIP upload process
3. Handle EventGrid timing
4. Update CI/CD integration

### Documentation
1. Update deployment guide
2. Document new configuration values
3. Create rollback procedure

---

## Recommended Approach

### Option A: Quick Fix (CURRENT - IMPLEMENTED)

**Change region to `westeurope`**

**Pros**:
- ✅ 5 minutes to implement
- ✅ Works immediately
- ✅ No deployment changes
- ✅ No risk

**Cons**:
- ❌ Still on retiring Y1 plan (until 2028)
- ❌ Data in different region

**Status**: ✅ **COMPLETED**

---

### Option B: Migrate to FC1 (FUTURE WORK)

**Do this AFTER quick fix, as separate project**

**Pros**:
- ✅ Future-proof
- ✅ Better features
- ✅ Can use Italy North

**Cons**:
- ❌ 12-18 hours of work
- ❌ Complete deployment rework
- ❌ High risk of issues
- ❌ Requires extensive testing

**Timeline**: Q1 2026 (or before Sep 2028 retirement)

---

## Testing Strategy for FC1 Migration

When ready to migrate:

1. **Prototype** (2-4 hours)
   - Create single FC1 function app
   - Test blob storage deployment
   - Verify EventGrid works
   - Document working configuration

2. **Staging** (4-6 hours)
   - Deploy full stack to staging
   - Run all E2E tests
   - Verify cross-cloud connections
   - Performance testing

3. **Production** (2-3 hours)
   - Blue-green deployment
   - Monitor for issues
   - Rollback plan ready

---

## Rollback Plan

If FC1 causes issues:

**Option A**: Revert to Y1 + West Europe
```hcl
sku_name = "Y1"
location = "westeurope"
```

**Option B**: Keep FC1 but adjust settings
```hcl
sku_name = "FC1"
maximum_instance_count = 50  # Reduce if cost is issue
instance_memory_mb     = 512  # Reduce if not needed
```

---

## References

- [Azure Functions Flex Consumption Documentation](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan)
- [Linux Consumption Plan Retirement Notice](https://azure.microsoft.com/en-us/updates/retirement-notice-transition-from-azure-functions-linux-consumption-plan-to-flex-consumption-by-30-september-2028/)
- [Terraform azurerm_function_app_flex_consumption](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/function_app_flex_consumption)

---

## Conclusion

**Current Solution**: Y1 + westeurope (working, stable)  
**Future Migration**: FC1 (complex, 12-18 hours, before Sep 2028)

**Do NOT migrate to FC1 now** unless:
- You specifically need Italy North region
- You need VNet integration
- You need faster cold starts
- You have 2-3 days for implementation and testing
