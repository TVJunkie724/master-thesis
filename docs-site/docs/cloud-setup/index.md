# Cloud Setup

Cloud setup is one of the most fragile parts of the platform because the original projects expected broad local credentials and provider-specific manual setup. The thesis version should make cloud access explicit, reproducible, and least-privilege where possible.

## Setup Model

Each provider setup should document:

- required cloud account and billing prerequisites,
- APIs or services that must be enabled,
- one-time bootstrap permissions,
- generated deployment identity permissions,
- local development behavior,
- failure symptoms when a required provider step is missing.

The intended app workflow is Cloud Connections: a user creates or imports a provider connection, the Management API stores it as user-scoped secret material, and deployments reference that connection instead of reading random files from the workspace.

Encrypted per-twin legacy credential columns may still exist in old local databases, but they are no longer an active runtime source. Use `python -m migrations.disable_legacy_twin_credentials` for an explicit cleanup of duplicated per-twin secret columns after upgrading a local database.

## Provider Overview

| Provider | Setup focus | Important caveat |
|----------|-------------|------------------|
| AWS | IAM credentials, pricing API access, IoT Core, Lambda, DynamoDB, S3, API Gateway, TwinMaker, Managed Grafana | Managed Grafana setup depends on IAM Identity Center in the deployment region. |
| Azure | App registration/service principal, subscription access, Functions, Cosmos DB, Blob Storage, API Management, Digital Twins, Managed Grafana | Function hosting choices matter because Linux Consumption is being retired for Azure Functions. |
| GCP | project, billing, service account, enabled APIs, Pub/Sub, Cloud Functions, Firestore, Cloud Storage, API Gateway, Scheduler, Workflows | GCP currently supports the lower deployment layers; managed Digital Twin and Grafana equivalents are not first-class in the same way as AWS/Azure. |

The old documentation has two GCP paths: private account setup using an existing project, and organization setup where Terraform can create a project for a deployment. The current app should present that as an explicit setup choice, not as hidden provider behavior.

## Bootstrap Credentials

Bootstrap/admin credentials are temporary setup material. They may be used to create a constrained deployment identity for a provider, but they should not remain readable in the app and should not be persisted as the regular deployment credential.

The intended flow for creating a new deployment identity is:

1. User starts provider setup from the app.
2. User supplies temporary bootstrap/admin material for that provider.
3. The backend runs a provider-specific bootstrap script that creates or verifies the least-privilege deployment identity.
4. The generated deployment identity is stored as a Cloud Connection.
5. Bootstrap/admin material is discarded and is not available for later reads.

Real credential values must never be committed or pasted into documentation. Examples should use placeholders or schema-only files.

## Bootstrap Artifacts

The first repeatable setup slice lives in `bootstrap/` at the repository root.
It is intentionally manual-first: the scripts run in dry-run mode by default,
require `--apply` before mutating cloud resources, verify the active provider
account/project/subscription, and emit JSON that matches the current
CloudConnection create contract.

| Provider | Script | Output auth type |
|----------|--------|------------------|
| AWS | `bootstrap/aws/bootstrap_deployment_identity.sh` | `access_key` |
| Azure | `bootstrap/azure/bootstrap_deployment_identity.sh` | `service_principal` |
| GCP | `bootstrap/gcp/bootstrap_deployment_identity.sh` | `service_account_key` |

The active deployment permission baseline is `thesis-demo-v1`. Bootstrap output
includes this as `permission_set_version`, and the Management API stores it as
non-secret CloudConnection metadata. Deployment preflight compares the stored
version with the active Deployer baseline before a deployment starts.

If a CloudConnection has no version metadata, or carries an older version,
preflight returns `OUTDATED_PERMISSION_SET`. The fix is to re-run provider
bootstrap, rotate/import the generated CloudConnection, and then rerun
preflight. This is intentionally conservative: old credentials may still
authenticate, but they are not auditable against the current thesis deployment
permission contract.

The generated output file is local secret material. It can be pasted/imported
into the CloudConnection API/UI during supervised setup, then removed locally.
Do not commit generated output files.

The scripts also refuse silent key sprawl: existing AWS access keys, Azure
client secrets, and GCP service-account keys require explicit rotation flags
before a new deployment secret is generated.

The provider permission artifacts are covered by offline guardrail tests. Those
tests compare the AWS policy, Azure custom role, and GCP custom role against the
permission sets enforced by the Deployer's credential/preflight checkers. This
keeps the documented setup path and runtime readiness checks aligned without
requiring live cloud credentials in the default test suite.

The versioned permission-set artifacts live in
`3-cloud-deployer/docs/references/permission_sets/`:

| Provider | Permission-set artifact | Native source artifact |
|----------|-------------------------|------------------------|
| AWS | `aws_thesis_demo_v1.json` | `aws_deployer_policy.json` |
| Azure | `azure_thesis_demo_v1.json` | `azure_custom_role.json` |
| GCP | `gcp_thesis_demo_v1.json` | `gcp_custom_role.yaml` |

`deployer_permission_inventory.json` records the Terraform provider resource
types that feed this baseline. Offline tests compare that inventory to the
current Terraform files so new resource families cannot silently appear without
updating the permission-set documentation.

For AWS, the v1 baseline now also includes an explicit pre-E2E scope review in
`aws_thesis_demo_v1_scope_review.json`. It classifies each IAM policy statement
as globally required, a prefix-scoping candidate, or condition-constrained.
This caught the CloudWatch Logs gap for Terraform-managed
`aws_cloudwatch_log_group` resources before live E2E validation. The policy now
includes the CloudWatch Logs actions needed to create, tag, retain, inspect,
and delete those log groups.

`thesis-demo-v1` is the first validated thesis/demo baseline. It is not a
claim that every provider action is already the final least-privilege shape.
The artifacts explicitly document known broad areas such as AWS `Resource: *`,
Azure `*/read`, subscription-scope role assignment, and GCP API-enablement /
custom-role mutation permissions. The next hardened version can remove those
gaps after supervised live deployments and provider-operation validation. The
AWS next step is to run IAM Access Analyzer validation and a supervised
deployment/destroy smoke before producing `least-privilege-v2`.

The Management API exposes the first stable contract for this flow:

- `POST /cloud-bootstrap/{provider}/plan` returns the manual bootstrap command
  set for AWS, Azure, or GCP. It does not execute cloud CLIs and does not accept
  admin secrets.
- `POST /cloud-bootstrap/import` imports generated bootstrap output as a normal
  CloudConnection and returns only the masked CloudConnection read model.
- `POST /cloud-connections/{connection_id}/preflight` runs the existing
  Optimizer/Deployer validation path and returns normalized, UI-actionable
  checks without persisting validation status. It also reports
  `expected_permission_set_version`, `supplied_permission_set_version`, and
  `permission_set_status`.
- `POST /permissions/preflight/{provider}` on the Deployer normalizes provider
  permission, API, billing, region, and secret-expiration failures for AWS,
  Azure, and GCP, and rejects missing or stale permission-set metadata with
  `OUTDATED_PERMISSION_SET`.

## Provider Material

The provider pages are migrated from the original optimizer and deployer docs as the setup flows are cleaned up. Start with [Provider Links](provider-links.md) for cloud-console, API, and pricing references that are already used by the platform.
