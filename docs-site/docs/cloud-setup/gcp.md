# Google Cloud Setup

## Prerequisites

- Use an existing isolated Google Cloud project with billing already attached.
- Create one non-human service account in that project and grant only the roles
  required by the resolved Six-layer graph.
- Create a JSON key only when the project policy permits it. Workload Identity
  Federation is preferable outside this PoC, but the current CloudConnection
  contract intentionally accepts one service-account JSON document.
- Select the primary Region before validation.

Project creation, billing repair, organization-policy exemptions, quota approval,
OAuth/IAP consent configuration, and key lifecycle remain external operations.

## Enter or import

In **Settings → Cloud access → GCP** choose one path:

- **Enter manually:** project ID, Region, and the service-account JSON through
  the write-only file control.
- **Import JSON:** one standard Google service-account JSON plus typed project ID
  and Region. File contents are never previewed.

The project ID in the JSON must match the selected target project. Do not store
the private key in the repository, evidence, screenshots, or logs.

## Validation and bounded preparation

Before binding the connection, confirm that readiness reports:

1. the expected service account and project;
2. usable billing and required IAM permissions;
3. graph-required APIs and Region availability;
4. quota and capacity headroom for the selected Small scenario;
5. L4 IAP/OAuth prerequisites separately from L1–L3 and eventing.

Twin2MultiCloud may propose enabling only the APIs required by the immutable
graph. The exact digest-bound plan is shown first and requires explicit
confirmation. API enablement is shared project state and is not reversed by Twin
Destroy. No project, billing account, OAuth client, organization policy, or quota
change is created automatically.

## Cleanup and revocation

After every run, Destroy Twin-owned resources and inspect residual inventory.
After the final evaluation, unbind and delete the CloudConnection, delete the
service-account key, and review or remove the service account and its project
roles. Shared APIs remain enabled unless the operator deliberately disables them.

See the official [Google Cloud references](provider-links.md#gcp).
