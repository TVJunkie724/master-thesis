# Azure Managed Grafana Version Upgrade

## 1. Executive Summary

### The Problem
Azure Managed Grafana deployment failed with:
- `GrafanaMajorVersionNotSupported: version 'X' is not valid for sku type Standard`

Root cause: Azure only supports Grafana v11 for Standard SKU as of 2024, but the AzureRM provider 3.x only accepted v9/v10.

### The Solution
- Upgrade AzureRM provider from `~> 3.85` to `~> 4.0`
- Update `grafana_major_version` from `"10"` to `"11"`
- Replace deprecated `skip_provider_registration` with `resource_provider_registrations = "none"`

### Impact
- Grafana L5 layer now deploys successfully
- Using latest AzureRM provider with current API support

---

## 2. Proposed Changes

### Component: Terraform Versions

#### [x] [MODIFY] versions.tf
- **Path:** `src/terraform/versions.tf`
- **Description:** Upgraded AzureRM provider version

```hcl
azurerm = {
  source  = "hashicorp/azurerm"
  version = "~> 4.0"  # Was: "~> 3.85"
}
```

---

### Component: Terraform Main

#### [x] [MODIFY] main.tf
- **Path:** `src/terraform/main.tf`
- **Description:** Replaced deprecated provider configuration

```hcl
# Before:
skip_provider_registration = true

# After:
resource_provider_registrations = "none"
```

---

### Component: Terraform Grafana

#### [x] [MODIFY] azure_grafana.tf
- **Path:** `src/terraform/azure_grafana.tf`
- **Description:** Updated Grafana version to v11

```hcl
# Grafana version (11 required for Standard SKU as of 2024)
grafana_major_version = "11"  # Was: 9
```

---

## 3. Verification Checklist

- [x] Terraform init succeeds with new provider
- [x] Terraform validate passes
- [x] Grafana deployment creates v11 instance
- [x] E2E test conftest.py updated with comment

---

## 4. Design Decisions

### Provider Version ^4.0
AzureRM 4.x introduces breaking changes but is required for:
- Grafana v11 support
- Current Azure API compatibility
- `resource_provider_registrations` attribute

### Version String Format
Changed from integer `9` to string `"11"` as required by AzureRM 4.x provider.
