# Multi-Cloud Environment Variables & GCP Features

Add missing environment variables for cross-cloud data flow and complete GCP L2 implementation.

## User Review Required

> [!IMPORTANT]
> Multi-cloud env vars are empty strings in single-cloud deployments. No behavior change for existing deployments.

> [!WARNING]
> GCP Phase 2 creates new files. Confirm GCP L2 is in scope before proceeding.

---

## Proposed Changes

### Phase 1: Multi-Cloud Environment Variables

---

#### [MODIFY] [azure_iot.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/azure_iot.tf)

Add to L1 dispatcher `app_settings`:
```hcl
REMOTE_INGESTION_URL = var.layer_1_provider == "azure" && var.layer_2_provider != "azure" ? (
  var.layer_2_provider == "aws" ? aws_lambda_function_url.l0_ingestion[0].function_url : ""
) : ""
```

---

#### [MODIFY] [azure_compute.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/azure_compute.tf)

Add to L2 function `app_settings`:
```hcl
REMOTE_WRITER_URL = var.layer_2_provider == "azure" && var.layer_3_hot_provider != "azure" ? (
  var.layer_3_hot_provider == "aws" ? aws_lambda_function_url.l0_hot_writer[0].function_url :
  var.layer_3_hot_provider == "google" ? google_cloudfunctions2_function.hot_writer[0].url : ""
) : ""

REMOTE_ADT_PUSHER_URL = var.layer_2_provider != "azure" && var.layer_4_provider == "azure" ? (
  azurerm_linux_function_app.l4_adt_pusher[0].default_hostname
) : ""

LOGIC_APP_TRIGGER_URL = var.trigger_notification_workflow ? (
  azurerm_logic_app_trigger_http_request.event_trigger[0].callback_url
) : ""
```

---

#### [MODIFY] [azure_storage.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/azure_storage.tf)

Add to L3 mover functions:
```hcl
REMOTE_COLD_WRITER_URL = var.layer_3_hot_provider == "azure" && var.layer_3_cold_provider != "azure" ? (
  var.layer_3_cold_provider == "aws" ? aws_lambda_function_url.l0_cold_writer[0].function_url :
  var.layer_3_cold_provider == "google" ? google_cloudfunctions2_function.cold_writer[0].url : ""
) : ""

REMOTE_ARCHIVE_WRITER_URL = var.layer_3_cold_provider == "azure" && var.layer_3_archive_provider != "azure" ? (
  var.layer_3_archive_provider == "aws" ? aws_lambda_function_url.l0_archive_writer[0].function_url :
  var.layer_3_archive_provider == "google" ? google_cloudfunctions2_function.archive_writer[0].url : ""
) : ""
```

---

#### [MODIFY] [aws_iot.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/aws_iot.tf)

Add to dispatcher Lambda `environment.variables`:
```hcl
REMOTE_INGESTION_URL = var.layer_1_provider == "aws" && var.layer_2_provider != "aws" ? (
  var.layer_2_provider == "azure" ? "https://${azurerm_linux_function_app.l0[0].default_hostname}/api/ingestion" : ""
) : ""
INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
```

---

#### [MODIFY] [aws_compute.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/aws_compute.tf)

Add to L2 Persister Lambda `environment.variables`:
```hcl
REMOTE_WRITER_URL = var.layer_2_provider == "aws" && var.layer_3_hot_provider != "aws" ? (
  var.layer_3_hot_provider == "azure" ? "https://${azurerm_linux_function_app.l0[0].default_hostname}/api/hot-writer" :
  var.layer_3_hot_provider == "google" ? google_cloudfunctions2_function.hot_writer[0].url : ""
) : ""
INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result

REMOTE_ADT_PUSHER_URL = var.layer_2_provider == "aws" && var.layer_4_provider == "azure" ? (
  "https://${azurerm_linux_function_app.l4_adt_pusher[0].default_hostname}/api/adt-pusher"
) : ""
ADT_PUSHER_TOKEN = var.layer_4_provider == "azure" ? var.inter_cloud_token : ""
```

