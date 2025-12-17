# Hybrid Function Deployment Implementation

## Goal
Implement Option C: System functions via Terraform `zip_deploy_file`, user functions via SDK post-deploy with hash comparison.

## Changes Overview

### 1. Terraform Infrastructure

#### [MODIFY] azure_compute.tf
- Add a "user-functions" Function App for user-customizable functions
- This app will host: event actions, processors, event-feedback

---

### 2. tfvars_generator.py (Already Updated)
- Builds system function ZIPs (L0, L1, L2, L3) for Terraform
- User functions are NOT built here (handled by deployer)

---

### 3. Azure Deployer Updates

#### [MODIFY] azure_deployer.py
- Remove system function Kudu deployment (now handled by Terraform)
- Add user function deployment with hash comparison
- Call `build_user_packages()` → check hashes → deploy only changed

---

### 4. Package Builder Updates

#### [MODIFY] package_builder.py
- Add `check_user_hash_changed()` function to compare current vs saved hash
- Add `deploy_changed_user_functions()` orchestration function

---

## Proposed Changes

### Phase 1: Terraform - Add User Functions App

```hcl
# azure_compute.tf - add after L2 function app

resource "azurerm_linux_function_app" "user" {
  count               = var.layer_2_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-user-functions"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.l2[0].id  # Share with L2

  storage_account_name       = azurerm_storage_account.main[0].name
  storage_account_access_key = azurerm_storage_account.main[0].primary_access_key

  # No zip_deploy_file - user functions deployed via SDK after terraform

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main[0].id]
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME       = "python"
    FUNCTIONS_EXTENSION_VERSION    = "~4"
    AzureWebJobsStorage           = local.azure_storage_connection_string
    DIGITAL_TWIN_NAME              = var.digital_twin_name
    AZURE_CLIENT_ID                = azurerm_user_assigned_identity.main[0].client_id
    INTER_CLOUD_TOKEN              = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
  }

  tags = local.common_tags
}
```

### Phase 2: Package Builder - Add Hash Comparison

```python
# package_builder.py - add functions

def check_user_hash_changed(project_path: Path, function_name: str, provider: str) -> bool:
    """Check if user function code has changed since last build."""
    metadata_path = project_path / ".build" / "metadata" / f"{function_name}.{provider}.json"
    
    if not metadata_path.exists():
        return True  # No previous build, needs build
    
    # Get current hash
    func_type = "event_actions" if not function_name.startswith("processor-") else "processors"
    func_dir = project_path / f"{provider}_functions" / func_type / function_name
    
    if not func_dir.exists():
        return False  # Function doesn't exist
    
    current_hash = _compute_directory_hash(func_dir)
    
    # Compare with saved
    with open(metadata_path, 'r') as f:
        saved = json.load(f)
    
    return current_hash != saved.get("zip_hash")
```

### Phase 3: Azure Deployer - User Function Deployment

```python
# azure_deployer.py - update deploy_azure_function_code

def deploy_azure_function_code(self, project_path: str, providers_config: dict):
    """Deploy user function code (system functions handled by Terraform)."""
    from src.providers.terraform.package_builder import (
        build_user_packages,
        check_user_hash_changed,
        get_user_package_path,
    )
    
    # Get user functions app name from terraform output
    user_app_name = self.terraform_outputs.get("azure_user_functions_app_name")
    
    if not user_app_name:
        logger.info("No user functions app deployed, skipping user function deployment")
        return
    
    # Build user packages with hash tracking
    packages = build_user_packages(Path(project_path), providers_config)
    
    # Deploy each changed function
    for func_name, zip_path in packages.items():
        if check_user_hash_changed(Path(project_path), func_name, "azure"):
            logger.info(f"Deploying changed user function: {func_name}")
            self._deploy_to_azure_app(user_app_name, zip_path)
        else:
            logger.info(f"Skipping unchanged user function: {func_name}")
```

---

## Verification Plan

### Automated Tests
- Run existing unit tests to ensure no regressions
- Run E2E test with all layers

### Manual Verification
- Deploy, modify a user function, redeploy - only modified should update
