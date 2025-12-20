# GCP Dual-Mode Support: Auto-Create vs Existing Project

## Problem
Users without a GCP organization cannot grant `roles/resourcemanager.projectCreator`. GCP documentation states: *"Service accounts are not allowed to create projects outside of an organization resource."*

## Solution
Support two modes:
1. **Auto-Create Mode**: Provide `gcp_billing_account` → Terraform creates `{twin-name}-project`
2. **Existing Project Mode**: Provide `gcp_project_id` → Use existing project

Validation: At least one of `gcp_billing_account` OR `gcp_project_id` must be provided.

---

## Proposed Changes

### Terraform (~30 lines changed)

#### [MODIFY] [variables.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/variables.tf)
- Add `gcp_project_id` variable (optional, default = "")
- Make `gcp_billing_account` optional (default = "")

#### [MODIFY] [gcp_setup.tf](file:///d:/Git/master-thesis/3-cloud-deployer/src/terraform/gcp_setup.tf)
- Add local: `gcp_use_existing_project = var.gcp_project_id != ""`
- Add local: `gcp_project_id = local.gcp_use_existing_project ? var.gcp_project_id : google_project.main[0].project_id`
- Modify `google_project.main` count: `count = local.deploy_gcp && !local.gcp_use_existing_project ? 1 : 0`
- Add `data "google_project" "existing"` for existing project mode

**KEY INSIGHT**: All 50+ references use `google_project.main[0].project_id`. By changing them to use `local.gcp_project_id`, we only need to update the local definition, NOT all 50+ references.

---

### Python Files (~20 lines changed)

#### [MODIFY] [constants.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/constants.py)
- Add `gcp_project_id` to GCP optional fields

#### [MODIFY] [credentials.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/api/credentials.py)
- Make `gcp_billing_account` optional (default = None)
- Add optional `gcp_project_id` field

#### [MODIFY] [tfvars_generator.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/tfvars_generator.py)
- Update validation: require either `gcp_billing_account` OR `gcp_project_id`
- Pass through `gcp_project_id` to tfvars

#### [MODIFY] [gcp_credentials_checker.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/api/gcp_credentials_checker.py)
- Update validation logic for dual-mode

#### [MODIFY] [validator.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/validator.py)
- Update required fields check

---

### Documentation (Two Separate Pages)

#### [NEW] [docs-credentials-gcp-private.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-credentials-gcp-private.html)
**"GCP Setup for Private Accounts"** - For personal Gmail accounts without an organization:
1. Get your existing project ID
2. Create service account in that project
3. Grant IAM roles to the SA (in the project)
4. Download key & configure

#### [MODIFY] [docs-credentials-gcp.html](file:///d:/Git/master-thesis/3-cloud-deployer/docs/docs-credentials-gcp.html) → rename to `docs-credentials-gcp-org.html`
**"GCP Setup for Organization Accounts"** - For Google Workspace/Cloud Identity users:
- Auto-creates new projects (current structure)
- Requires org-level permissions

---

## Estimated Effort
| Component | Files | Lines Changed |
|-----------|-------|---------------|
| Terraform | 2 | ~30 |
| Python | 5 | ~40 |
| Docs | 2 | ~150 |
| **Total** | **9** | **~220** |

## Verification Plan
1. Test existing project mode: deploy with `gcp_project_id` only
2. Test auto-create mode: deploy with `gcp_billing_account` only  
3. Test validation: error when neither is provided
4. Run unit tests
