---
title: "Twin2MultiCloud PoC Credential, Readiness, and Repair Concept"
description: "Bounded credential and provider-preparation contract for the supervised thesis proof of concept."
tags: [security, credentials, readiness, repair, thesis-scope]
lastUpdated: "2026-08-31"
version: "2.3"
---

# PoC credential, readiness, and repair concept

Status: active scope decision

## 1. Decision

The proof of concept accepts a pre-existing, non-root deployment administrator
credential for an isolated thesis account, Azure subscription, or Google Cloud
project. It does not create, rotate, or revoke this deployment authority and
does not claim that it is least privilege or production ready.

AWS and Google Cloud each use one provider principal. Azure is the bounded
exception: one encrypted deployment-purpose CloudConnection contains two
distinct service principals for the same tenant and subscription. The
deployment principal owns ordinary resource CRUD; the preparation principal
owns only the exact conditional RBAC and Microsoft Graph operations required
by the resolved graph. This does not introduce a general credential-purpose
registry.

Twin2MultiCloud may use the supplied authority to prepare a closed set of
provider capabilities that the selected resolved deployment graph actually
requires. Preparation is always preceded by a non-mutating readiness check, a
reviewable action plan, and explicit user confirmation.

This boundary keeps the final user journey practical without turning the PoC
into an identity-governance or cloud-account-onboarding product.

## 2. Credential classes

The implementation must not use the word `credential` for unrelated secrets
without identifying the class:

| Class | Purpose | Owner | PoC behavior |
|---|---|---|---|
| Deployment authority | Pricing reads, readiness, bounded preparation, Terraform deployment and Destroy | thesis operator | imported or entered, encrypted, selectable, never returned |
| Runtime workload identity | Service-to-service and cross-cloud calls of one deployed Twin | deployed Twin | generated through the reviewed Terraform graph, narrowly scoped, cleaned up with the Twin where provider semantics allow |
| Runtime access identity | Human access to an L4/L5 surface | university user or deployed service | existing SSO/Entra identity or bounded service-local Viewer identity |
| Ephemeral exchange token | One cross-cloud request or session | provider federation | generated at runtime, short-lived, never persisted as a CloudConnection |

Deployment authority and runtime access must never be conflated. In
particular, an administrator secret must not be displayed as the password for
a deployed dashboard.

## 3. CloudConnection model

A single user may retain multiple named CloudConnections for AWS, Azure, and
Google Cloud. A Twin selects one connection for every provider required by its
resolved graph. A connection records only the non-secret metadata needed to
make that choice, including provider, display name, target account scope,
allowed purpose, last readiness result, and validation timestamp.

Secret values are:

- write-only at API and Flutter boundaries;
- encrypted at rest;
- redacted from logs, errors, events, traces, exports, and support bundles;
- forwarded only to the selected Optimizer or Deployer operation; and
- replaced as a complete secret set rather than patched field by field.

Deletion removes the local encrypted connection. It does not claim to revoke
the identity in the provider.

## 4. Credential input

The UI supports both typed entry and a small allowlist of common provider
credential files. Import is a convenience parser, not a general file upload.

| Provider | Accepted PoC input | Required target metadata |
|---|---|---|
| AWS | access-key CSV or equivalent typed fields; optional session token for a supervised temporary session | account identity discovered by STS, intended regions |
| Azure | service-principal JSON or equivalent typed fields | tenant ID, subscription ID, client ID |
| GCP | service-account JSON or equivalent typed fields | existing billing-enabled project ID |

The exact schemas are versioned and allowlisted. Unknown keys, multiple
credentials in one file, executable content, provider CLI profiles with
implicit local dependencies, and arbitrary ZIP layouts are rejected. The
original file is not retained after validated field extraction.

Immediately after entry or import, a non-mutating identity probe verifies the
principal and target scope. It does not yet claim deployment readiness.

For Azure, typed entry requires both client IDs and secrets. Import accepts one
standard JSON document for the deployment principal plus typed preparation
client ID and secret fields; it does not retain or invent a two-file archive.
Both principals must resolve to the same tenant and subscription and their
client IDs must differ. Legacy single-principal Azure records remain listable
and deletable but must be replaced before readiness or deployment.

## 5. Graph-derived readiness

Readiness consumes the immutable resolved deployment graph, selected
CloudConnections, and region decisions. It must not infer requirements from a
generic provider permission pack.

The graph resolver emits typed requirements for:

- providers and target account scopes;
- resource and identity control planes;
- exact APIs or resource providers;
- regions, including distinct identity or federation regions;
- graph-specific permissions;
- quotas and regional capacity that can be queried;
- workload-identity routes and trust objects;
- runtime-access prerequisites; and
- services whose terms, preview status, or tenant consent require an external
  decision.

