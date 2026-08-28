---
title: "Twin2MultiCloud Thesis PoC Target Concept"
description: "Research-question-driven target scope for the final Twin2MultiCloud proof of concept."
tags: [architecture, thesis-scope, six-layer, evaluation]
lastUpdated: "2026-08-27"
version: "1.2"
---

# Twin2MultiCloud Thesis PoC Target Concept

Status: active target concept

## 1. Thesis objective

Twin2MultiCloud demonstrates how a theoretical, layer-based cost model can be
operationalized as a functionally gated, traceable, and reproducibly deployable
Digital Twin across AWS, Azure, and Google Cloud.

The proof of concept is not a general cloud-management product. Its success is
measured by whether it can answer the working research questions with explicit
contracts and reproducible evidence:

| Research question | PoC responsibility | Required evidence |
|---|---|---|
| RQ1: Operationalization | Transform typed Twin intent into a reviewed optimization result, a deterministic deployment graph, a supervised deployment, and verification evidence | contract trace, readiness result, deployment operation, verification and cleanup evidence |
| RQ2: Functional comparability | Admit only provider bundles satisfying the same mandatory Six-layer responsibilities | capability matrix, exclusion reasons, provider implementation evidence |
| RQ3: Cost effect | Compare functionally admissible single-cloud and multi-cloud allocations using one frozen cost method | cost trace, pricing snapshot, transfer/bridge attribution, sensitivity and limitations |
| RQ3.1: Baselines | Compare three provider-local baselines with the selected multi-cloud result under identical inputs | paired scenario results and assumptions |
| RQ3.2: Eventing responsibility | Make Eventing functionality, topology, delivery behavior, and cost explicit | event contract, directed bridge coverage, eventing cost contribution and live roundtrip evidence |

Engineering breadth is justified only when it produces one of these evidence
types or is necessary to execute them safely.

### Capability traceability gate

| Retained capability | Justification | Evidence or safety output |
|---|---|---|
| Standalone `six-layer-eventing@1` contract | RQ1, RQ2, RQ3.2 | one shared functional and deployment boundary |
| Cost-only scoring strategy | RQ3, RQ3.1 | deterministic monetary ranking and trace |
| Provider capability gate | RQ2 | admissible bundles and explicit exclusions |
| Frozen pricing snapshots | RQ3 | dated, cited, hashed, reproducible cost input |
| Resolved deployment graph | RQ1 | deterministic resource, identity, edge, and verification requirements |
| Multiple selectable CloudConnections | RQ1 and supervised repeatability | explicit provider-account binding without secret duplication |
| Graph-derived readiness and bounded preparation | RQ1 and mutation safety | reviewed prerequisites, confirmation, and repair evidence |
| Typed Twin configuration and bounded user functions | RQ1 and RQ2 | reproducible behavior-rich university scenario |
| Twin Duplicate and typed Export/Import | reproducibility | shareable secret-free experiment input |
| Immutable deployed Twin lifecycle | traceability and cost safety | no hidden recalculation or infrastructure update |
| Durable Deploy/Destroy operations with SSE replay | mutation and cost safety | reconnect without duplicated provider action |
| L4/L5 access bundle and telemetry roundtrip | RQ1 and RQ2 | usable endpoint and functional verification evidence |
| Three provider-local plus six directed multi-cloud scenarios | RQ1, RQ2, RQ3, RQ3.1, RQ3.2 | bounded live evidence across all providers and directions |

Any runtime capability that cannot be mapped to this table requires a scope
decision before implementation. Code-level extensibility alone is not a reason
to expose an inactive capability through contracts, APIs, persistence, or UI.

## 2. Canonical architecture

`six-layer-eventing@1` is the sole deployable cross-service architecture. It is
a standalone, closed-world contract owned directly by the Optimizer,
Management API, Deployer, Terraform projection, Flutter presentation, and
evaluation evidence.

