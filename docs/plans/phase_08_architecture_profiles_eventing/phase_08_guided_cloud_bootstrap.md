---
title: "Phase 8 Guided Cloud Bootstrap And Manual Prerequisites"
description: "Binding cross-service plan for turning request-scoped bootstrap authority into reusable bounded CloudConnections while exposing the few unavoidable provider actions."
tags: [phase-8, credentials, bootstrap, cloud-connections, identity, preflight, security]
lastUpdated: "2026-08-24"
version: "1.7"
---

<!-- SOURCES:
- User-approved flow from the 2026-07-31 Phase 8 service and layer-access review
- docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md
- docs/plans/2026-05-19_credential_ssot_compose_split.md
- docs/plans/2026-05-21_provider_bootstrap_preflight_plan.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_service_bundle_closure.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md
- bootstrap/aws/bootstrap_deployment_identity.sh
- bootstrap/azure/bootstrap_deployment_identity.sh
- bootstrap/gcp/bootstrap_deployment_identity.sh
- Current Management API OpenAPI contract on 2026-07-31
- twin2multicloud_flutter/docs/configuration_workspace/CONCEPT_CONFIGURATION_WORKSPACE.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_02_PROFILE_CLOUD_ACCESS.md
- AWS IAM Identity Center, Microsoft Azure RBAC, and Google Cloud IAM/IAP primary documentation linked in section 15
EXTRACTED: 2026-08-24 | VERSION: 1.7
-->

# Phase 8 Guided Cloud Bootstrap And Manual Prerequisites

## 1. Decision

The user must not manually construct a deployer-ready CloudConnection before
using Twin2MultiCloud. When no suitable deployment CloudConnection exists, the
platform offers a guided one-time bootstrap. The user supplies temporary
provider authority, and the Management API uses it to create, validate, and
persist only a bounded deployment identity. Bootstrap secrets are never a
normal application credential type.

Creating a Twin draft, describing the workload, calculating alternatives, and
reviewing the selected architecture remain credential-free. The bootstrap is
required only when the selected architecture reaches **Prepare deployment ->
Cloud access**, or when the user deliberately prepares reusable access earlier
from **Settings -> Cloud Accounts & Access**.

```text
Twin draft and workload
  -> selected immutable architecture
  -> required provider scopes known
  -> reuse compatible CloudConnection
     or start guided bootstrap
        -> show provider-owned preparation guide
        -> receive request-scoped bootstrap credential
        -> create and validate bounded deployment identity
        -> persist bounded CloudConnection only
        -> stop retaining bootstrap secret after the request
        -> apply the provider-specific disposal matrix in Section 6
        -> deployment CloudConnection ready
  -> run Twin-specific deployment preflight with that CloudConnection
     -> ready
        or pause on exact external action
           -> user completes provider action
           -> rerun Twin deployment preflight with the bounded CloudConnection
  -> finish deployment preparation
  -> explicit deploy from Twin Overview
```

## 2. Scope

| In scope | Out of scope |
|---|---|
| Guided AWS, Azure, and GCP deployment-access bootstrap | Creating an AWS account, Azure tenant/subscription, or commercial billing relationship |
| Existing billing-enabled GCP project path | GCP organization/project creation or billing mutation |
| Request-only bootstrap secret handling | Automatic provider-console or browser-login automation |
| Reusable bounded PoC CloudConnections | Treating deployment credentials as human browser passwords |
| Typed pause, remediation, and resume behavior | Silently creating human Azure, Google, or externally managed AWS users |
| Explicit built-in AWS Identity Center user invitation with consent | Managing external IdP membership, MFA, password recovery, or organization membership |
| Disposable-credential revocation status | Deleting an existing general administrator credential supplied by the user |
| Offline contract, adapter, redaction, and mock-plan evidence | Default live provider E2E or cost-incurring deployment |

### 2.1 Current Baseline And Migration

The repository already implements a manual-first Stage 1 bootstrap:

```text
POST /cloud-bootstrap/{provider}/plan
  -> run reviewed bootstrap/<provider>/bootstrap_deployment_identity.sh outside the app
  -> POST /cloud-bootstrap/import
  -> purpose=deployment CloudConnection
```

That contract is implemented and remains a compatibility fallback beside the
offline guided lifecycle. The new session contract is additive; Flutter Phase
9 uses the new guide/session contract and does not execute a local script or
provider CLI. The legacy
`plan` and `import` endpoints may be deprecated only after all three guided
provider adapters, migration tests, and documentation pass. Removing them is
not part of this phase.

The first guided implementation deliberately preserves the currently
supported generated authentication types:

| Provider | Generated identity and CloudConnection auth type |
|---|---|
| AWS | Dedicated IAM user plus one access key; `access_key` |
| Azure | App registration/service principal plus one client secret; `service_principal` |
| GCP | Dedicated service account plus one user-managed key; `service_account_key` |

The current manual scripts generate identities against the versioned
`thesis-demo-v1` deployment permission artifacts already checked against the
current Deployer. Five-layer v2 adds services and must not mutate or overclaim
that historical version. Its immutable decision package therefore publishes
new AWS/Azure/GCP `thesis-demo-v2` deployment artifacts and drift fixtures
before guided provider adapters are activated. These remain bounded,
reviewable PoC baselines, not a formal least-privilege result. Existing and new
documented permission-scope gaps remain visible thesis limitations.

The current scripts assume that the already authenticated CLI principal can
perform their setup calls. Guided bootstrap now publishes a distinct reviewed,
machine-checkable permission pack for that initial authority:

