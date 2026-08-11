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
Project creation, service enablement, IAM, GKE/Cloud Run for Five-layer v2
(Cloud Functions only for retained historical paths), Firestore/Storage, and
deployment execution require broader but still reviewed permissions.

## Verification Status

Schema validation, permission inventory, preflight adapters, pricing fixtures,
GCP tier tests, and the closed-world Five-layer v2 GCP L1-L5 packages are
implemented offline. Final policy, quota, browser-access, and capacity
completeness still require supervised project-level evidence and therefore
block deployment selection.

The active Five-layer v2 profile uses BifroMQ on GKE as the MQTT/command device
boundary while retaining Pub/Sub as the durable cloud backbone, Firestore
Native Standard edition with timestamp shards as L3 hot history, a typed Cloud
Run reader, a bounded Cloud Run Twin API, and Grafana on GKE as L5. When GCP
owns both L3 and L4, their separate collections and identities share the one
deployment Firestore database; the database-wide IAM boundary is a documented
PoC limitation. The historical Pub/Sub-direct simulator and retired
`google.cloud.iot_v1` feedback template do not prove this target. BigQuery,
Spanner Graph, and a dedicated Grafana node pool are not part of it.
