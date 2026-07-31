---
title: "Phase 8 Five-Layer v2 Layer Access Handoff"
description: "Feasibility and implementation boundary for usable post-deployment L4 and L5 browser access."
tags: [architecture, flutter, deployment, identity, digital-twin, grafana, phase-8]
lastUpdated: "2026-07-31"
version: "1.0"
---

<!-- SOURCES:
- phase_08_service_bundle_closure.md
- phase_08_service_bundle_evaluation.md
- phase_08_6_deployer_graph_resolver.md
- phase_08_7_flutter_profile_workflow.md
- Current Management deployment-output and Twin Overview contracts
- Primary AWS, Azure, GCP, and Grafana documentation listed in Section 12
- User-approved PoC boundary: inspect both L4 and L5 after deployment, keep L4
  independent from the provider-local L3-hot/L5 bundle, and avoid unjustified
  production infrastructure
EXTRACTED: 2026-07-31 | VERSION: 1.0
-->

# Phase 8 Five-Layer v2 Layer Access Handoff

## 0. Decision And Scope

This document records the missing post-deployment requirement for
`five-layer-baseline@2` and closes its feasibility boundary before
implementation:

1. a successful deployment must expose one usable L4 browser surface and one
   usable L5 browser surface in Twin Overview;
2. each surface must show its provider, service, link, authentication method,
   bound interactive principal, readiness, and limitations;
3. L4 must contain a deterministic semantic Twin sample; L5 must contain a
   deterministic raw/rollup dashboard;
4. L4 and L5 remain independent views. L4 shows semantic current state and
   relationships. L5 shows L3 raw history and hourly rollups. Five-layer v2
   still has no L4-to-L5, scene, or 3D claim;
5. Flutter talks only to the Management API. It never reads Terraform state,
   calls a cloud API, or calls the Deployer directly;
6. deployment credentials and browser identities are different concerns. A
   technically created resource is not reported as accessible until an
   interactive principal is bound;
7. the requirement applies to all three single-cloud placements and all six
   `L3-hot == L5 != L4` placements;
8. Six-layer planning remains deferred. It must inherit this L1-L5 access
   contract unchanged when it is replanned.

This is PoC infrastructure, not an enterprise access portal. It adds only the
smallest provider support needed to inspect the two scientific layers. Custom
scene plugins, multi-tenant RBAC administration, high availability, custom
domains, and automated browser login are outside scope.

## 1. Feasibility Result

The target is feasible with one important qualification: cloud sign-in cannot
be manufactured from the API credentials used for deployment. The user must
already have, or activate, the selected provider's interactive identity
facility. Terraform can then bind that principal to the deployed L4/L5
resources.

| Requirement | Result | Boundary |
|---|---|---|
| L4 browser UI on AWS | Feasible | IoT TwinMaker console deep link plus an IAM Identity Center account assignment and read-only TwinMaker permission set |
| L4 browser UI on Azure | Feasible | Azure Digital Twins Explorer deep link plus `Azure Digital Twins Data Reader` |
| L4 browser UI on GCP | Feasible with one support service | Read-only Twin Explorer on a separate Cloud Run service protected by direct IAP |
| L5 browser UI on AWS | Feasible | Amazon Managed Grafana workspace URL and IAM Identity Center workspace association |
| L5 browser UI on Azure | Feasible | Azure Managed Grafana endpoint and Azure RBAC assignment |
| L5 browser UI on GCP | Feasible | Existing Grafana OSS/GKE TLS endpoint plus a generated human Viewer credential |
| Universal unattended identity bootstrap | Not feasible | AWS Identity Center and first-time/no-organization GCP IAP setup can require account-owner action; deployment preflight must expose and block on that prerequisite |
| Offline proof of browser sign-in | Not possible | Offline tests prove contracts and bindings only; a supervised live run proves the actual sign-in |

The selected GCP Twin Explorer is deliberately a second Cloud Run service,
not a second Twin implementation. The existing L4 materializer/API continues
to receive machine traffic through its workload identity. The explorer reuses
the same image and read model but exposes read-only routes behind IAP. This
separation prevents interactive IAP from blocking projection/materialization
traffic and both services can scale to zero.

## 2. Exact Post-Deployment Surfaces

### 2.1 L4 Semantic Twin