```text
bootstrap.aws.admin-v2
bootstrap.azure.admin-v2
bootstrap.gcp.admin-v3
```

Their canonical planned locations are:

| Contract ID | Repository artifact |
|---|---|
| `bootstrap.aws.admin-v2` | `3-cloud-deployer/docs/references/permission_sets/aws_bootstrap_admin_v2.json` |
| `bootstrap.azure.admin-v2` | `3-cloud-deployer/docs/references/permission_sets/azure_bootstrap_admin_v2.json` |
| `bootstrap.gcp.admin-v3` | `3-cloud-deployer/docs/references/permission_sets/gcp_bootstrap_admin_v3.json` |

AWS v2 supersedes the historical `bootstrap.aws.admin-v1` pack without
rewriting it. The v1 inline-policy path cannot hold the Phase 8 permission
inventory because AWS limits all inline policies on one IAM user to 2,048
characters. The v2 pack instead creates, attaches, versions, detaches, and
deletes one gate-owned customer-managed policy; its rendered document must
remain below AWS's 6,144-character customer-managed-policy limit.

The frozen `aws_thesis_demo_v2.json` permission inventory historically names
a deployment role, but the approved PoC credential path above is an IAM user
with one access key. The implementation does not rewrite that historical
artifact. Instead, `aws.thesis-demo-v2.iam-user-v1` is a separate, versioned
identity binding that pins the exact base-pack digest, IAM-user identity kind,
`access_key` CloudConnection auth type, customer-managed-policy attachment, and
the IAM-user self-inspection actions used by the Deployer preflight. Guide and
setup-gate digests cover both documents. STS AssumeRole is therefore not
implied by the active PoC contract.

Azure v2 likewise supersedes the historical `bootstrap.azure.admin-v1` pack
without rewriting it. The v2 pack adds the exact role-definition write/delete
boundary required to create and clean up the generated `thesis-demo-v2` custom
role; it does not permit a fallback to broad `Contributor` plus
`User Access Administrator` assignments.

GCP v3 supersedes the historical v1/v2 packs without rewriting them. It keeps
read-only readiness verification and custom-role listing, and adds the bounded
Service Usage enable/poll operations for the fixed 19-service Phase 8
baseline. Service Usage, IAM, and Cloud Resource Manager must already be
available; a key-creation organization-policy block remains a manual
prerequisite rather than something the PoC weakens.

Each artifact covers only generated-identity creation/reconciliation,
assignment of the guide-selected deployment pack, validation, cleanup, and the
attempted deletion of a dedicated bootstrap credential. Directory,
organization, billing, and key-policy limitations are recorded beside it.
Calling a user `Owner` or `Administrator` never substitutes for validating this
artifact at the actual provider scopes.

## 3. Placement In The User Journey

The bootstrap is not a mandatory screen before a Twin can be drafted. At that
point the Optimizer has not yet established which provider scopes are needed.
The same bootstrap capability has two entry points backed by the same
Management-owned session contract:

| Entry point | Purpose | Result |
|---|---|---|
| Configuration workspace, Prepare deployment -> Cloud access | Satisfy only the provider scopes required by the selected immutable architecture | Created/reused CloudConnection is bound to the draft |
| Settings -> Cloud Accounts & Access -> Add deployment access | Prepare a reusable provider scope before a specific Twin needs it | Created CloudConnection appears in the later workspace selector |

The user may leave and reopen the application while an external action is
pending. The safe bootstrap session and Twin draft are durable; the bootstrap
secret is not.

## 4. Manual-Step Inventory

### 4.1 Always External To Twin2MultiCloud

The following authority must exist before the platform can bootstrap itself:

| Provider | User-owned preparation | Values supplied to the guided flow |
|---|---|---|
| AWS | Existing billable AWS account; dedicated temporary IAM principal or assumed-role session that passes `bootstrap.aws.admin-v2` | account ID, region, access key ID, secret access key, optional session token, and required provider-issued expiry when a session token is used |
| Azure | Existing active Entra tenant and subscription; dedicated bootstrap app/service principal that passes `bootstrap.azure.admin-v2` across the required directory and subscription RBAC scopes | tenant ID, subscription ID, client ID, client secret, region, and safe credential key ID when automatic disposable-secret removal is requested |
| GCP existing-project path | Existing billing-enabled project where Service Usage, IAM, and Cloud Resource Manager are available; dedicated bootstrap service account that passes `bootstrap.gcp.admin-v3` at project scope | project ID, region, service-account JSON credential |
| GCP organization path | Not admitted by the first supervised PoC gate; project creation and organization/folder/billing mutation require a separate reviewed ownership contract | no active input form; the API returns `BOOTSTRAP_SCOPE_UNSUPPORTED` |

Provider guides must recommend a dedicated temporary credential. AWS root
access keys are forbidden. GCP JSON keys are an explicit PoC compatibility
path; when organization policy forbids key creation, the guide reports the
policy boundary and must not advise disabling it silently.

The user-facing provider guide must spell out these exact pre-application
steps. “Use admin credentials” is not sufficient:

