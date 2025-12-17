# EventGrid Subscription Deployment Order Fix

## 1. Executive Summary

### The Problem
EventGrid subscription in `azure_iot.tf` failed with `Resource should pre-exist before attempting this operation` because:
1. Terraform creates the function app container (empty shell)
2. Python deploys the actual function code AFTER Terraform finishes
3. When EventGrid subscription is created, the `dispatcher` function doesn't exist yet

### The Solution
Use Terraform's `zip_deploy_file` attribute to deploy function code during `terraform apply`, ensuring functions exist before EventGrid subscriptions.

### Impact
- Functions are deployed as part of Terraform apply
- EventGrid subscriptions can reference function endpoints immediately
- No more Kudu deployment needed after Terraform apply

---

## 2. Proposed Changes

### Component: Terraform Variables

#### [x] [MODIFY] variables.tf
- **Path:** `src/terraform/variables.tf`
- **Description:** Added Azure function ZIP path variables for Terraform zip deployment

```hcl
variable "azure_l0_zip_path" {
  description = "Path to the L0 glue functions ZIP file"
  type        = string
  default     = ""
}

variable "azure_l1_zip_path" {
  description = "Path to the L1 (Dispatcher) functions ZIP file"
  type        = string
  default     = ""
}

variable "azure_l2_zip_path" {
  description = "Path to the L2 (Processor) functions ZIP file"
  type        = string
  default     = ""
}

variable "azure_l3_zip_path" {
  description = "Path to the L3 (Storage) functions ZIP file"
  type        = string
  default     = ""
}
```

---

### Component: Terraform Azure Storage

#### [x] [MODIFY] azure_storage.tf
- **Path:** `src/terraform/azure_storage.tf`
- **Description:** Added `zip_deploy_file` attribute to L3 function app

```hcl
zip_deploy_file = var.azure_l3_zip_path != "" ? var.azure_l3_zip_path : null
```

---

### Component: tfvars Generator

#### [x] [MODIFY] tfvars_generator.py
- **Path:** `src/tfvars_generator.py`
- **Description:** 
  - Added `_build_azure_function_zips()` function
  - Uses `function_bundler.py` to pre-build function ZIPs
  - Returns ZIP paths for Terraform to deploy

```python
def _build_azure_function_zips(project_dir: Path, providers: dict) -> dict:
    """
    Build Azure function ZIP files for Terraform zip_deploy_file.
    Uses the existing function_bundler to create ZIP files, then returns
    the paths for Terraform to deploy via zip_deploy_file attribute.
    """
    # ... implementation
```

---

## 3. Verification Checklist

- [x] tfvars_generator.py builds function ZIPs
- [x] ZIP paths passed to Terraform variables
- [x] Function apps deploy code during terraform apply
- [x] EventGrid subscriptions succeed

---

## 4. Design Decisions

### Pre-build During tfvars Generation
Building ZIPs during `tfvars_generator.py` execution ensures:
- ZIPs exist before `terraform plan`
- File hashes are consistent for Terraform state
- No additional orchestration needed

### Optional ZIP Paths
Using `var.azure_lX_zip_path != "" ? var.azure_lX_zip_path : null` allows:
- Backward compatibility with existing deployments
- Flexibility for different deployment workflows
