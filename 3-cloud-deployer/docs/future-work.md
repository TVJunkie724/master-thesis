# Future Work

This document tracks planned improvements and features for the Digital Twin Multi-Cloud Deployer.

> [!TIP]
> See [future-work-resolved.md](future-work-resolved.md) for completed items.

---

## 1. Deprecated Code Cleanup

### Status: Pending

### Items to Review

- [ ] Legacy `provider.naming` method in `src/providers/azure/provider.py`
- [ ] Audit for any remaining SDK deployment methods that should be Terraform-only

---

## 2. Azure API Helper Functions

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

## 3. Event Checker Azure Support

### Status: Not Implemented

The event checker redeployment function only supports AWS. Azure support needs implementation.

**File:** `src/providers/deployer.py:162`

```python
raise NotImplementedError("Event checker redeployment only supported for AWS.")
```

---

## 4. Template Processor Cleanup

### Status: Not Implemented

The processor function in `upload/template/*/processors/default_processor/` already uses the correct minimal `process()` signature. However, the built-in default processors at `src/providers/*/default-processor/` contain full boilerplate code.

**Goal:** Ensure consistency - the default processors should only contain a `process(event)` function like the template, with the system wrapper handling the Lambda/Function boilerplate.

**Files:**
- `src/providers/aws/lambda_functions/default-processor/lambda_function.py`
- `src/providers/azure/azure_functions/default-processor/`
- `src/providers/gcp/cloud_functions/default-processor/`

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

- [x] Update architecture docs with Terraform-first approach
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

## 9. Azure Custom Role: Cosmos DB Permission Investigation

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

## 10. Grafana Dashboard & Datasource Automation via Terraform

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

### Implementation Tasks (If Prioritized)

- [ ] Add `grafana` provider to `versions.tf`
- [ ] Create `aws_grafana_config.tf` for datasource + dashboard resources
- [ ] Create dashboard JSON template (`src/terraform/templates/grafana_dashboard.json`)
- [ ] Add E2E test to verify datasource connectivity
- [ ] Document JSON API datasource configuration in docs

---

## 11. GCP IoT Device Simulator Implementation

> [!CAUTION]
> The GCP IoT Device Simulator is **not implemented**. This section documents the required work.

### Status: Not Implemented

The `src/iot_device_simulator/google/` folder contains only `.gitkeep` and `__init__.py`. 
Unlike AWS and Azure simulators, no functional simulator exists for GCP.

### IoT Simulator Authentication Comparison

| Cloud | Auth Method | Protocol | Config File Contents |
|-------|-------------|----------|---------------------|
| **Azure** | Symmetric Key (SAS) | MQTT/AMQP via SDK | `connection_string`, `device_id` |
| **AWS** | X.509 Certificates | MQTT/TLS | `endpoint`, `cert_path`, `key_path`, `root_ca_path` |
| **GCP** | Service Account | HTTP/gRPC to Pub/Sub | `project_id`, `topic_name`, `service_account_key_path` |

### Key Architectural Difference

**Azure and AWS** use **device-level authentication**:
- Each physical/simulated device has unique credentials
- Credentials are generated during IoT Hub/IoT Core device registration
- Simulator needs `config_generated.json` with device-specific connection string

**GCP** uses **project-level service account authentication**:
- No device registry (GCP IoT Core was deprecated Jan 2023)
- Uses standard Pub/Sub SDK with service account credentials
- Any authorized service account can publish to the telemetry topic
- Terraform already generates per-device `config_generated_{device_id}.json` (see `gcp_iot.tf` line 143-159)

### Implementation Tasks

#### 1. Create Simulator Files

```
src/iot_device_simulator/google/
├── __init__.py          # Exists (empty)
├── globals.py           # NEW - Config loading (similar to aws/globals.py)
├── main.py              # NEW - Entry point
├── transmission.py      # NEW - Pub/Sub message sending
└── templates/           # NEW - Docker/README templates
    ├── Dockerfile
    ├── docker-compose.yml.template
    ├── README.md.template
    └── requirements.txt
```