The original Five-layer implementation remains an immutable, Optimizer-only
historical reproduction. It is not selectable in the normal workflow and has
no Management, Deployer, Terraform, Flutter, or live-E2E surface.

```text
Flutter
   |
   v
Management API
   |--------------------|
   v                    v
Cost Optimizer      Cloud Deployer
   |                    |
   +---- immutable -----+
        calculation,
        manifest and
        operation evidence
```

Flutter calls only the Management API. The Management API owns users, Twins,
CloudConnections, immutable calculation evidence, deployment lifecycle, public
errors, and operation history. The Optimizer owns pricing, formulas,
admissibility, cost scoring, and resolved deployment decisions. The Deployer
owns graph validation, packages, provider preparation, Terraform execution,
runtime verification, and cleanup.

The PoC retains one local owner profile so Twins and encrypted
CloudConnections have an explicit user boundary. Startup binds a configured
static local bearer to that profile; it does not expose interactive application
login. Google OAuth, Microsoft login, university SAML, JWT issuance, roles, and
multi-tenant session management are outside the runtime. The existing login
screen remains dormant and unrouted as a possible adapter boundary, not as a
supported capability. Provider-owned Entra, IAM Identity Center, IAP, OIDC, or
SAML mechanisms used by deployed cloud resources are separate from application
authentication and remain where the Six-layer graph requires them.

## 3. Supported user journey

The final PoC supports one cohesive workflow:

1. Create, import, or duplicate a draft Twin under a unique name.
2. Configure its typed workload, devices, events, state behavior, bounded user
   functions, simulator settings, and provider-independent Twin inputs.
3. Select one deployment CloudConnection per required provider from the
   user's existing connections.
4. Calculate the cost-only Six-layer result and review the selected provider
   allocation, exclusions, assumptions, and trace.
5. Run graph-derived provider readiness checks.
6. Review and explicitly confirm any bounded, persistent provider preparation.
7. Repair a failed preparation by following typed manual instructions or by
   replacing a CloudConnection, then rerun readiness.
8. Review the immutable deployment plan and explicitly confirm deployment.
9. Follow durable operation progress, verification, and logs even after a UI
   reconnect.
10. Receive the deployed L4/L5 access information and run the defined
    telemetry roundtrip.
11. Explicitly confirm Destroy and verify cleanup.

## 4. Twin lifecycle and immutability

A Twin can be edited while it is a draft. The calculation and deployment
evidence selected for deployment is immutable.

Once a Twin is deployed, its infrastructure configuration is not updated in
place. A changed architecture, workload, provider allocation, runtime package,
or credential binding produces a new draft through Duplicate or Import and is
calculated and deployed independently under a new Twin name.

The source Twin is never destroyed implicitly when it is duplicated. The user
owns the cost decision and may destroy either Twin explicitly.

The PoC supports:

- draft Create and Edit;
- Duplicate to a new Twin;
- typed Twin export and import for sharing or reproduction;
- immutable Deploy;
- explicit Destroy;
- independent Re-deploy only after a successful Destroy of the same Twin.

The PoC does not support in-place infrastructure updates, migrations,
rollbacks, continuous re-optimization, or automatic replacement of a deployed
Twin.

## 5. Configuration and extension boundary

The UI presents typed forms for the canonical configuration. It may also
import the corresponding validated individual configuration files so a user
can reuse an existing university experiment without assembling one arbitrary
deployment project.

Twin export/import is a versioned data interchange boundary, not a mechanism
for executing an arbitrary directory layout. An archive contains only
allowlisted Twin configuration, bounded extension sources and metadata, and
portable non-secret evidence. Cloud credentials, Terraform state, deployment
outputs containing secrets, and arbitrary executables are excluded.

User functions remain a bounded extension mechanism because processor,
rule/action, and feedback behavior is part of the evaluated university use
case. Their archive format, metadata, runtime, size, file types, and extension
slots are fixed and validated. General artifact catalogs, ownership workflows,
version histories, migrations, discovery, and arbitrary provider packages are
outside scope.

