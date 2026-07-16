# Google Cloud Setup

## Tools And Project Context

`bootstrap/gcp/bootstrap_deployment_identity.sh` uses the Google Cloud CLI. Distinguish:

- an existing project where a service account is created;
- organization/billing authority needed to create or attach a new project;
- the deployment service account imported into Twin2MultiCloud.

The generated auth type is `service_account_key`; the JSON is stored as one encrypted
CloudConnection payload. Project/billing metadata is not a substitute for the required
service-account key under the current auth contract.

## Workflow

```bash
bash bootstrap/gcp/bootstrap_deployment_identity.sh --help
# review the dry-run plan and explicit project/billing scope
# use --apply only in the intended gcloud account/configuration
```

Existing user-managed keys require `--rotate-service-account-keys` before destructive
replacement. Workload identity is a preferred long-term direction, but the current
CloudConnection import explicitly does not support it.

## Pricing Versus Deployment

Google Cloud pricing discovery may require project/catalog context and can be slower
than the other providers. Refresh is therefore provider-specific and asynchronous.
Project creation, service enablement, IAM, Cloud Functions, Firestore/Storage, and
deployment execution require broader but still reviewed permissions.

## Verification Status

Schema validation, permission inventory, preflight adapters, pricing fixtures, and GCP
tier tests are implemented. GCP L4/L5 equivalence and selected cross-cloud functions
remain limited. Final policy completeness requires supervised project-level evidence.