| Provider | Manual steps before secret submission |
|---|---|
| AWS | Sign in as a non-root administrator; select the target account; create a dedicated temporary IAM principal or obtain a short STS session; attach the versioned bootstrap pack; create/copy the access key material once; record account ID and region. |
| Azure | Sign in to the correct tenant; select the subscription; create a dedicated bootstrap app/service principal; assign the versioned bootstrap authority at the displayed subscription or resource-group scope; create a short-lived client secret; record tenant, subscription, and client IDs. Azure subscription `Owner` alone does not prove permission to create Entra applications, so the guide validates both directory and Azure RBAC authority. |
| GCP existing project | Select an existing billing-enabled project; confirm Service Usage, IAM, and Cloud Resource Manager are available; create a dedicated bootstrap service account; bind `bootstrap.gcp.admin-v3`; create and download one JSON key only if organization policy permits; record project and region. Bootstrap then enables the displayed fixed Phase 8 API baseline before creating the bounded identity. |
| GCP organization path | No steps are offered in the active PoC. Use an existing project or treat organization/project creation as separately scoped future work. |

An existing general administrator credential is accepted only through the
explicit `existing_user_owned` choice and only if validation proves every
required permission. Provider marketing role names such as `Owner` or
`Administrator` are not treated as sufficient evidence across directory,
organization, billing, and resource scopes.

### 4.2 Conditional Pre-Deployment Provider Actions

These actions occur only when preflight returns the named typed prerequisite:

| Condition | Required user action | Resume behavior |
|---|---|---|
| AWS L4 selected and no IAM Identity Center organization instance exists | In the AWS Organizations management account, enable the organization instance in the selected region and acknowledge any account-plan consequence | Select **Recheck**; the stored bounded CloudConnection discovers the instance and completes permission-set/account assignment |
| AWS uses an external identity source and the selected principal is absent | Provision the user/group through the external identity system | Recheck resolves the principal; Twin2MultiCloud never holds that password |
| GCP L4 selected in a project without an organization | Complete the documented first-time custom OAuth/IAP setup in Cloud Console | Recheck completes the IAP policy binding |
| GCP L4 uses an out-of-organization principal | Configure an External consent audience and custom OAuth client in Cloud Console | Recheck validates external access and completes the binding |
| Required scenario capacity exceeds an available provider quota | Request the displayed quota increase or select a smaller scenario/provider placement | Recheck reruns the same immutable capacity admission |
| Billing, subscription, region, API, or organization policy blocks admission and cannot be changed through the bounded API path | Resolve the exact provider finding or choose another supported placement | Recheck never mutates the architecture selection silently |

These are Twin-specific deployment-preflight findings, not bootstrap-session
states. They block finishing deployment preparation, not draft creation,
calculation, Settings, or reuse of the generated CloudConnection. A remediation
response contains a safe provider-console URL, an explanation, the affected
provider/scope, and a recheck action. Recheck reruns
`POST /twins/{twin_id}/deployment-preflight` with stored CloudConnection
references; it contains no provider response body or credential material.

### 4.3 Personal Post-Deployment Actions

These are authentication or supervised evidence actions, not infrastructure
provisioning:

| Surface | User action |
|---|---|
| AWS L4/L5 | Accept a new built-in Identity Center invitation when requested, set a password, complete MFA, and sign in; an existing principal signs in normally |
| Azure L4/L5 | Sign in with the bound Entra principal and complete tenant MFA/Conditional Access |
| GCP L4 | Sign in with the bound Google principal and complete any required consent |
| GCP L5 | Request a new human Viewer password from Twin Overview, store the one-time value, verify the certificate fingerprint, and sign in from an allowed source range |
| Optional thesis live gate | Open both L4 and L5, send one test message when visible telemetry is desired, capture redacted evidence, and destroy the supervised deployment |

Deployment succeeds with deterministic L4 seed content and an empty-state L5
dashboard. Sending a test message is never part of deployment success.

### 4.4 User-Visible Runbook

For a first Twin, the complete expected user sequence is:

1. Outside Twin2MultiCloud, create/own the required provider account, tenant,
   subscription, project/organization, billing relationship, and an ordinary
   human provider login.
2. Start the UI and create, calculate, and select an architecture without cloud
   credentials.
3. Open **Prepare deployment -> Cloud access**. For every required provider,
   reuse a compatible deployment CloudConnection or open its generated guide.
4. If no connection exists, follow the provider guide to create/obtain the
   temporary bootstrap credential listed in Section 4.1, then submit it once.
5. Wait while Twin2MultiCloud creates and validates the bounded PoC deployment
   identity and persists its CloudConnection. Never copy the generated
   deployment secret from the UI; it is not displayed.
6. If automatic deletion of a dedicated bootstrap credential failed, delete
   the displayed safe key/client identifier in the provider console and
   acknowledge that manual action. If an existing user-owned credential was
   used, understand that Twin2MultiCloud released its copy but did not revoke
   the credential at the provider.
7. Select the required existing human L4/L5 principals and run Twin deployment
   preflight. When it reports Identity Center, IAP, quota, billing, or policy
   action, complete only that linked provider step and choose **Rerun
   preflight**. Do not submit bootstrap credentials again.
8. Finish configuration, review, and explicitly deploy. After deployment,
   accept invitations/configure MFA or rotate the GCP Grafana Viewer password
   when the Layer Access cards request those personal steps.

For later Twins in the same compatible scope, steps 4-6 disappear because the
bounded CloudConnection is reused. Starting from Settings performs steps 3-6
without binding a Twin; steps 7-8 occur only after a later architecture is
selected.

## 5. Bootstrap Session Contract

The Management API owns one owner-scoped, provider-and-target-scoped bootstrap
session. It is not owned by Flutter or the Deployer. Bootstrap completion and
Twin deployment admission have separate sources of truth:

