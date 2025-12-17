# GCP Terraform Custom IAM Role Implementation

## 1. Executive Summary

### The Problem
GCP Terraform configuration used predefined roles (e.g., `roles/pubsub.editor`) assigned individually. This was:
1. Less secure (overly broad permissions)
2. Inconsistent with the custom role YAML provided in documentation

### The Solution
Implement `google_project_iam_custom_role` in Terraform with least-privilege permissions, replacing individual predefined role assignments.

### Impact
- **Security:** Functions now get only the exact permissions needed
- **Consistency:** Terraform automatically creates the same custom role documented for manual setup
- **Simpler Dependencies:** One custom role binding instead of 4 separate role bindings

---

## 2. Proposed Changes

### Component: Terraform

#### [x] [MODIFY] gcp_setup.tf
- **Path:** `src/terraform/gcp_setup.tf`
- **Description:** 
  - Added `google_project_iam_custom_role.functions_role` with 20 least-privilege permissions
  - Added `google_project_iam_member.functions_custom_role` binding
  - Removed individual role bindings: `functions_pubsub`, `functions_firestore`, `functions_storage`, `functions_run_invoker`

```hcl
resource "google_project_iam_custom_role" "functions_role" {
  count       = local.deploy_gcp ? 1 : 0
  project     = var.gcp_project_id
  role_id     = "${replace(var.digital_twin_name, "-", "_")}_functions_role"
  title       = "${var.digital_twin_name} Functions Role"
  description = "Custom role for Digital Twin Cloud Functions"
  stage       = "GA"

  permissions = [
    # Pub/Sub (L1)
    "pubsub.topics.get",
    "pubsub.topics.publish",
    "pubsub.subscriptions.consume",
    "pubsub.subscriptions.get",

    # Firestore (L3 Hot)
    "datastore.entities.create",
    "datastore.entities.delete",
    "datastore.entities.get",
    "datastore.entities.list",
    "datastore.entities.update",

    # Cloud Storage (L3 Cold/Archive)
    "storage.objects.create",
    "storage.objects.delete",
    "storage.objects.get",
    "storage.objects.list",

    # Cloud Run (Function invocation)
    "run.routes.invoke",
  ]
}
```

#### [x] [MODIFY] gcp_iot.tf
- **Path:** `src/terraform/gcp_iot.tf`
- **Description:** Updated `depends_on` from `google_project_iam_member.functions_pubsub` to `google_project_iam_member.functions_custom_role`

#### [x] [MODIFY] gcp_compute.tf
- **Path:** `src/terraform/gcp_compute.tf`
- **Description:** Updated `depends_on` references in processor and persister functions

#### [x] [MODIFY] gcp_storage.tf
- **Path:** `src/terraform/gcp_storage.tf`
- **Description:** Updated `depends_on` references in hot_reader and hot_to_cold_mover functions

---

## 3. Verification Checklist

- [x] `terraform validate` passes
- [x] All depends_on references updated
- [x] Documentation updated with Terraform automatic note

---

## 4. Design Decisions

### Least Privilege
The custom role includes only the specific permissions needed by Cloud Functions at runtime:
- Publishing to Pub/Sub topics (not creating/deleting)
- Reading/writing Firestore entities (not creating databases)
- Reading/writing Storage objects (not managing buckets)
- Invoking Cloud Run services

### Role ID Format
Role ID uses `${replace(var.digital_twin_name, "-", "_")}_functions_role` since GCP role IDs cannot contain hyphens.

### Single Role Binding
Using one custom role binding instead of 4 predefined role bindings simplifies dependencies and ensures atomic permission updates.