| Provider | Selected surface | What the researcher can inspect | Human authentication |
|---|---|---|---|
| AWS | IoT TwinMaker console opened at the deployed workspace | Workspace, models/component types, entities, current component state, and relationships | Existing IAM Identity Center user/group receives an account assignment with a generated deployment-scoped read-only permission set |
| Azure | Azure Digital Twins Explorer opened at the deployed instance | Models, twins, properties, graph relationships, and bounded queries | Existing Microsoft Entra principal receives `Azure Digital Twins Data Reader` on the instance |
| GCP | Minimal read-only Twin Explorer on Cloud Run | Model list, twin list/detail, current source state, and direct incoming/outgoing relationships | Existing Google principal receives `roles/iap.httpsResourceAccessor` on the explorer service |

The GCP explorer must not become a general Firestore console or arbitrary
query builder. Its server routes accept only the bounded `Twin by ID`, `model
lookup`, and one-hop relationship queries already selected for L4. It never
returns L3 telemetry collections.

### 2.2 L5 Raw And Rollup Visualization

| Provider | Selected surface | Provisioned content | Human authentication |
|---|---|---|---|
| AWS | Amazon Managed Grafana 12 workspace | One versioned `Twin2MultiCloud Raw & Rollups` folder/dashboard using the typed DynamoDB reader | The selected IAM Identity Center principal is associated with the workspace. The first PoC operator is `ADMIN` because Amazon Managed Grafana requires an administrator; additional study users are `VIEWER` |
| Azure | Azure Managed Grafana 12 workspace | The same logical folder/dashboard using the typed Cosmos reader | Existing Entra principal receives `Grafana Viewer`; provisioning stays on the workspace managed identity/automation path |
| GCP | Grafana OSS 12 on GKE | The same logical folder/dashboard using the typed Firestore reader and signed Infinity datasource | A deployment-scoped human Viewer account; the provisioning Admin credential remains internal and is never returned |

The dashboard exists immediately after deployment even if no device telemetry
has arrived yet. Empty panels display a bounded no-data state. The existing
test-message utility is the explicit way to create demonstrable telemetry; it
is not part of deployment success.

## 3. Interactive Access Inputs

The configuration workspace must collect or select only the principals needed
by the resolved L4 and L5 providers. It does not ask for browser passwords.

| Provider | Safe configuration fields | Secret field | Preflight condition |
|---|---|---|---|
| AWS | Identity Center instance ARN, identity-store ID, principal type, principal ID, account ID, display label | None | Instance/principal exists; deployer principal may create permission sets, account assignments, and Grafana associations |
| Azure | Entra object ID and display label/UPN | None | Principal exists; deployer principal may assign ADT/Grafana roles |
| GCP L4 | Google principal (`user:` or approved `group:` member) | None | Direct Cloud Run IAP is already initialized for the project or can be enabled automatically; an out-of-organization/no-organization user completes the documented first-time Cloud Console OAuth setup before preflight |
| GCP L5 | Human Viewer username; default is deterministic and deployment-scoped | None before deploy | Deployer can create/rotate the Viewer credential inside the Grafana deployment |

One provider can own both L4 and L5. The same interactive principal is reused
inside that provider, but the two resource-role bindings remain distinct. In a
two-provider placement the configuration requires one interactive principal
for each involved provider. L3 alone adds no browser identity requirement.

The platform must not create AWS, Entra, or Google user accounts silently.
Account invitations, MFA, password recovery, and organization membership stay
with the provider identity system. Preflight returns a specific remediation
link/status when that external prerequisite is missing.

## 4. All Nine L3/L4/L5 Placements

`provider(L3_hot) == provider(L5)` remains mandatory. Layer access is resolved
from L4 and L5 independently:

| Placement | L4 access | L5 access | Required interactive identities |
|---|---|---|---|
| AWS L3/L5 + AWS L4 | TwinMaker console | Amazon Managed Grafana | One AWS Identity Center principal, two bindings |
| AWS L3/L5 + Azure L4 | ADT Explorer | Amazon Managed Grafana | Azure Entra plus AWS Identity Center |
| AWS L3/L5 + GCP L4 | GCP Twin Explorer | Amazon Managed Grafana | Google/IAP plus AWS Identity Center |
| Azure L3/L5 + AWS L4 | TwinMaker console | Azure Managed Grafana | AWS Identity Center plus Azure Entra |
| Azure L3/L5 + Azure L4 | ADT Explorer | Azure Managed Grafana | One Azure Entra principal, two bindings |
| Azure L3/L5 + GCP L4 | GCP Twin Explorer | Azure Managed Grafana | Google/IAP plus Azure Entra |
| GCP L3/L5 + AWS L4 | TwinMaker console | GCP Grafana | AWS Identity Center plus generated GCP Grafana Viewer |
| GCP L3/L5 + Azure L4 | ADT Explorer | GCP Grafana | Azure Entra plus generated GCP Grafana Viewer |
| GCP L3/L5 + GCP L4 | GCP Twin Explorer | GCP Grafana | Google/IAP plus generated GCP Grafana Viewer |

The single-cloud rows are not shortcuts. They execute the same provider role,
content, link, and readiness logic as the mixed rows. Mixed rows do not add a
browser bridge: each link opens its owning provider directly.

## 5. One GCP Firestore Database Per Deployment

The PoC uses one named Firestore Native database per deployment, not one per
GCP layer. The database contains only the collections selected by the resolved
placement:

```text
L3 selected on GCP:
  telemetry/{...}
  hourly_rollups/{...}

L4 selected on GCP:
  models/{...}
  twins/{...}
  twins/{...}/sources/{...}
  relationships/{...}
```

Consequences:

- GCP-only L3 or GCP-only L4 still creates one database;
- all-GCP L3/L4 creates the same one database with both collection groups;
- indexes, collection prefixes, code paths, logical component IDs, operation
  pricing, and cost attribution stay separate;
- this removes an unnecessary second database resource from the PoC without
  changing the selected scientific service family.

The tradeoff must be explicit: Firestore server libraries bypass Security
Rules and use IAM, and the relevant IAM boundary is the database rather than a
collection. When both layers share the database, their runtime service
accounts are distinct but technically receive database-wide data-plane
permissions. The application allowlists collection prefixes and query shapes,
but that is not equivalent to collection-level IAM isolation. This residual
risk is accepted for the PoC. A later production profile may restore two
databases if strict L3/L4 runtime isolation becomes a requirement.

## 6. Typed Management Contract

Generic Terraform outputs remain available as technical evidence, but they
must not drive the new UI. Add an owner-scoped, secret-free read model:

```text
GET /twins/{twin_id}/deployment-access
  -> deployment-access.v1
```

Minimum response shape:

```json
{
  "schema_version": "deployment-access.v1",
  "twin_id": "...",
  "deployment_id": "...",
  "generated_at": "...",
  "availability": "available|unsupported",
  "reason_code": null,
  "surfaces": [
    {
      "layer": "l4",
      "provider": "aws|azure|gcp",
      "service_id": "...",
      "display_name": "...",
      "url": "https://...",
      "auth": {
        "mode": "aws_identity_center|azure_entra|gcp_iap|generated_viewer",
        "principal_label": "...",
        "credential_action": "none|rotate"
      },
      "readiness": {
        "resource": "ready|failed|pending",
        "access_binding": "ready|blocked|pending",
        "content": "ready|failed|pending",
        "data_probe": "ready|failed|pending",
        "browser_sign_in": "unverified|verified|failed"
      },
      "capabilities": ["..."],
      "limitations": ["..."]
    }
  ]
}
```

Validation is fail closed:

- an `available` Five-layer v2 response contains exactly one L4 and one L5
  entry and no reason code;
- an `unsupported` historical response contains zero surfaces and one safe
  stable reason code;
- `url` is absolute HTTPS and matches the selected provider/service output;
- auth modes are provider/service compatible;
- no password, token, Function key, reader key, private certificate, or
  Terraform state fragment is accepted;
- destroyed or superseded deployments return no active links;
- cross-user access remains 404;
- historical `five-layer-baseline@1` returns `availability=unsupported` with
  `reason_code=unsupported_historical_profile` rather than fabricated links.

For GCP Grafana only, add an explicit mutating operation:

```text
POST /twins/{twin_id}/deployment-access/l5/credentials:rotate
  -> deployment-access-credential.v1
```