#### 2. Config File Format

Terraform already generates this at `{project_path}/iot_device_simulator/gcp/config_generated_{device_id}.json`:

```json
{
    "project_id": "my-gcp-project",
    "topic_name": "dt/my-twin/telemetry",
    "device_id": "temperature-sensor-1",
    "digital_twin_name": "my-twin",
    "payload_path": "../payloads.json",
    "auth_method": "service_account",
    "service_account_key_path": "service_account.json"
}
```

#### 3. Transmission Implementation

```python
# transmission.py (pseudocode)
from google.cloud import pubsub_v1
from google.oauth2 import service_account

def publish_message(config, payload):
    credentials = service_account.Credentials.from_service_account_file(
        config["service_account_key_path"]
    )
    publisher = pubsub_v1.PublisherClient(credentials=credentials)
    topic_path = f"projects/{config['project_id']}/topics/{config['topic_name']}"
    
    data = json.dumps(payload).encode("utf-8")
    future = publisher.publish(topic_path, data)
    return future.result()
```

#### 4. Update Download Simulator Endpoint

The REST API endpoint that bundles simulators for download needs GCP support:
- `src/api/simulator.py` - Add GCP case
- Bundle the service account key file with the simulator

#### 5. Add E2E Test Verification (Optional)

Update `test_gcp_terraform_e2e.py` to verify:
- `config_generated_*.json` files exist after deployment
- Files contain correct `topic_name` and `project_id`

### Dependencies

```
# requirements.txt for GCP simulator
google-cloud-pubsub>=2.0.0
google-auth>=2.0.0
```

### Notes

- **No MQTT**: GCP Pub/Sub does not support MQTT natively (unlike AWS IoT Core)
- **gRPC option**: For high-throughput scenarios, consider gRPC instead of HTTP (7x faster)
- **Service Account security**: The SA key file must be protected; consider Workload Identity for production

---

## 12. L0 Glue Layer Conditional Deployment Optimization

> [!CAUTION]
> Current implementation deploys empty L0 Function Apps even in single-cloud scenarios.

### Status: Needs Implementation

### Issue

The L0 Glue Layer (cross-cloud receiver functions) is currently deployed whenever a provider appears in **any** layer configuration, even when no cross-cloud communication is needed.

**Current logic in `main.tf` (lines 75-83):**
```hcl
deploy_azure = contains([
  var.layer_1_provider,
  var.layer_2_provider,
  var.layer_3_hot_provider,
  var.layer_3_cold_provider,
  var.layer_3_archive_provider,
  var.layer_4_provider,
  var.layer_5_provider
], "azure")
```

**Current L0 deployment in `azure_glue.tf` (line 43):**
```hcl
resource "azurerm_linux_function_app" "l0_glue" {
  count = local.deploy_azure ? 1 : 0  # <-- Too broad!
  ...
}
```

### Problem Scenario

When deploying **Azure single-cloud** (all layers = Azure):
- `local.deploy_azure = true` ✅
- L0 Function App is created ❌ (empty, no functions needed)
- Wasted resources and potential confusion

### Expected Behavior

L0 Glue functions should ONLY be deployed when:
1. **Multi-cloud scenario**: More than one provider is used across layers
2. **Cross-layer boundary exists** that requires glue code

### L0 Function Deployment Matrix

Each L0 function has specific deployment conditions:

| L0 Function | Deploy When | Receives From | Sends To |
|-------------|-------------|---------------|----------|
| `ingestion` | L1 provider ≠ L2 provider | Remote L1 | Local L2 Persister |
| `hot-writer` | L2 provider ≠ L3 Hot provider | Remote L2 | Local L3 Hot |
| `cold-writer` | L3 Hot ≠ L3 Cold provider | Remote L3 Hot | Local L3 Cold |
| `archive-writer` | L3 Cold ≠ L3 Archive provider | Remote L3 Cold | Local L3 Archive |
| `hot-reader` | L4 provider ≠ L3 Hot provider | Remote L4/L5 | Local L3 Hot |