```text
cloud-bootstrap-session.v1
  draft
    -> bootstrap_running
    -> generated_connection_ready
    -> disposal_running
       -> manual_revocation_required -> ready after explicit acknowledgement
       -> ready
    -> credential_reentry_required | cancelled | failed

then, only for a concrete Twin:

POST /twins/{twin_id}/deployment-preflight
  -> ready
  -> external_action_required
       -> user completes exact provider action
       -> rerun the same Twin deployment preflight
```

Settings stops at bootstrap `ready`. The configuration workspace binds the
ready CloudConnection and continues with the existing Twin deployment-
preflight owner. It may present both parts as one guided journey, but it must
not duplicate preflight findings inside the bootstrap-session record.

The durable bootstrap session contains only:

- owner, provider, safe account/project/subscription/bootstrap-project scope,
  and selected region;
- optional Twin draft binding and entry point (`settings` or `twin_prepare`);
- bootstrap-authority-pack ID/version/digest, generated-deployment-pack
  ID/version/digest, and generated CloudConnection ID;
- current typed state, stable bootstrap finding codes, safe timestamps, and
  idempotency key;
- bootstrap credential origin and disposal status; and
- credential fingerprint/key identifier only when safe and necessary for
  manual deletion guidance.

It never contains the access key secret, session token, client secret,
service-account JSON/private key, OAuth client secret, browser password, or raw
provider response.

Required Management API capabilities are:

```text
POST /cloud-bootstrap/{provider}/guide
POST /cloud-bootstrap/sessions
GET  /cloud-bootstrap/sessions?provider={provider}&active={bool}
GET  /cloud-bootstrap/sessions/{session_id}
POST /cloud-bootstrap/sessions/{session_id}/execute
POST /cloud-bootstrap/sessions/{session_id}/acknowledge-manual-revocation
POST /cloud-bootstrap/sessions/{session_id}/cancel
```

`POST /cloud-bootstrap/{provider}/guide` accepts safe target context only and
returns `cloud-bootstrap-guide.v1`. `POST /cloud-bootstrap/sessions` creates
the safe `draft` and returns its ID before any secret is submitted. Only
`POST /cloud-bootstrap/sessions/{session_id}/execute` accepts a bootstrap
credential. All secret-dependent provider work and any automatic disposable-
credential revocation occur within that request; no queued worker or retry
payload may retain it.

Guide/session target objects are strict and mutually exclusive:

| Provider/mode | Required safe target fields |
|---|---|
| AWS | `account_id`, `region`; optional `session_expires_at` becomes required only when execute includes a session token |
| Azure | `tenant_id`, `subscription_id`, `region`; optional safe `bootstrap_credential_key_id` for automatic disposable-secret removal. The first PoC implementation is subscription-scoped because the Deployer creates its resource group. |
| GCP `existing_project` | exact `mode`, `project_id`, `region` |
| GCP `organization` | Reserved compatibility request shape only; Management returns `BOOTSTRAP_SCOPE_UNSUPPORTED` before guide/session creation or mutation |

`entry_point=settings` forbids `twin_id`; `entry_point=twin_prepare` requires an
owner-visible Twin draft ID whose resolved architecture includes the provider.
The Management API rejects a target that conflicts with that immutable
provider requirement.

The client persists the safe session ID before `execute`. If the response is
lost, it loads the session instead of submitting automatically again. A state
of `generated_connection_ready`, `disposal_running`,
`manual_revocation_required`, or `ready` never asks for the credential again.
Only `credential_reentry_required`, which is allowed solely when no validated
generated connection exists and the prior request no longer holds a usable
secret, permits a new explicit submission.

The guide contract contains:

| Field | Required meaning |
|---|---|
| `schema_version` | Exact `cloud-bootstrap-guide.v1` discriminator |
| `execution_mode` | Exact `disabled`, offline `deterministic_fake`, or `supervised_live`. The UI labels simulation and live setup differently. `supervised_live` remains blocked while its provider adapter is unconfigured; provider mutation still requires the separate reviewed setup-only gate. |
| `provider`, `target`, `region` | Safe provider context echoed from the request |
| `bootstrap_authority_pack` | Stable active AWS/Azure admin-v2 or GCP admin-v3 ID, digest, scope summary, directory/organization/billing/key-policy limitations, and an opaque downloadable provider artifact; historical artifacts remain versioned evidence and Flutter never edits them |
| `generated_deployment_pack` | Management-selected active ID/version/digest, scope summary, and known-gap references; Five-layer v2 requires `thesis-demo-v2` |
| `api_baseline` | `null` for AWS/Azure; for GCP, the exact digest-pinned 19-service Phase 8 superset, retained-state policy, mutation summary, limitations, and reviewed artifact link |
| `credential_fields` | Ordered provider-specific field IDs, safe labels, input type, required flag, and redaction rule; never values |
| `credential_origins` | `dedicated_disposable` and `existing_user_owned` with exact consequences |
| `preparation_steps` | Ordered manual steps, expected outcome, and allowlisted official HTTPS URL |
| `known_blockers` | Key-policy, directory/RBAC, organization, billing, and target-mode limitations detectable before submission |
| `legacy_fallback_available` | `true` while the implemented script/import path remains supported |

The session-create request contains only guide digest, both permission-pack
digests, entry point, optional Twin ID, safe target/region, display name, and
client idempotency key. Credential origin is selected together with the
one-use credential at execute time, so an abandoned draft never claims an
origin or disposal obligation that was not actually submitted. The execute
request contains that origin and exactly one strict discriminated credential
object:

| Provider | Execute-only secret fields |
|---|---|
| AWS | access key ID, secret access key, optional session token; provider-issued session expiry is safe session context, not part of the secret object |
| Azure | tenant ID, subscription ID, client ID, client secret |
| GCP | parsed service-account JSON object; strings containing a file path are rejected |