---

#### [MODIFY] [aws_storage.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/aws_storage.tf)

Add to mover Lambdas `environment.variables`:
```hcl
# Hot-to-Cold Mover
REMOTE_COLD_WRITER_URL = var.layer_3_hot_provider == "aws" && var.layer_3_cold_provider != "aws" ? (
  var.layer_3_cold_provider == "azure" ? "https://${azurerm_linux_function_app.l0[0].default_hostname}/api/cold-writer" : ""
) : ""

# Cold-to-Archive Mover
REMOTE_ARCHIVE_WRITER_URL = var.layer_3_cold_provider == "aws" && var.layer_3_archive_provider != "aws" ? (
  var.layer_3_archive_provider == "azure" ? "https://${azurerm_linux_function_app.l0[0].default_hostname}/api/archive-writer" : ""
) : ""
```

---

#### [MODIFY] [gcp_compute.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/gcp_compute.tf)

Add to persister `environment_variables`:
```hcl
REMOTE_WRITER_URL = var.layer_2_provider == "google" && var.layer_3_hot_provider != "google" ? (
  var.layer_3_hot_provider == "aws" ? aws_lambda_function_url.l0_hot_writer[0].function_url :
  var.layer_3_hot_provider == "azure" ? "https://${azurerm_linux_function_app.l0[0].default_hostname}/api/hot-writer" : ""
) : ""
INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : (
  local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
)
```

---

### Phase 2: GCP Simulator Config (Terraform-Native)

> [!TIP]
> GCP uses Pub/Sub with no device registry, so simulator config can be generated entirely via Terraform!

---

#### [MODIFY] [variables.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/variables.tf)

Add `iot_devices` variable for Terraform to iterate over:
```hcl
variable "iot_devices" {
  type = list(object({ id = string }))
  default = []
}
```

---

#### [MODIFY] [gcp_iot.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/gcp_iot.tf)

Add `local_file` resource to generate simulator configs:
```hcl
resource "local_file" "gcp_simulator_config" {
  for_each = local.gcp_l1_enabled ? { for device in var.iot_devices : device.id => device } : {}
  
  filename = "${var.project_path}/iot_device_simulator/gcp/config_generated_${each.key}.json"
  content  = jsonencode({
    project_id              = var.gcp_project_id
    topic_name              = "dt/${var.digital_twin_name}/telemetry"
    device_id               = each.key
    digital_twin_name       = var.digital_twin_name
    ...
  })
}
```

> [!NOTE]
> Azure and AWS still require SDK for simulator config because the device connection strings are only available AFTER registering the device in IoT Hub/IoT Core.

---

## Verification Plan

### Automated Tests

#### Terraform Validation
- `terraform validate` after each file change

#### Unit Tests (New)

**Multi-cloud env var logic:**

| Scenario | Expected |
|----------|----------|
| L2=L3 (same cloud) | `REMOTE_WRITER_URL = ""` |
| L2≠L3 (multi-cloud) | `REMOTE_WRITER_URL = <target_url>` |
| `trigger_notification_workflow=false` | `LOGIC_APP_TRIGGER_URL = ""` |
| `trigger_notification_workflow=true` | `LOGIC_APP_TRIGGER_URL = callback_url` |

**GCP functions (`layer_1_iot.py`):**

| Scenario | Expected |
|----------|----------|
| Valid config with devices | `config_generated.json` created |
| Empty device list | No file created, no error |
| Missing project_path | `ValueError` raised |
| Invalid config | Clear error message |

**GCP deployer (`gcp_deployer.py`):**

| Scenario | Expected |
|----------|----------|
| L1=GCP, valid config | Simulator config generated |
| L2=GCP with user functions | User functions deployed |
| Missing credentials | Clear error message |

**Error scenarios:**
- Missing provider variable → Terraform validation error
- Invalid provider combination → Clear error message

### Manual Verification
- Deploy multi-cloud scenario and verify cross-cloud POST in logs