It rotates the human Viewer password and returns the username/password exactly
once in the authenticated response. It never reads or exposes the provisioning
Admin credential, reader key, Kubernetes Secret document, or Terraform state.
The Management database stores only the rotation timestamp and a credential
fingerprint. The Flutter reveal dialog warns that closing it discards the
value. Reissuing the credential always rotates; there is no password-read
endpoint.

## 7. Deployer And Terraform Outputs

Each selected L4/L5 implementation must produce a typed internal output bundle
that the Deployer validates before projecting it to Management:

| Surface | Required safe outputs | Required internal evidence |
|---|---|---|
| AWS L4 | workspace ID/ARN, console URL, principal label | permission-set and account-assignment IDs; seeded entity/model probe |
| Azure L4 | instance endpoint, Explorer URL, principal label | exact role-assignment ID; seeded graph probe |
| GCP L4 | explorer run.app URL, principal label | IAP policy binding; image digest; bounded L4 read probe |
| AWS L5 | workspace ID and URL, principal label | workspace association/role; datasource/dashboard probe |
| Azure L5 | workspace resource ID and endpoint, principal label | Grafana RBAC assignment; datasource/dashboard probe |
| GCP L5 | HTTPS endpoint, Viewer username, certificate SHA-256 fingerprint | source allowlist; datasource/dashboard probe; internal Admin-secret reference |

Terraform-sensitive values stay sensitive. The existing generic
`deployment-outputs.v1` projection remains redacted and cannot be used as a
credential transport. The new read model is assembled from allowlisted safe
fields and persisted operation evidence, not by substring-filtering arbitrary
Terraform output keys.

## 8. Deterministic Visible Content

A surface is not `content=ready` merely because its resource exists.
Deployment must idempotently provision:

### L4 seed

- one versioned `Twin2MultiCloudPoCDevice` model/component type;
- at least one entity/twin derived from the configured device inventory, or a
  deterministic `poc-device-001` seed when the inventory is empty;
- current state fields for provider, deployment, and last-update status;
- one relationship when at least two configured entities exist;
- no scene, 3D asset, editor, or raw-telemetry mirror.

### L5 seed

- one folder and one versioned `Twin2MultiCloud Raw & Rollups` dashboard;
- provider/deployment/device/metric filters;
- one bounded recent-raw panel;
- one bounded 30-day hourly-rollup panel;
- a no-data explanation that points to the existing test-message utility;
- a datasource `Save & test`/health check and both bounded query probes.

The content revision/digest is part of deployment evidence so refresh,
destroy, and redeploy are deterministic.

## 9. Twin Overview Boundary

The post-deployment Twin Overview adds an `Layer access` section immediately
after Deployment Readiness and before Deployment Actions. It renders two
sibling cards:

```text
Layer access
|-- L4 Semantic Twin
|   |-- provider + service + readiness
|   |-- Open Twin UI
|   `-- auth principal + capabilities + limitations
`-- L5 Raw & Rollup Dashboard
    |-- provider + service + readiness
    |-- Open Grafana
    `-- auth principal or Rotate Viewer credential (GCP only)