Every public session response returns only the safe session fields, an optional
existing `CloudConnectionResponse` summary, disposal outcome, and one stable
redacted finding. Unknown versions, states, provider fields, non-allowlisted
URLs, and secret-like response keys fail closed.

## 6. Credential Origins, Disposal, And Revocation

Discarding a secret from the application is not the same as revoking it at the
provider. The request therefore declares one origin:

| Origin | Meaning | Required outcome |
|---|---|---|
| `dedicated_disposable` | Credential was created specifically for this bootstrap | Apply the provider matrix below: confirm provider-side revocation, record provider expiry for a short session, or return `manual_revocation_required` with exact deletion guidance |
| `existing_user_owned` | User deliberately supplied an existing administrator credential | Never alter it; stop deliberate application retention and report `not_retained_user_managed`, explicitly stating that it remains valid at the provider |

Allowed disposal states are:

```text
revoked
expires_at_provider
manual_revocation_required
not_retained_user_managed
released_after_failure
```

The initial provider behavior is explicit:

| Provider credential submitted as `dedicated_disposable` | Automatic final action | Fallback |
|---|---|---|
| AWS IAM-user access key | Delete the exact submitted access-key ID when it belongs to the declared bootstrap principal and `bootstrap.aws.admin-v2` permits the call | Show IAM key ID and official delete-key steps |
| AWS STS session | Record the provider-issued expiration as `expires_at_provider`; do not claim deletion or early revocation | Show principal/session identifier and exact expiry; no cleanup acknowledgement is required |
| Azure service-principal client secret | Remove the exact submitted credential/key ID only when the bootstrap app and Graph authority permit it | Show tenant, application ID, safe credential ID, and official credential-removal steps |
| GCP service-account key | Delete the exact submitted key ID only after its private material matches that key ID's provider X.509 public key; leave the shared API baseline enabled | Show service-account email/key ID and official delete-key steps |

The execute request must derive and validate the safe credential/key identifier
before provider mutation. If a provider credential format does not expose a
stable identifier, automatic revocation is disabled and the guide says so
before submission.

No success message may say that a credential was revoked merely because the
request object was released. A disposable credential with unresolved manual
revocation keeps the bootstrap assistant incomplete until the user confirms
the provider-side cleanup through the dedicated acknowledgement operation. The
PoC records the confirmation and safe key ID; it does not claim cryptographic
proof when the generated CloudConnection cannot inspect that bootstrap
credential.

The normal persistent implementation minimizes secret copies and drops every
application-held reference after the execute request. The separately admitted
setup-only runner retains the submitted authority only in its process until
generated-identity and bootstrap-authority cleanup finish; Management still
does not persist it. Python and provider SDKs do not guarantee cryptographic
zeroization of immutable strings or managed-runtime memory, so the UI and
thesis must claim **non-persistence and no deliberate retention beyond the
bounded setup transaction**, not proven memory erasure. Request bodies are
excluded from access logs, traces, metrics, audit payloads, exception
serialization, retry queues, crash dumps under application control, and
temporary files.

## 7. Generated CloudConnection

The generated identity is the only persistent deployment credential. Its
initial shape matches the implemented manual bootstrap instead of inventing a
second credential model:

| Provider path | Generated scope and known PoC boundary |
|---|---|
| AWS | IAM user in the selected account with the guide-selected reviewed AWS deployment pack and one managed access key |
| Azure | Service principal in the selected tenant with the reviewed subscription-scope PoC assignments and one client secret |
| GCP existing project | Service account in the selected project with the reviewed custom role and one user-managed key |
| GCP organization path | No generated identity in the active PoC; the request fails closed before a guide or mutation |

This identity is bounded by the guide-selected reviewed PoC permission
artifacts and target
scope. It is not described as formally least-privileged, especially for Azure
role-assignment authority and the temporary GCP API-enable boundary.

The Management API must:

1. create or idempotently reuse the generated identity;
2. attach only the exact reviewed deployment permission pack required by the
   guide/profile (`thesis-demo-v2` for Five-layer v2);
3. validate provider identity, scope, permissions, expiry, and fingerprint;
4. encrypt the bounded credential payload as a user-owned
   `purpose=deployment` CloudConnection;
5. expose only safe identity/scope/deployment-permission-pack metadata;
6. bind its ID to a Twin only after the selected architecture requires that
   provider; and
7. invalidate readiness when its credential fingerprint or deployment-pack
   version changes.

A compatible CloudConnection is reusable by later Twins in the same declared
scope. The active GCP scope is exactly one existing project; organization-path
reuse is not claimed by this PoC.
Creating a new Twin does not request bootstrap authority again unless the
connection is missing, revoked, incompatible, or explicitly replaced.
An existing `thesis-demo-v1` connection remains valid for deployments that
require v1; Five-layer v2 preflight reports it as outdated and requires an
explicit v2 upgrade/new bootstrap. Settings uses the current Management-owned
default deployment-pack version and shows that version before submission.

## 8. Interactive Human Identity

Cloud deployment authority and browser identity remain distinct inputs.

| Provider | Twin deployment-preflight and deployment behavior |
|---|---|
| AWS built-in Identity Center directory | Resolve an existing principal, or create/invite one only after an explicit user choice and email confirmation |
| AWS external identity source | Resolve only; account/group provisioning remains external |
| Azure Entra | Resolve an existing object ID/UPN and assign exact ADT/Grafana roles; no silent user invitation |
| GCP L4 | Resolve an existing Google user or approved group and assign exact IAP access; no Google-account creation |
| GCP L5 | Create the deployment-scoped Grafana Viewer inside the deployment; its password uses the existing one-time rotation contract |