### Proposed Implementation

#### 1. Add granular locals in `main.tf`:

```hcl
locals {
  # Multi-cloud boundary detection
  needs_azure_l0_ingestion     = var.layer_1_provider != var.layer_2_provider && var.layer_2_provider == "azure"
  needs_azure_l0_hot_writer    = var.layer_2_provider != var.layer_3_hot_provider && var.layer_3_hot_provider == "azure"
  needs_azure_l0_cold_writer   = var.layer_3_hot_provider != var.layer_3_cold_provider && var.layer_3_cold_provider == "azure"
  needs_azure_l0_archive_writer = var.layer_3_cold_provider != var.layer_3_archive_provider && var.layer_3_archive_provider == "azure"
  needs_azure_l0_hot_reader    = var.layer_4_provider != var.layer_3_hot_provider && var.layer_3_hot_provider == "azure"
  
  # Only deploy L0 app if ANY L0 function is needed
  deploy_azure_l0 = (
    local.needs_azure_l0_ingestion ||
    local.needs_azure_l0_hot_writer ||
    local.needs_azure_l0_cold_writer ||
    local.needs_azure_l0_archive_writer ||
    local.needs_azure_l0_hot_reader
  )
}
```

#### 2. Update `azure_glue.tf`:

```hcl
resource "azurerm_linux_function_app" "l0_glue" {
  count = local.deploy_azure_l0 ? 1 : 0  # <-- Precise condition
  ...
}
```

#### 3. Apply same pattern to AWS and GCP

Each provider's L0 glue layer needs equivalent boundary detection.

### Files to Modify

- `src/terraform/main.tf` - Add boundary detection locals
- `src/terraform/azure_glue.tf` - Update count condition
- `src/terraform/aws_glue.tf` - Update count condition (if exists)
- `src/terraform/gcp_glue.tf` - Update count condition
- `src/core/tfvars_generator.py` - Optionally skip L0 ZIP building when not needed

### Impact

- Cleaner single-cloud deployments (no empty L0 apps)
- Faster `terraform apply` (fewer resources)
- Lower costs (no idle Function Apps)
- Clearer resource visibility in cloud consoles

---

## 13. Multi-User Grafana Provisioning (N Users)

> [!NOTE]
> Current implementation (Dec 2024) supports **single admin user** per cloud.
> This section documents the extension to support **N users** with different roles.

### Status: Documented, Not Implemented

### Background

The optimizer collects `amountOfActiveEditors` and `amountOfActiveViewers` for cost calculation, but the deployer currently only provisions a **single admin** user. This enhancement would allow provisioning multiple users with appropriate roles (Admin, Editor, Viewer).

### Current Implementation (Single Admin)

```json
// config_grafana.json - Current Simple Version
{
  "admin_email": "admin@example.com",
  "admin_first_name": "Grafana",
  "admin_last_name": "Admin"
}
```

### Proposed N-User Implementation

#### Config File Format

```json
// config_grafana.json - N-User Version
{
  "users": [
    {
      "email": "admin@example.com",
      "first_name": "Jane",
      "last_name": "Admin",
      "role": "ADMIN"
    },
    {
      "email": "editor1@example.com",
      "first_name": "Editor",
      "last_name": "One",
      "role": "EDITOR"
    },
    {
      "email": "editor2@example.com",
      "first_name": "Editor",
      "last_name": "Two",
      "role": "EDITOR"
    },
    {
      "email": "viewer1@example.com",
      "first_name": "Viewer",
      "last_name": "One",
      "role": "VIEWER"
    }
  ]
}
```

#### Terraform Implementation - AWS (Create N Users)