Every result is one of `ready`, `preparable`, `manual_action`,
`replace_connection`, `transient`, or `unsupported`. Deployment is disabled
until all mandatory graph requirements are `ready`.

## 6. Bounded provider preparation

The PoC may perform the following actions when the graph requires them and the
selected authority permits them:

| Provider | Automatically preparable after confirmation | Detect or guide only |
|---|---|---|
| AWS | enable the reviewed regional outbound-identity capability for an AWS-to-Azure route when an idempotent supported API exists | create account, payment setup, Service Quotas approval, organization policy, IAM Identity Center user activation and any irreversible account/organization decision |
| Azure | register the exact Azure resource providers required by the graph | subscription creation, billing recovery, quota approval, tenant-wide Microsoft Graph consent, policy exemptions |
| GCP | enable the exact Service Usage APIs required by the graph in an existing project | project/payment-account creation or linkage, quota approval, organization-policy changes, legal or preview approval |

Twin-scoped workload identities, trust objects, managed identities, service
accounts, and role assignments are deployment resources, not account
bootstrap. They remain in the Terraform graph and follow its reviewed
lifecycle.

Preparation actions must be idempotent, individually reported, and safe to
rerun. Persistent account capabilities are recorded separately from
Twin-owned resources and are not disabled by Twin Destroy because another Twin
may use them.

## 7. Region-sensitive AWS prerequisites

Three AWS region concepts must remain explicit:

1. the Six-layer resource region;
2. the IAM Identity Center primary Region used by the selected Amazon Managed
   Grafana login path; and
3. the regional STS endpoint used for AWS-to-Azure outbound workload identity.

IAM Identity Center has a primary Region whose selection has account-wide
consequences. The PoC detects and records it. If no compatible instance exists,
the supervised flow presents the exact provider link and manual decision
instead of silently choosing a primary Region.

AWS-to-Azure uses the reviewed regional STS token path. The global STS endpoint
is not an accepted fallback. This requirement is independent of dashboard
login and is included only when that directed route occurs in the graph.

## 8. Azure identity prerequisite

An Azure deployment that creates Entra application registrations, service
principals, federated identity credentials, or application role assignments
requires Microsoft Graph permissions in addition to Azure subscription roles.

Readiness tests both planes. Missing tenant consent is classified as
`manual_action`; it is not hidden behind a generic Owner-role check and is not
granted automatically by the PoC.

The deployment principal must have the resource actions required by the
Six-layer graph and must not have effective
`Microsoft.Authorization/roleAssignments/write` or `delete`. Terraform uses
this principal for the default AzureRM and AzAPI providers.

The preparation principal must have exactly one subscription-scoped **Role
Based Access Control Administrator** assignment with condition version 2.0.
The condition permits only the active Six-layer data/access role definitions
plus the identity-probe `Reader` role, and only `User` or `ServicePrincipal`
targets. Owner, Contributor, User Access Administrator, group targets,
unrestricted delegation, and ordinary resource write/delete authority are
rejected. Terraform uses this principal only for Azure role assignments and
Entra operations.

The same preparation principal requires exactly the Microsoft Graph
application permissions `Application.ReadWrite.OwnedBy`,
`Application.Read.All`, and `AppRoleAssignment.ReadWrite.All`, with tenant
administrator consent. Twin2MultiCloud verifies this consent but never grants
it.

## 9. Repair flow

Repair is an extension of readiness, not a generic administration console:

```text
select or import CloudConnections
              |
              v
identity and scope probes
              |
              v
graph-derived readiness
      |                    |
      | ready              | preparable/manual/invalid
      v                    v
deployment review     review exact actions
                           |
                           +-> confirm supported preparation
                           |       -> rerun readiness
                           |
                           +-> open provider-specific manual steps
                           |       -> rerun readiness
                           |
                           +-> replace CloudConnection
                                   -> rerun identity and readiness
```

An automatic preparation failure returns the failed action, sanitized provider
reason, retry safety, completed actions, remaining requirements, and the next
manual or credential-replacement option. A partially successful sequence is
never reported as a total success.

## 10. Confirmation contract

The preparation confirmation shows:

- provider, target account scope, and selected connection;
- each exact persistent account-level action;
- why the resolved graph requires it;
- whether Twin Destroy will revert it;
- the authority being exercised;
- external or manual prerequisites that remain; and
- a stable plan digest invalidated by any graph or connection change.

Deployment Apply has a separate confirmation. Confirming account preparation
does not implicitly confirm cost-incurring infrastructure.