The setup contract never accepts a browser password. Invitations, password
setup, MFA, Conditional Access, consent, recovery, and organization membership
remain provider-owned.

## 9. Provider-Specific Admission Rules

### 9.1 AWS

- Amazon Managed Grafana alone may use an API-created IAM Identity Center
  account instance where supported.
- The planned L4 TwinMaker console deep link requires AWS-account access via a
  permission set and therefore an IAM Identity Center **organization
  instance**.
- The `CreateInstance` API cannot create that organization instance in the
  Organizations management account. If it is absent, preflight must pause with
  `AWS_IDENTITY_CENTER_ORGANIZATION_INSTANCE_REQUIRED`.
- Once the instance and principal exist, permission sets, account assignments,
  TwinMaker access, Grafana associations, and deterministic content are
  automated.

### 9.2 Azure

- The selected Entra principal must already exist.
- The bootstrap identity creates the bounded deployment service principal or
  credential and the exact role assignments permitted by the reviewed pack.
- ADT Data Reader and Grafana roles are assigned automatically at exact
  resource scopes after deployment.
- Tenant MFA, Conditional Access, invitations, and browser sign-in remain
  external human actions.

### 9.3 GCP

- Service APIs, service agents, bounded IAM roles, Cloud Run direct IAP, and
  principal policy bindings are automated when the project context permits.
- First-time IAP in a project without an organization, and external-user
  custom OAuth configuration, remain typed external actions because Google
  does not provide the required end-to-end programmatic OAuth-client path.
- A GCP organization created on or after 2024-05-03 can enforce service-account
  key creation restrictions by default. The plan reports that policy and does
  not silently weaken it. An approved alternative bootstrap credential path
  requires a separate contract revision.
- GCP L5 additionally requires a non-empty user-supplied source CIDR before
  deployment. It is configuration, not an administrator credential.

## 10. Concurrency, Retry, And Failure Behavior

- One active bootstrap session is allowed per owner/provider/scope. A second
  start returns the existing safe session or a conflict; it never creates a
  second deployment identity.
- Provider writes use deterministic names, idempotency tokens where available,
  and read-after-write reconciliation.
- Automatic retries are allowed only while the same request still owns the
  bootstrap credential in memory. A later retry never asks a worker to reload
  that secret.
- A failure before CloudConnection validation reconciles/deletes partial
  generated identities while the execute request still holds authority. If
  cleanup or completion cannot finish, deterministic resource identifiers are
  stored safely and the session becomes `credential_reentry_required`; a later
  explicit execute may reconcile them but never recovers the prior secret.
- A failure after CloudConnection validation preserves the bounded connection
  and safe session. Disposal completion and later Twin preflight continue
  without administrator authority unless the disposable bootstrap credential
  itself still requires user-confirmed manual deletion.
- On Management restart, a stale `bootstrap_running`/`disposal_running` lease
  is reconciled deterministically: without a validated connection it becomes
  `credential_reentry_required`; with an `existing_user_owned` origin it
  records `not_retained_user_managed`; with a disposable origin whose provider-
  side deletion was not durably confirmed it becomes
  `manual_revocation_required`. Recovery never guesses `revoked`.
- Cancel is cooperative while `bootstrap_running`. From `draft` it cancels
  directly; after a validated CloudConnection exists it never deletes that
  reusable connection and instead returns the current safe state. It never
  revokes an `existing_user_owned` credential.
- Twin deletion does not automatically delete a reusable CloudConnection.

## 11. Stable Finding Codes

The bootstrap-session contract adds:

```text
BOOTSTRAP_CREDENTIAL_REQUIRED
BOOTSTRAP_CREDENTIAL_INVALID
BOOTSTRAP_CREDENTIAL_REENTRY_REQUIRED
BOOTSTRAP_AUTHORITY_PACK_MISMATCH
BOOTSTRAP_GENERATED_DEPLOYMENT_PACK_MISMATCH
BOOTSTRAP_IDENTITY_CREATION_FAILED
BOOTSTRAP_CONNECTION_VALIDATION_FAILED
BOOTSTRAP_MANUAL_REVOCATION_REQUIRED
BOOTSTRAP_SESSION_CONFLICT
PROVIDER_ORGANIZATION_POLICY_BLOCKED
```

The separate Twin deployment-preflight contract owns:

```text
AWS_IDENTITY_CENTER_ORGANIZATION_INSTANCE_REQUIRED
AWS_INTERACTIVE_PRINCIPAL_REQUIRED
AZURE_INTERACTIVE_PRINCIPAL_REQUIRED
GCP_INTERACTIVE_PRINCIPAL_REQUIRED
GCP_IAP_PREREQUISITE_REQUIRED
PROVIDER_BILLING_ACTION_REQUIRED
PROVIDER_QUOTA_ACTION_REQUIRED
```

Every finding has a safe title, explanation, provider/scope, blocking flag,
explicit next action, and optional allowlisted official remediation URL.
Bootstrap findings declare whether execute or acknowledgement is allowed;
deployment findings declare whether Twin-preflight recheck is allowed.
Provider payloads, resource-policy documents, and secret-derived strings are
forbidden.

## 12. Implementation And Commit Boundaries

Prerequisite: the immutable Five-layer v2 decision package and its three
`thesis-demo-v2` deployment permission artifacts are committed and reviewed.
The bootstrap branch consumes their IDs/digests and does not invent or mutate
deployment permissions.