```hcl
# Variable receives list of users from config_grafana.json
variable "grafana_users" {
  type = list(object({
    email      = string
    first_name = string
    last_name  = string
    role       = string  # ADMIN, EDITOR, VIEWER
  }))
  default = []
}

# Create each user in IAM Identity Center
resource "aws_identitystore_user" "grafana_users" {
  for_each = { for u in var.grafana_users : u.email => u }
  
  identity_store_id = local.identity_store_id
  display_name      = "${each.value.first_name} ${each.value.last_name}"
  user_name         = each.value.email
  
  name {
    given_name  = each.value.first_name
    family_name = each.value.last_name
  }
  
  emails {
    value   = each.value.email
    primary = true
  }
}

# Group users by role for assignment
locals {
  grafana_admins  = [for u in var.grafana_users : u.email if u.role == "ADMIN"]
  grafana_editors = [for u in var.grafana_users : u.email if u.role == "EDITOR"]
  grafana_viewers = [for u in var.grafana_users : u.email if u.role == "VIEWER"]
}

# Assign roles (one resource per role type)
resource "aws_grafana_role_association" "admins" {
  count        = length(local.grafana_admins) > 0 ? 1 : 0
  role         = "ADMIN"
  user_ids     = [for email in local.grafana_admins : aws_identitystore_user.grafana_users[email].user_id]
  workspace_id = aws_grafana_workspace.main[0].id
}

resource "aws_grafana_role_association" "editors" {
  count        = length(local.grafana_editors) > 0 ? 1 : 0
  role         = "EDITOR"
  user_ids     = [for email in local.grafana_editors : aws_identitystore_user.grafana_users[email].user_id]
  workspace_id = aws_grafana_workspace.main[0].id
}

resource "aws_grafana_role_association" "viewers" {
  count        = length(local.grafana_viewers) > 0 ? 1 : 0
  role         = "VIEWER"
  user_ids     = [for email in local.grafana_viewers : aws_identitystore_user.grafana_users[email].user_id]
  workspace_id = aws_grafana_workspace.main[0].id
}
```

#### Terraform Implementation - Azure (Lookup + Assign N Users)

```hcl
# Azure role names differ from AWS
# AWS: ADMIN, EDITOR, VIEWER
# Azure: Grafana Admin, Grafana Editor, Grafana Viewer

locals {
  azure_role_map = {
    "ADMIN"  = "Grafana Admin"
    "EDITOR" = "Grafana Editor"
    "VIEWER" = "Grafana Viewer"
  }
}

# Look up existing Entra ID users (Azure cannot create users)
data "azuread_user" "grafana_users" {
  for_each = { for u in var.grafana_users : u.email => u }
  mail     = each.value.email
}

# Assign roles to each user
resource "azurerm_role_assignment" "grafana_users" {
  for_each = { for u in var.grafana_users : u.email => u }
  
  scope                = azurerm_dashboard_grafana.main[0].id
  role_definition_name = local.azure_role_map[each.value.role]
  principal_id         = data.azuread_user.grafana_users[each.key].object_id
}
```

### Key Differences: AWS vs Azure

| Aspect | AWS | Azure |
|--------|-----|-------|
| **User Creation** | ✅ Creates new users in IAM Identity Center | ❌ Cannot create, must exist in Entra ID |
| **Roles** | `ADMIN`, `EDITOR`, `VIEWER` | `Grafana Admin`, `Grafana Editor`, `Grafana Viewer` |
| **User Lookup** | Not needed (we create the user) | Required via `data.azuread_user` |
| **Activation** | User receives email invitation | Immediate access via Entra ID |
| **Provider** | `aws` | `azuread` + `azurerm` |

### Validation Requirements