## 6. Optimization boundary

Only estimated monetary cost participates in scoring. A small internal
cost-scoring strategy and complete traceability remain as the extension
pattern. The normal API and UI do not expose objective registries, strategy
selection, weighted scoring, or disabled latency, sustainability, and
resilience objectives.

Possible future objectives are documented in one theoretical future-work
concept. They are not declared as planned product capabilities and do not add
inactive runtime branches.

## 7. CloudConnections and provider preparation

Users may store multiple encrypted CloudConnections per provider and select
one connection per required provider for a Twin. Credential values are
write-only, redacted from logs and responses, and forwarded only for the
current downstream request.

The operator supplies a pre-existing, non-root deployment administrator
credential for an isolated thesis account, subscription, or project. The PoC
does not create, rotate, or revoke that deployment authority. It may delete its
local encrypted CloudConnection, but provider-side revocation remains an
explicit operator action.

After a graph-derived, non-mutating readiness check, the PoC may prepare only
the exact account capabilities required by the selected deployment:

- register required Azure resource providers;
- enable required Google Cloud APIs;
- identify AWS outbound-identity prerequisites for a selected cross-cloud
  route and present the supervised manual action;
- create Twin-scoped runtime identities, roles, trust objects, service
  accounts, managed identities, and role assignments through the deployment.

Account-level changes are listed before execution, require explicit
confirmation, are idempotent, and are recorded separately from Twin-owned
resources. Twin Destroy does not undo shared provider capabilities.

Account or subscription creation, payment setup, billing recovery, quota
approval, organization-policy changes, tenant-wide consent, legal/preview
approval, and production credential lifecycle remain manual provider
responsibilities.

The detailed boundary is defined in
`docs/plans/2026-08-26_poc_credentials.md`.

## 8. Repair behavior

Repair is a bounded readiness workflow, not an administrative control plane.

```text
credential selection
       |
       v
non-mutating graph readiness
       |
       +---- pass -------------------------+
       |                                   |
       v                                   v
preparation plan                    deployment review
       |
       v
explicit confirmation
       |
       v
idempotent preparation
       |
       v
readiness rerun
       |
       +---- fail ---> manual action or replacement credential
```

Every failure states whether it is:

- automatically preparable;
- blocked by missing credential authority;
- an external billing, quota, capacity, policy, consent, or legal prerequisite;
- transient and safe to retry; or
- unsupported by the closed-world profile.

The user can inspect the planned action, apply supported preparation, open the
provider-specific manual instruction, or replace the selected connection.

## 9. Operation reliability

Deploy and Destroy can create costs and must not be duplicated because a UI
connection was interrupted. The Management API therefore persists operations,
correlation, terminal status, and bounded progress history. SSE is the live
transport, while reconnect, resume, and replay of persisted progress are part
of the PoC safety boundary.

This does not create a general event-streaming platform. One active operation
per Twin, idempotent command handling, bounded retention, and authoritative
terminal state are sufficient.

## 10. Runtime access handoff

Twin2MultiCloud does not embed or administer provider dashboards. After a
successful deployment it exposes a typed access bundle for every supported L4
and L5 surface:

- provider and responsibility;
- display name and URL;
- authentication kind;
- required login identity or user name;
- role and readiness state;
- expiry or rotation information where applicable;
- certificate fingerprint or network restriction when relevant;
- a one-time generated Viewer password or token only when the deployed service
  actually uses such a credential.

Deployment administrator secrets are never returned. AWS and Azure managed
surfaces normally redirect to IAM Identity Center, SAML, or Entra ID, so the
access bundle contains the link and assigned login identity rather than an
invented password. A generated resource-local credential, such as a bounded
Grafana Viewer for the GCP-hosted surface, is revealed once and can be rotated
through its narrow runtime operation.

AWS IAM Identity Center remains a provider prerequisite for the selected
Amazon Managed Grafana access path. Its primary Region is recorded explicitly
and must be compatible with the workspace. AWS-to-Azure workload identity is a
separate requirement and uses a regional STS endpoint.