```

The generic Terraform Outputs card remains lower on the page as technical
evidence. It is not merged into the access cards. The current Twin Overview
BLoC owns loading, retry, and credential rotation. Widgets open only validated
HTTPS URLs through the existing external-launcher boundary and never call an
API directly.

The detailed widget/state/API/test plan is maintained in
[`2026-07-31_twin_layer_access_handoff.md`](../../../twin2multicloud_flutter/implementation_plans/2026-07-31_twin_layer_access_handoff.md).

## 10. Implementation And Commit Order

Every slice is mandatory and receives its own clean commit and review before
the next slice starts:

1. **Decision package and contracts:** update the service catalog, one-
   Firestore decision, schemas, fixtures, failure codes, and all nine placement
   expectations.
2. **Management persistence/read model:** persist safe access evidence and add
   the owner-scoped `deployment-access.v1` endpoint with no secret operation.
3. **Deployer/Terraform provider surfaces:** implement AWS, Azure, and GCP L4
   links/content/role bindings and L5 dashboard/access outputs; implement GCP
   Viewer rotation last within this slice.
4. **Flutter contract and state:** strict Dart models, Management API methods,
   demo parity, BLoC loading/retry/rotation states.
5. **Flutter presentation:** responsive two-card section, external launching,
   one-time secret dialog, and accessibility behavior.
6. **Offline integration and documentation:** Management-API integration
   fixtures for all nine placements, complete docs, and two zero-finding
   reviews.
7. **Optional supervised live gate:** only with explicit approval and cloud
   credentials, deploy each approved placement, sign into both surfaces, run a
   test message, capture redacted evidence, and destroy resources.

The optional live gate may be batched by provider account, but no placement is
called live-verified without opening both its L4 and L5 surfaces. Offline
activation remains `live_capacity_pending`.

## 11. Failure Codes And Readiness

Add stable safe codes:

```text
DEPLOYMENT_ACCESS_NOT_AVAILABLE
DEPLOYMENT_ACCESS_CONTRACT_INVALID
INTERACTIVE_PRINCIPAL_REQUIRED
INTERACTIVE_PRINCIPAL_NOT_FOUND
INTERACTIVE_ROLE_BINDING_FAILED
GCP_IAP_PREREQUISITE_REQUIRED
LAYER_ACCESS_CONTENT_PROVISIONING_FAILED
LAYER_ACCESS_DATA_PROBE_FAILED
LAYER_ACCESS_URL_INVALID
GCP_GRAFANA_VIEWER_ROTATION_FAILED
```

Deployment may succeed technically while layer access is blocked only if the
provider prerequisite changed after a successful preflight. In that case Twin
Overview shows the deployment as deployed but the affected card as blocked,
with safe remediation. A new deployment cannot start when its required
interactive principal or first-time IAP prerequisite is already known to be
missing.

## 12. Primary Provider Evidence

- [AWS IoT TwinMaker concepts and console capabilities](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/what-is-twinmaker.html)
- [AWS IoT TwinMaker identity-policy examples](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/security_iam_id-based-policy-examples.html)
- [Amazon Managed Grafana authentication](https://docs.aws.amazon.com/grafana/latest/userguide/authentication-in-AMG.html)
- [Amazon Managed Grafana user roles](https://docs.aws.amazon.com/grafana/latest/userguide/Grafana-user-roles.html)
- [Azure Digital Twins Explorer](https://learn.microsoft.com/en-us/azure/digital-twins/how-to-use-azure-digital-twins-explorer)
- [Azure Digital Twins data-plane roles](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-security)
- [Azure Managed Grafana access roles](https://learn.microsoft.com/en-us/azure/managed-grafana/how-to-manage-access-permissions-users-identities)
- [Cloud Run direct IAP configuration](https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)
- [Firestore server-client IAM](https://cloud.google.com/firestore/docs/security/iam)
- [Firestore Security Rules and server-library boundary](https://cloud.google.com/firestore/native/docs/security/rules-conditions)

The GCP source explicitly records the non-automatable edge: first-time IAP in
a project without an organization can require Cloud Console setup because
OAuth clients cannot be created programmatically. That is why the plan exposes
an admission prerequisite instead of claiming universal unattended setup.

## 13. Definition Of Done

- [ ] The complete-service decision package contains this access contract and
      the one-Firestore tradeoff.
- [ ] Exactly one typed L4 and one typed L5 access surface resolve for every
      Five-layer v2 deployment.
- [ ] All nine placement fixtures pass, including all three single-cloud rows.
- [ ] AWS, Azure, and GCP interactive identity prerequisites are preflighted
      independently from deployment credentials.
- [ ] Each L4 opens a usable semantic Twin UI with deterministic content.
- [ ] Each L5 opens a usable Grafana dashboard with deterministic raw/rollup
      content and an honest no-data state.
- [ ] No L4-to-L5, scene, 3D, or custom Grafana Twin plugin is introduced.
- [ ] GCP uses one Firestore database per deployment and documents its weaker
      collection-isolation boundary.
- [ ] Flutter consumes Management API only and never interprets raw Terraform
      outputs as access configuration.
- [ ] GCP Viewer credential rotation reveals only the human Viewer password
      once; no provisioning or reader secret crosses the Management boundary.
- [ ] Destroy and redeploy invalidate old URLs, bindings, credentials, and
      access evidence.
- [ ] Offline tests make no live-cloud/browser claim.
- [ ] Two fresh architect/builder and cross-stack reviews have zero unresolved
      findings before implementation begins.