The offline implementation was delivered in independently reviewed commits:

1. **Contracts and fixtures:** retain the original three
   `bootstrap.<provider>.admin-v1` authority artifacts as historical evidence;
   publish the active AWS, Azure, and GCP v2 corrections plus the AWS
   deployment-identity binding; add bootstrap guide/session schemas, stable
   finding codes, both permission-pack references, provider matrices,
   compatibility fixtures, and redaction tests.
2. **Management lifecycle:** request-only secret boundary, session ownership,
   idempotency, generated CloudConnection persistence, execute/cancel/manual-
   revocation acknowledgement, audit events, and disposal status. Keep the
   current manual `plan`/`import` endpoints compatible.
3. **Provider bootstrap adapters:** deterministic AWS, Azure, and GCP lifecycle
   simulation, including permission binding, validation, cleanup/revocation
   behavior, and mock-provider evidence. The production adapter remains
   `disabled`; real identity creation is an optional supervised live gate.
4. **Deployer admission integration:** consume generated CloudConnections,
   extend the existing Twin deployment preflight with identity/quota/billing/
   manual prerequisites, and prohibit raw bootstrap credentials in packages
   or Terraform inputs.
5. **Flutter delivery:** architect-reviewed implementation of the shared
   Settings/configuration-workspace flow, provider guides, safe secret entry,
   pause/recheck, and disposal acknowledgement.
6. **Documentation and offline quality gate:** docs-site setup guides, contract
   generation/drift gates, complete safe suites, security scans, and two
   zero-finding reviews.
7. **Optional supervised live gate, not executed:** separately approved
   provider setup, bootstrap, recheck, one supported deployment, L4/L5 sign-in,
   redacted evidence, and destroy per provider context.

No commit mixed provider bootstrap support with Five-layer service-resource
implementation. The shared contract landed before the provider adapters; all
three deterministic providers closed before the UI exposed the shared guided
setup.

### 12.1 Completion Status

The request/response contracts, owner-scoped sessions, request-only credential
boundary, generated `thesis-demo-v2` deployment CloudConnections, Deployer
admission, both Flutter entry points, deterministic provider adapters, manual
cleanup acknowledgement, and compatibility fallback are implemented. The
production default fails closed and therefore makes no live-provider claim.
The AWS SDK, Azure OAuth/Graph/ARM, and GCP existing-project REST drivers are
available only when both `supervised_live` and the exact provider allowlist
are configured. Organization/project-creation GCP remains blocked.

The implementation and review evidence is recorded in
[`guided_cloud_access_bootstrap.md`](../../../twin2multicloud_flutter/docs/configuration_workspace/implementation/guided_cloud_access_bootstrap.md).

The optional setup-only live gate additionally uses
`scripts/materialize_deployment_policy.py` as the single offline translation
from the frozen provider-neutral deployment packs to provider-native request
documents. The materializer preserves the exact inventories and target scopes,
enforces AWS's managed-policy size limit and required conditions, and contains
no provider client or credential input. AWS output is now a complete safe
bundle for the pinned IAM-user binding: generated user name, managed-policy
name/ARN and document, plus the exact user-policy attachment. It contains no
access-key value and still makes no live-provider claim. The binding also owns
the unconditioned `ec2:DescribeRegions` read used before the region-scoped
workload policy can be evaluated.

Azure now likewise pins
`azure.thesis-demo-v2.service-principal-v1`. Its materialized custom role is
the frozen v2 workload inventory plus only the subscription, location, and
role-definition reads used by the existing service-principal preflight. The
Deployer selects the synchronized v2 provider packs by
`permission_set_version`; GCP checks the fixed Service Usage baseline and
fails preflight when any required API is absent. No provider result is claimed
until the supervised gate runs. GCP Terraform API ownership is resolved by the approved
[`GCP Phase 8 API Enablement Ownership`](../2026-08-24_gcp_phase8_api_ownership.md)
plan and implementation: the short-lived v3 bootstrap owns a fixed existing-
project API superset, the retained v2 deployment identity only verifies it,
and active v2 Terraform no longer creates `google_project_service` resources.
The AWS driver uses the same materialized bundle, validates the generated key
through STS, the exact managed-policy document, absence of inline/group
authority, and frozen regional discovery, and
performs ownership-bounded rollback/finalization. Its stateful fake-provider
tests include retry, validation failure, and unowned name collisions. The Azure
driver uses the same materialized custom-role bundle, one exactly tagged
application/service principal, one deterministic subscription assignment, and
one 24-hour generated client secret. It validates the exact role, sole
assignment, tenant/subscription, and frozen region and refuses foreign Graph
credentials or ARM assignments during cleanup. GCP now pins
`gcp.thesis-demo-v2.service-account-v1`, authenticates only from the submitted
service-account JSON without ADC fallback, checks the existing project and
active billing, enables the exact fixed API baseline, and reconciles one
run-owned service account, project custom-role binding, and JSON key. It
validates the generated credential against the sole binding, project-testable
permissions, and all 19 services, with bounded backoff only for documented GCP
IAM account/key visibility and role-binding propagation. Before any submitted-
key deletion it also cryptographically matches the private material to the
exact provider key ID;
identity cleanup never disables the shared baseline. G2-G5 live proof remains
pending for all providers, so G6/G7 stay blocked.