## 11. Verification and live evaluation

Deterministic tests prove contracts, formulas, admissibility, state behavior,
redaction, graph resolution, package selection, and offline provider logic.
They are not live-cloud evidence.

Before cost-incurring deployments, the evaluation runs low-cost or read-only
provider gates:

- credential identity and target scope;
- required API/resource-provider state;
- exact graph-required permissions, including Azure Microsoft Graph rights;
- quota and regional capacity reads where available;
- all six directed workload-identity exchanges with minimal messages;
- image-build and service availability checks without full Twin load.

The final supervised evaluation targets nine Small scenarios:

- three provider-local deployments;
- six multi-cloud deployments covering every directed AWS/Azure/GCP provider
  pair at least once on the required cross-cloud Eventing or Twin-projection
  boundary.

Before execution, a generated coverage matrix must prove that the nine
scenarios cover the required provider directions and graph edge classes. A
scenario is not added merely to enumerate redundant layer assignments.

The checked scenario set and execution safeguards are defined by
`docs/research/evaluation/small-scenario-matrix.json` and
`docs/research/evaluation/live-evaluation-protocol.md`. They are plans, not
live-result evidence.

Every live run uses cost guardrails: reviewed Small inputs, no Large/preview
capacity, an explicit maximum duration, immediate verification, guaranteed
Destroy attempt, post-destroy inventory, and recorded residual-resource check.

## 12. Documentation boundary

The active repository retains:

- this target concept;
- one research-driven execution plan;
- focused architecture and security concepts;
- research method and evidence documentation;
- one development and decision log explaining important design rationale;
- one architecture-evolution trace separating inherited, reasoned,
  offline-verified, and live-validated changes;
- one provider-service evolution register for material service, tier, hosting,
  access-path, and support-component changes;
- focused future-work concepts without delivery promises; and
- minimal current component and operating documentation.

The durable rationale is recorded in
`docs/development_and_decision_log.md`; predecessor-to-target deltas and open
architecture decisions are recorded in
`docs/research/architecture_evolution.md`; service-level changes are recorded
in `docs/research/service_selection_evolution.md`. Superseded plans, handoffs,
and product roadmaps remain recoverable from Git history rather than being
presented as active project state.

Implementation handoffs, superseded phase plans, duplicate TODO lists, product
roadmaps, and documentation for removed behavior are deleted after their
information has been incorporated into the active sources. Git history remains
the archive.

## 13. Explicit non-goals

- general architecture-profile registration or inheritance;
- arbitrary topology and service selection;
- multi-objective optimization;
- Google, Microsoft, or university-SAML application login, JWT issuance,
  production authentication, RBAC, multi-tenancy, or identity governance;
- provider account creation and billing onboarding;
- automatic quota or organization-policy administration;
- arbitrary deployment projects and executable ZIP layouts;
- in-place deployment update, migration, rollback, or drift remediation;
- embedded Grafana administration or a general operations dashboard;
- exhaustive live testing of every valid layer permutation;
- production availability, scaling, installer, support, or FinOps claims.

## 14. Definition of done

The PoC is complete when:

1. active code and documentation expose only the target scope;
2. one immutable intent-to-cost-to-graph-to-deployment trace exists;
3. graph-derived readiness covers every selected provider and operation;
4. bounded provider preparation and manual repair are distinguishable;
5. deployment operations survive UI reconnect without duplicate mutation;
6. L4/L5 access bundles and telemetry verification are usable without an
   embedded dashboard;
7. all offline gates pass without real cloud mutation;
8. the nine supervised Small scenarios deploy, verify, destroy, and record
   residual-resource evidence, or produce an honestly classified provider
   blocker;
9. RQ1, RQ2, RQ3, RQ3.1, and RQ3.2 can each be answered from named evidence;
10. limitations and threats to validity clearly separate PoC evidence from
    product maturity.