## 11. Runtime access handoff

After verification, the Management API returns a typed, redacted AccessBundle
for each supported L4/L5 entry point:

- provider and architectural responsibility;
- URL and display label;
- authentication kind and assigned role;
- login identity or user name;
- readiness, expiry, and rotation information; and
- a one-time Viewer password or token only when the deployed service actually
  implements a resource-local credential.

For Amazon Managed Grafana and Entra-protected Azure surfaces, the bundle
normally contains the external URL and assigned SSO/Entra login identity. The
provider owns password setup, MFA, and login activation. For a bounded
service-local login, a generated Viewer secret may be revealed once and then
stored only in the provider secret service.

The bundle never contains the selected deployment administrator secret.

## 12. Explicit exclusions

- automatic creation, rotation, or provider-side revocation of deployment
  administrator identities;
- generated least-privilege deployment credentials and permission-pack
  versioning;
- production RBAC, multi-tenancy, approval workflows, and identity governance;
- account, subscription, payment profile, or billing-account creation;
- automatic quota-increase requests, policy overrides, tenant-wide consent,
  or legal/Marketplace acceptance;
- general-purpose repair scripting or arbitrary provider commands; and
- treating a successful identity probe as proof of complete readiness.

## 13. Current-state findings

The offline implementation now provides the intended service boundary:

- the resolved deployment graph projects provider scope, regions, exact APIs
  and Azure resource providers, permissions, quota probes, workload-identity
  routes, runtime-access prerequisites, and verification probes;
- a user can store multiple encrypted, named CloudConnections and bind one per
  required provider to a Twin;
- Management separates connection validation from graph-bound readiness,
  caches only redacted evidence, and invalidates stale graph or connection
  results;
- Deployer emits a deterministic preparation plan and executes only confirmed
  Azure resource-provider registration and GCP API enablement;
- partial preparation is reported action by action, remains retry-safe, and is
  followed by a readiness rerun; and
- AWS IAM Identity Center, regional outbound identity, and Azure Microsoft
  Graph authority are modeled separately from ordinary subscription or account
  permissions.

The remaining boundary is deliberately visible:

- AWS outbound-identity account enablement remains `manual_action`; the PoC has
  no reviewed automatic executor for it;
- external billing, quota, organization-policy, tenant-consent, and Marketplace
  steps remain manual or unsupported;
- GCP L4 uses the approved supervised console bootstrap in
  `docs/research/evaluation/gcp-l4-iap-bootstrap-runbook.md`; it is deliberately
  not an automatic credential executor and no OAuth client credential enters
  the repository or application;
- a manual acknowledgement records the supervised operator decision but is not
  substituted for a provider probe where a non-mutating probe exists;
- provider-specific text setup guides and canonical Settings links are
  available for AWS, Azure, and GCP without embedding provider identifiers or
  secrets; and
- Flutter exposes the digest-bound plan, warns about persistent account-level
  changes, confirms only the listed automatic actions, records individually
  selected manual acknowledgements, and renders the returned readiness result.

No live provider behavior is inferred from these offline contracts. Real
permissions, regional availability, quotas, API registration, partial-failure
behavior, and repeatability remain Phase 8 supervised evidence.

## 14. Verification boundary

Offline tests cover parsing, schema validation, encryption, redaction,
selection, graph requirement resolution, plan digests, confirmation, failure
classification, idempotency contracts, and AccessBundle secrecy.

Before the nine supervised Small deployments, low-cost provider probes verify
the real principal, exact target scope, region-sensitive prerequisites,
resource-provider/API state, Microsoft Graph access where needed, and all six
directed workload-identity exchanges.

The thesis evaluates whether pre-existing deployment authorities plus bounded
preparation can drive the closed-world Six-layer workflow safely enough for a
supervised PoC. It does not evaluate an identity-provisioning product.

## 15. Implementation dependency

The standalone Six-layer graph is now the cross-service source of truth. The
Management/Deployer readiness and account-preparation contracts and their
bounded Flutter confirmation/repair surface are implemented and covered
offline. Completion still requires supervised provider validation. This
section must not be read as live-cloud readiness evidence.

## 16. Provider references for implementation review

- [AWS IAM Identity Center regional behavior](https://docs.aws.amazon.com/singlesignon/latest/userguide/resiliency-regional-behavior.html)
- [Amazon Managed Grafana authentication](https://docs.aws.amazon.com/grafana/latest/userguide/authentication-in-AMG.html)
- [AWS outbound identity federation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_outbound_getting_started.html)
- [Azure resource providers and types](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types)
- [Google Cloud Service Usage enablement](https://cloud.google.com/service-usage/docs/enable-disable)