```python
def validate_grafana_n_users(ctx: ValidationContext) -> None:
    """Validate config_grafana.json for N-user support."""
    grafana_config = ctx.grafana_config.get("users", [])
    
    if not grafana_config:
        raise ValidationError("config_grafana.json must have at least one user")
    
    # Must have at least one admin
    admins = [u for u in grafana_config if u.get("role") == "ADMIN"]
    if not admins:
        raise ValidationError("At least one user must have role 'ADMIN'")
    
    # Validate email format for all users
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    for user in grafana_config:
        if not re.match(email_pattern, user.get("email", "")):
            raise ValidationError(f"Invalid email: {user.get('email')}")
        
        # Validate role enum
        if user.get("role") not in ["ADMIN", "EDITOR", "VIEWER"]:
            raise ValidationError(
                f"Invalid role '{user.get('role')}' for {user.get('email')}. "
                "Must be: ADMIN, EDITOR, or VIEWER"
            )
    
    # Check for duplicate emails
    emails = [u["email"] for u in grafana_config]
    if len(emails) != len(set(emails)):
        raise ValidationError("Duplicate email addresses in config_grafana.json")
```

### E2E Test Requirements

| Test Case | Description |
|-----------|-------------|
| `test_grafana_multiple_users_created` | Verify all users exist in IAM Identity Center (AWS) |
| `test_grafana_role_assignments_correct` | Each user has correct role in Grafana workspace |
| `test_grafana_user_lookup_azure` | All Entra ID users found successfully |
| `test_grafana_user_not_found_azure` | Clear error when user doesn't exist in Entra ID |
| `test_grafana_duplicate_emails_rejected` | Validation rejects duplicate emails |
| `test_grafana_invalid_role_rejected` | Validation rejects invalid role values |

### Integration with Optimizer

The optimizer already returns `amountOfActiveEditors` and `amountOfActiveViewers` in `inputParamsUsed`. Future enhancement:

1. **Validation alignment**: Warn if `config_grafana.json` user counts don't match optimizer input
2. **Auto-generation**: Consider generating placeholder config based on counts
3. **Cost verification**: Ensure actual provisioned users match billing expectations

### Files to Modify/Create

| File | Change Type | Description |
|------|-------------|-------------|
| `upload/template/config_grafana.json` | MODIFY | Update schema to array of users |
| `src/terraform/variables.tf` | MODIFY | Change `grafana_admin_*` to `grafana_users` list |
| `src/terraform/aws_grafana.tf` | MODIFY | Add `for_each` loop for N users |
| `src/terraform/azure_grafana.tf` | MODIFY | Add `for_each` loop for N users |
| `src/tfvars_generator.py` | MODIFY | Transform users array to terraform format |
| `src/validation/core.py` | MODIFY | Add N-user validation logic |
| `tests/unit/test_validation.py` | MODIFY | Add N-user test cases |
| `tests/e2e/*/test_*_e2e.py` | MODIFY | Add multi-user verification |

### Complexity Assessment

| Aspect | Effort |
|--------|--------|
| Config schema change | Low |
| Terraform for_each conversion | Medium |
| AWS multi-user creation | Medium |
| Azure user lookup handling | Medium |
| Error handling for missing users | High |
| E2E testing | Medium |
| **Total** | **~3-4 days** |

---

## 14. Deploy API Return Value Enhancement

### Status: Planned

### Problem

`deploy_all()` currently only returns Terraform outputs:

```python
def deploy_all(context, skip_credential_check=False) -> dict:
    return self._terraform_outputs  # Only infrastructure IDs/URLs
```

Post-deployment SDK operations (IoT registration, DTDL upload, TwinMaker entities, Grafana config) log warnings on failure but don't report status in the return value.

### Impact

- Callers cannot programmatically determine if SDK operations succeeded
- Must parse logs to determine full deployment status
- AWS fail-soft pattern silently degrades without structured notification

### Proposed Solution

Return structured result including SDK operation status:

```python
return {
    "terraform_outputs": {...},
    "sdk_operations": {
        "azure_dtdl_upload": {"success": True},
        "azure_iot_registration": {"success": True, "devices": 2},
        "azure_grafana_config": {"success": True},
        "aws_twinmaker_entities": {"success": True, "entities": 2, "failed": 0},
        "aws_iot_devices": {"success": True, "devices": 2, "failed": 0},
        "aws_grafana_config": {"success": True}
    }
}
```

