# Hardcoded Configurations

This document lists all hardcoded configuration values in the 3-cloud-deployer system.

---

## Azure Consumption Plan (Y1) Configuration

### Current Implementation (Y1 - Traditional Consumption)

| Configuration | Value | Location | Rationale |
|---------------|-------|----------|-----------|
| **SKU Name** | `"Y1"` | `src/terraform/azure_*.tf` | Consumption plan (serverless) |
| **OS Type** | `"Linux"` | `src/terraform/azure_*.tf` | Required for Python 3.11 runtime |
| **Python Version** | `"3.11"` | `src/terraform/azure_*.tf` | Latest stable Python for Azure Functions |
| **Instance Memory** | 1.5 GB (fixed) | Azure platform | Cannot be configured in Y1 |
| **Max Instances** | 200 (platform limit) | Azure platform | Cannot exceed this in Y1 |

### App Service Plans

| Plan | Layer | Condition | File |
|------|-------|-----------|------|
| **l0-plan** | Glue (cross-cloud) | `deploy_azure` | [azure_glue.tf:27](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/azure_glue.tf#L27) |
| **l1-plan** | IoT | `layer_1_provider == "azure"` | [azure_iot.tf:51](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/azure_iot.tf#L51) |
| **l2-plan** | Compute | `layer_2_provider == "azure"` | [azure_compute.tf:21](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/azure_compute.tf#L21) |
| **l3-plan** | Storage | `layer_3_hot_provider == "azure"` | [azure_storage.tf:110](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/azure_storage.tf#L110) |

### Deployment Settings

| Setting | Value | Purpose |
|---------|-------|---------|
| `FUNCTIONS_EXTENSION_VERSION` | `"~4"` | Azure Functions runtime version |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `"true"` | Enable Oryx build on deployment |
| `ENABLE_ORYX_BUILD` | `"true"` | Required for pip install |
| `AzureWebJobsFeatureFlags` | `"EnableWorkerIndexing"` | Enable function indexing |

### Supported Regions (Y1 + Linux)

**Recommended** (empirically verified):
- `westeurope` (Primary - West Europe)
- `northeurope` (North Europe - Dublin)
- `francecentral` (France Central - Paris)
- `germanywestcentral` (Germany West Central - Frankfurt)
- `uksouth` (UK South - London)
- `eastus` (East US - Virginia)
- `westus2` (West US 2 - Washington)

**NOT Supported**:
- `italynorth` - Only supports Flex Consumption (FC1), not Y1+Linux

> **Note**: There is no programmatic API to query Y1+Linux regional support.  
> The unsupported list is based on empirical testing (December 2025).  
> See [azure_flex_consumption_migration.md](file:///d:/Git/master-thesis/3-cloud-deployer/docs/azure_flex_consumption_migration.md) for details.

---

## Future: Flex Consumption (FC1) Configuration

### If Migrating to FC1

| Configuration | Recommended Value | Rationale |
|---------------|-------------------|-----------|
| **SKU Name** | `"FC1"` | Flex Consumption |
| **Instance Memory** | `512` MB | Sufficient for our workload, reduces cost |
| **Max Instances** | `100` | Balance between scale and quota |
| **Always Ready** | `0` | Pay-as-you-go, no extra cost |

### Additional Plans Required

FC1 allows only **1 app per plan**, so L2 needs split:
- `l2-plan` → Main functions (persister, event-checker)
- `l2-user-plan` → User functions (processors, event-actions)

### Deployment Changes Required

- ❌ Remove `zip_deploy_file`
- ✅ Add blob storage deployment
- ✅ Use `function_app_config` block
- ✅ Handle EventGrid timing differently

**See**: [azure_flex_consumption_migration.md](file:///d:/Git/master-thesis/3-cloud-deployer/docs/azure_flex_consumption_migration.md) for full details

---

## AWS Configuration

| Configuration | Value | Location |
|---------------|-------|----------|
| **Lambda Runtime** | `python3.11` | `src/terraform/aws_*.tf` |
| **Lambda Timeout** | Various (30s-900s) | Per function |
| **Lambda Memory** | Various (128MB-1024MB) | Per function |

---

## GCP Configuration

| Configuration | Value | Location |
|---------------|-------|----------|
| **Cloud Functions Runtime** | `python311` | `src/terraform/gcp_*.tf` |
| **Cloud Functions Memory** | Various (256MB-1024MB) | Per function |

---

## Terraform Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| **Digital Twin Name Max Length** | 30 characters | Resource naming limits |
| **Valid Characters** | `[A-Za-z0-9_-]` | Cloud provider constraints |

---

## Validation Constants

### Azure Region Validation

**Location**: [src/constants.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/constants.py)

```python
AZURE_UNSUPPORTED_REGIONS_Y1_LINUX = [
    "italynorth",  # Only supports FC1, not Y1+Linux
]

AZURE_RECOMMENDED_REGIONS_Y1_LINUX = [
    "westeurope",
    "northeurope",
    "francecentral",
    "germanywestcentral",
    "uksouth",
    "eastus",
    "westus2",
]
```

---

## Notes

- All hardcoded values are based on cloud provider limitations and best practices
- Values may change when migrating to newer hosting plans (e.g., FC1)
- Always test configuration changes in staging before production
- Regional availability is validated at project upload/validation time