The credential-free local integration boundary is available as
`./thesis.sh test setup-smoke`. It runs the actual shared Flutter bootstrap UI
against a short-lived Management API and database in deterministic-fake mode,
checks all three provider client flows plus AWS UI submission, and removes the
isolated runtime after log/database secret-sentinel scans. It is G1 evidence,
not evidence of provider authority or live identity creation.

The supervised thesis path is implemented separately in
`scripts/setup_only_runner.py`; Flutter and the normal persistent session stay
unchanged. `prepare` creates only a guide/session plus secret-free manifest and
ledger. `execute` reads one provider credential document from stdin, calls the
real Management execute and CloudConnection-preflight APIs, and invokes the
mandatory setup cleanup before returning. Management retains only the
encrypted generated test connection and a secret-free provider rollback
receipt until cleanup succeeds. The runner retains submitted bootstrap
authority only in process memory so provider identity deletion happens before
the local connection is removed and disposable bootstrap authority is
finalized. If only that final revocation needs manual provider action, the
credential-free `acknowledge` command can close the retained receipt only after
Management has durably proven the first two cleanup stages. The setup flag
defaults false, exact run/provider confirmation is
required, CI activation is rejected, and no provider run has yet been made.

## 13. Verification Matrix

| Boundary | Required offline evidence |
|---|---|
| Schemas | Exact version, enum, finding, unknown-field, and no-secret fixtures |
| Management | owner isolation, idempotency, conflict, cancellation, stale-lease restart reconciliation for every origin/connection combination, no bootstrap secret persistence, CloudConnection encryption, and audit redaction |
| Provider adapters | create/reuse, permission mismatch, partial failure cleanup, existing-user-owned non-revocation, disposable revocation/manual fallback, and stable findings for AWS/Azure/GCP |
| Deployer | package/tfvars/state/log scan proves no bootstrap material; generated CloudConnection alone can pass mock admission |
| Flutter | both entry points reuse one bootstrap feature owner; secret fields never rehydrate; Settings ends at connection-ready; the workspace then composes Twin deployment-preflight pause/recheck; all async/blocked states render; no direct provider/service call exists |
| Documentation | every official link resolves, both authority/deployment-pack digests match the contract, and manual steps match the provider matrix |
| Live claim boundary | no browser sign-in, quota, billing, or provider availability claim without the separately approved supervised gate |

The final offline implementation gate runs from the repository root and must
include:

```bash
./thesis.sh test backend
./thesis.sh test deployment-contract --focused
./thesis.sh test deployment-contract
./thesis.sh test frontend
./thesis.sh test frontend-integration
docker compose --profile docs run --rm docs mkdocs build --strict
git diff --check
```

`frontend-integration` must use the real Docker Management API with the
deterministic fake provider-adapter mode. None of these commands may receive
real bootstrap credentials or reach a live provider.

## 14. Acceptance Criteria

- A user can create and calculate a Twin without any cloud credential.
- After architecture selection, the UI requests access only for providers in
  the immutable deployment decision.
- In the offline PoC adapter, a user can exercise creation of a validated
  bounded deployment CloudConnection without manually constructing it. A live
  provider result remains subject to the optional supervised gate.
- In the normal persistent workflow, the bootstrap secret is not retained after
  its execute request. In the separate setup-only runner it remains only in
  request-process memory until mandatory identity cleanup and bootstrap-
  authority finalization finish. It never enters durable application state,
  storage, packages, logs, traces, metrics, retry payloads, or error payloads;
  no cryptographic memory-zeroization claim is made.
- The UI distinguishes application release from provider-side revocation and
  never makes a false revocation claim.
- Every unavoidable manual provider action is typed and linked. Manual
  bootstrap-credential deletion uses explicit acknowledgement; Twin-specific
  provider prerequisites survive restart and rerun deployment preflight
  through the generated CloudConnection.
- Reusing a compatible CloudConnection never asks for administrator authority
  again.
- Human browser identity is explicit and separate from deployment authority.
- AWS L4, GCP no-organization/external IAP, quota, billing, and organization-
  policy cases fail closed with exact remediation.
- Flutter calls only the Management API.
- No live cloud operation is part of the default verification gate.

## 15. Primary Provider Evidence

- [AWS IAM Identity Center instance types](https://docs.aws.amazon.com/singlesignon/latest/userguide/identity-center-instances.html)
- [AWS IAM Identity Center `CreateInstance`](https://docs.aws.amazon.com/singlesignon/latest/APIReference/API_CreateInstance.html)
- [AWS identity and temporary credential guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction_identity-management.html)
- [Azure role assignments](https://learn.microsoft.com/en-us/azure/role-based-access-control/role-assignments-steps)
- [Azure CLI service-principal role management](https://learn.microsoft.com/en-us/cli/azure/azure-cli-sp-tutorial-5)
- [GCP service-account key creation and deletion](https://cloud.google.com/iam/docs/keys-create-delete)
- [GCP service-account key listing and public-key retrieval](https://cloud.google.com/iam/docs/keys-list-get)
- [GCP OAuth 2.0 service-account assertions](https://developers.google.com/identity/protocols/oauth2/service-account)
- [GCP service-account key security guidance](https://cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys)
- [Cloud Run direct IAP configuration](https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)

## 16. Related Plans

- [`2026-04-26_runtime_credentials_deployment_state_hardening.md`](../2026-04-26_runtime_credentials_deployment_state_hardening.md)
- [`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md)
- [`phase_08_layer_access_handoff.md`](phase_08_layer_access_handoff.md)
- [`phase_08_9_six_layer_eventing_implementation.md`](phase_08_9_six_layer_eventing_implementation.md)
- [`CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md`](../../../twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md)