### Files to Modify

| File | Change |
|------|--------|
| `deployer_strategy.py` | Capture SDK results, modify return |
| `azure_deployer.py` | Return status from each function |
| `aws_deployer.py` | Return status from each function |

### Complexity Assessment

| Aspect | Effort |
|--------|--------|
| Return type change | Low |
| Azure deployer updates | Medium |
| AWS deployer updates | Medium |
| Unit test updates | Medium |
| **Total** | **~1-2 days** |

---

## 15. Automated IAM Identity Center (SSO) Setup via SDK

> [!NOTE]
> Research completed December 2024. Implementation deferred pending priority assessment.

### Status: Research Complete, Not Implemented

### Background

AWS Managed Grafana requires IAM Identity Center (SSO) to be enabled. Currently, users must enable this manually via the AWS Console before deploying L5 Grafana on AWS. However, the AWS SDK (`boto3`) supports programmatic instance creation via the `sso-admin` client.

### Research Findings

**SDK API Available:**

```python
import boto3

# Create SSO-Admin client in desired region
client = boto3.client('sso-admin', region_name='eu-central-1')

# Create IAM Identity Center instance
try:
    response = client.create_instance(
        Name='digital-twin-deployer',  # Optional friendly name
        Tags=[
            {'Key': 'ManagedBy', 'Value': 'terraform'},
            {'Key': 'Application', 'Value': 'digital-twin-deployer'}
        ]
    )
    instance_arn = response['InstanceArn']
    print(f"Created SSO instance: {instance_arn}")
except client.exceptions.ConflictException:
    # Instance already exists - this is fine
    print("IAM Identity Center already enabled")
except client.exceptions.AccessDeniedException:
    print("ERROR: Insufficient permissions to create SSO instance")
```

**Key Constraints:**
- Only **ONE** instance allowed per AWS account
- Instance is **region-specific** (cannot be moved, only deleted and recreated)
- Terraform cannot create instances - only AWS SDK/CLI can
- If instance exists in different region, SDK cannot detect or use it

### Proposed Implementation

#### 1. Pre-Deployment Check (Python)

Add to `src/validation/aws_checks.py`:

```python
def ensure_sso_enabled(region: str, credentials: dict) -> tuple[bool, str]:
    """
    Ensure IAM Identity Center is enabled in the specified region.
    
    Returns:
        tuple: (success, identity_store_id or error_message)
    """
    import boto3
    
    client = boto3.client(
        'sso-admin',
        region_name=region,
        aws_access_key_id=credentials['aws_access_key_id'],
        aws_secret_access_key=credentials['aws_secret_access_key']
    )
    
    # Check if instance exists
    response = client.list_instances()
    if response['Instances']:
        instance = response['Instances'][0]
        return True, instance['IdentityStoreId']
    
    # Try to create instance
    try:
        response = client.create_instance(Name='digital-twin-sso')
        # Wait for creation and get identity store ID
        return True, response['IdentityStoreId']
    except client.exceptions.AccessDeniedException:
        return False, "Insufficient permissions to create IAM Identity Center"
    except Exception as e:
        return False, f"Failed to create SSO instance: {e}"
```

#### 2. Integration Point

Call from `src/providers/aws/validator.py` before Terraform runs:

```python
if layer_5_provider == "aws":
    success, result = ensure_sso_enabled(
        region=credentials['aws_sso_region'] or credentials['aws_region'],
        credentials=credentials
    )
    if not success:
        raise ValidationError(f"Cannot enable AWS Grafana: {result}")
```

### Required IAM Permissions

Add to the deployer IAM policy (`docs/references/aws_policy.json`):

```json
{
    "Effect": "Allow",
    "Action": [
        "sso:CreateInstance",
        "sso:ListInstances",
        "sso:DescribeInstance"
    ],
    "Resource": "*"
}
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| No instance exists | Create new instance in `aws_sso_region` |
| Instance exists in same region | Use existing (return identity_store_id) |
| Instance exists in different region | **Cannot detect** - SDK only sees current region |
| Insufficient permissions | Clear error message, user must create manually |

### Files to Modify

| File | Change |
|------|--------|
| `src/validation/aws_checks.py` | Add `ensure_sso_enabled()` function |
| `src/providers/aws/validator.py` | Call SSO check before Terraform |
| `docs/references/aws_policy.json` | Add SSO permissions |
| `docs/docs-credentials-aws.html` | Update to explain auto-creation |

### Complexity Assessment

| Aspect | Effort |
|--------|--------|
| SDK implementation | Low |
| Integration with validator | Low |
| IAM policy update | Low |
| Documentation update | Low |
| Error handling for region mismatch | Medium |
| **Total** | **~0.5 day** |

---

## 16. Legacy `globals.py` Cleanup

> [!WARNING]
> `src/globals.py` contains deprecated config loading patterns that bypass the centralized `config_loader.py`.

### Status: Pending

### Problem

The legacy `globals.py` file loads configs directly from files:

```python
# src/globals.py (lines 48-73) - DEPRECATED PATTERN
with open(f"{project_path()}/config.json", "r") as file:
with open(f"{project_path()}/config_iot_devices.json", "r") as file:
with open(f"{project_path()}/config_events.json", "r") as file:
with open(f"{project_path()}/config_hierarchy.json", "r") as file:
with open(f"{project_path()}/config_credentials.json", "r") as file:
with open(f"{project_path()}/config_providers.json", "r") as file:
```

This creates a **global mutable state anti-pattern** that bypasses the modern `ProjectConfig` / `DeploymentContext` pattern.

### Risk

- Multiple sources of truth for configuration
- Global state makes testing difficult
- State can be inadvertently mutated between calls

### Tasks

- [ ] Audit all usages of `globals.py` functions
- [ ] Migrate callers to use `DeploymentContext`
- [ ] Deprecate and remove `globals.py`

---

## 17. Unified Config Loading via Context

> [!NOTE]
> Multiple subsystems load configs independently. Consider unifying to single source of truth.

### Status: Architectural Improvement

### Current State

| Component | Loading Pattern | Context Available? |
|-----------|-----------------|-------------------|
| `config_loader.py` → `ProjectConfig` | Centralized | ✅ Source of truth |
| `tfvars_generator.py` | File-based | ❌ Standalone CLI tool |
| `deployer_strategy._load_providers_config()` | File-based | Pre-context |
| `deployer_strategy._load_credentials()` | File-based | Pre-context |
| `validation/core.py` → `ValidationContext` | File-based | Separate validation |
| `globals.py` | File-based | Legacy |

### Ideal Architecture

```
                    ┌─────────────────┐
                    │ config_loader.py │
                    │ (Single Source) │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
    ┌──────────────┐  ┌────────────┐  ┌──────────────┐
    │ Validation   │  │ tfvars     │  │ Deployment   │
    │ Pipeline     │  │ Generator  │  │ Context      │
    └──────────────┘  └────────────┘  └──────────────┘
```

### Tasks

- [ ] Refactor `tfvars_generator.py` to accept `ProjectConfig` instead of loading files
- [ ] Remove `_load_providers_config()` and `_load_credentials()` from `deployer_strategy.py`
- [ ] Unify `ValidationContext` with `ProjectConfig` or document separation clearly
- [ ] Update all callers to use centralized loading

### Complexity Assessment

| Aspect | Effort |
|--------|--------|
| tfvars_generator refactor | Medium |
| deployer_strategy cleanup | Low |
| ValidationContext unification | High |
| Test updates | Medium |
| **Total** | **~3-4 days** |

---

## Notes

- **Priority**: GCP Simulator > L0 Optimization > SDK validation > N-User Grafana > SSO Automation > Config Unification > Legacy Cleanup > Security enhancements
- **Timeline**: To be determined based on thesis requirements
