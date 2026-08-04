---
title: "Phase 8 Architecture Profiles And Eventing Handoff"
description: "Operational handoff for implementing the reviewed Phase 8 architecture-profile and Eventing roadmap without reinterpreting its scope."
tags: [architecture, eventing, handoff, roadmap, contracts, thesis]
lastUpdated: "2026-08-05"
version: "4.3"
---

<!-- SOURCES:
- docs/plans/phase_08_architecture_profiles_eventing/README.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
- docs/research/digital_twin_architecture_and_eventing_layer.md
- docs/research/research_questions_and_evaluation_design.md
- docs/research/related_work_multicloud_cost_comparability_eventing.md
- docs-site/docs/architecture/refactoring-roadmap.md
- Phase 8.0 current graph, Phase 8.1 five-layer baseline decision, Phase 8.2
  architecture-profile contracts, and the #113 user-function prerequisite
- GitHub Phase 8 issue and native dependency graph
- GitHub issues #154 and #155 plus user implementation authorization on 2026-08-03
EXTRACTED: 2026-08-05 | VERSION: 4.3
-->

# Phase 8 Architecture Profiles And Eventing Handoff

## Handoff Status

| Field | Value |
|---|---|
| Repository | `TVJunkie724/master-thesis` |
| Integration branch | `master` |
| Planning base | `626e907a` |
| Planning branch | `codex/phase-8-service-bundle-closure` |
| Locally completed implementation | Phase 8.0 / #144 through Phase 8.7 / #138, prerequisite #113, and the offline guided-bootstrap closure / #154; open issues remain open until publication/merge |
| Parent issue | [#112 Audit and redesign the Digital Twin reference architecture beyond the bachelor baseline](https://github.com/TVJunkie724/master-thesis/issues/112) |
| Completed prerequisite | [#113 Define and harden the user-function extension and packaging contract](https://github.com/TVJunkie724/master-thesis/issues/113) |
| Plan index | [`README.md`](README.md) |
| Implementation status | Guided bootstrap contracts, safe persistence, deterministic adapters, generated v2 CloudConnection admission, shared Flutter flow, and offline integration are committed and zero-finding reviewed; real/demo architecture catalogs remain empty and all new profiles remain default-off |
| Next action | Branch from this reviewed boundary and implement `five-layer-baseline@2` / 8.9A |
| Live cloud E2E | Deliberately deferred; never run without explicit user approval |
| LaTeX | Do not modify without separate user approval |

Phase 8.0 reconstructed the current deployment graph and closed #144. Phase
8.1 froze the historical `five-layer-baseline@1` target with complete
decisions for all 114 current implementation records and all 90 current edges.
That baseline contains no general Eventing responsibility and keeps its
L4-to-L5-only target evidence unchanged. The new `five-layer-baseline@2`
corrects the runtime mismatch by making the deployed L3-hot-to-L5 raw-history
read explicit and replacing L3-hot-to-L4 query coupling with the typed
`twin_projection.v1` domain-event route. L3 hot and L5 share a provider; L4 is
independent. L4-to-L5 and 3D/Twin-context visualization are not claimed by v2.
Phase 8.2 provides all four Draft 2020-12 contracts, the semantic
registry, deterministic fixtures and digests, byte-identical service copies,
and validators with stable cross-service error codes.

Prerequisite #113 now supplies the canonical Python 3.11 slot/artifact/envelope
contracts, immutable owner-scoped artifacts and bindings, deterministic
AWS/Azure/GCP packages, shared runtime adapters, a compact Flutter workflow,
and fail-closed deployment handoff. Phase 8.3 maps the reviewed slot to exact
AWS, Azure, and GCP processing catalog entries while keeping runtime activation
dark until the later resolver phases. This is an execution extension inside
the five-layer baseline, not an Event Layer.

Phase 8.3 now provides one generated historical baseline profile, three provider profiles,
22 reviewed deployment bundles covering all 42 deployment-dimension
components, 33 Phase 8.1 decision-traced edge implementations, 43
content-addressed platform/shared artifacts, 51 parser-verified Terraform
resources, exact coverage of all 51 Phase 8.3/#113 retained component
decisions, exact variable/output/dimension/permission/pricing/formula
references, and deterministic supported/blocked fixtures. The completed #113
user-processor scenario is supported at the catalog-binding boundary without
activating profile selection. Those mappings remain dark/historical. AWS and
Azure are not made deployable by the graph compiler alone because the current
query bindings and shared-token runtime are invalid. GCP remains unsupported
in historical `@1`; Five-layer v2 instead targets the separately reviewed
provider-hosted GCP L3-hot/L5 and L4 implementations.

Phase 8.4 adds transactional migration 022, one pinned baseline profile per
Twin, optimistic profile selection with server-derived invalidation previews,
immutable canonical resolutions and query projections, owner-scoped read APIs,
append-only audit evidence, and a fixture-gated atomic Optimizer admission
boundary. Historical runs are reconstructed only from complete matching
evidence; all others are `legacy_not_resolvable` and deselected. The seven old
`cheapest_l*` layer/provider fields are now a tracked baseline compatibility
projection, not a generic architecture model.

Phase 8.5 adds the profile-bounded Optimizer strategy, pre-ranking functional
completeness, deterministic candidate resolution, exact cost and rejection
evidence, `ResolvedTwinArchitecture v1`, and default-off Management admission.
The repository-backed runtime path remains deliberately dark. Phase 8.6
provides the typed Deployer graph compiler but does not promote the historical
provider profiles. New-profile activation belongs to Phase 8.9A after the
complete-service decision.

Phase 8.6 now also provides synchronized DeploymentManifest v3 contracts,
deterministic graph/stage/binding compilation, graph-owned package selection,
typed allowlisted Terraform inputs, frozen graph evidence in Management and
Deployer operation state, selected-architecture-first compatibility
projections, and historical v2 read/destroy support without invalid-v3
fallback. Its integrated 14-stage credential-free gate passed all decision,
contract, Optimizer, Management, Deployer, Flutter, MkDocs, security, and
static checks. Activation remains deliberately default-off.

Phase 8.8 is approved independently as an offline evidence gate. Its twelve
schema-validated artifacts freeze `five-layer-baseline@2`,
`six-layer-eventing@1`, all six selected AWS/Azure/GCP bundles, all eight domain
channels, the exact profile-bound source-owned bridge runtimes and destination
broker APIs, a complete GCP BifroMQ/GKE-to-Pub/Sub device boundary,
66 reviewed primary sources, Small/Medium/Large calculations, an exact
non-executable Phase 8.9 component manifest, and two zero-finding review
records. This approval does not bypass Phases 8.6 or 8.7 and does not claim
live-cloud identity or capacity verification.
The stale native `#146 blocked by #152` relationship was removed because the
offline evidence is complete independently; #138 and the future 8.9A issue
still enforce the runtime implementation order.

The subsequent complete-service review found boundaries outside the Eventing
package: cross-provider storage movement, competing L3/L4 visualization
assumptions, the predecessor public Function/shared-token mechanism, conflated
Twin/scene entity counts, and complete GCP support. User review then removed unneeded
CDC/outbox/permanent-worker storage machinery, Spanner Graph, the default
dedicated Grafana node pool, mandatory L4-to-L5/3D visualization, and the ADX
migration. A follow-up correction also retains Firestore Native as GCP L3 hot
instead of changing the existing storage model to BigQuery merely for its
Grafana datasource; GCP Grafana now uses a typed Cloud Run reader and signed
Infinity datasource. The corrected target keeps Cosmos DB and Firestore L3,
uses finite scheduled storage jobs, couples L3 hot with L5, and places L4
independently. It freezes
`eu-central-1`/`westeurope`/`europe-west1`, uses
cumulative hot/cool/archive boundaries with non-overlapping cost intervals,
excludes L4-to-L5/3D paths from v2, and fails closed on unproven datasource
identity. The controlling plan
is [`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md),
with research evidence in
[`phase_08_service_bundle_evaluation.md`](../../research/phase_08_service_bundle_evaluation.md).

The subsequent post-deployment access review found one more functional gap:
resource outputs alone do not guarantee that the researcher can sign into and
inspect L4 and L5. The corrected boundary now requires a typed Layer Access
section in Twin Overview, provider-native interactive identity bindings,
deterministic semantic L4 content, and one raw/rollup Grafana dashboard in all
nine L3/L4/L5 placements. AWS uses TwinMaker console plus Managed Grafana,
Azure uses ADT Explorer plus Managed Grafana, and GCP adds a minimal
IAP-protected Cloud Run Twin Explorer beside Grafana OSS. GCP uses one
Firestore database per deployment with separate L3/L4 collection contracts;
the weaker database-wide IAM isolation is an explicit PoC limitation. The
binding feasibility and implementation order are frozen in
[`phase_08_layer_access_handoff.md`](phase_08_layer_access_handoff.md).

The subsequent credential review removed one more hidden prerequisite: a user
must not manually construct a bounded deployment CloudConnection before Phase 8
can deploy. When the resolved provider scope has no compatible connection, the
Management API receives one request-scoped bootstrap credential, creates and
validates the bounded deployment identity, persists only that CloudConnection,
and stops retaining the bootstrap secret after the request. The current
`thesis-demo-v1` permission packs remain bounded PoC baselines with documented
scope gaps, not a formal least-privilege proof. Disposable credential
revocation and mere application-side release are separate states. The
bootstrap session ends at a validated connection; AWS L4 organization-instance
activation, GCP no-organization/external OAuth, quota, billing, and policy
actions belong to the later Twin deployment preflight and resume through the
generated connection. Draft creation and calculation remain credential-free. The
binding contract is
[`phase_08_guided_cloud_bootstrap.md`](phase_08_guided_cloud_bootstrap.md).

The offline PoC implementation is complete on
`codex/phase-8-guided-bootstrap`. It provides strict synchronized contracts,
owner-scoped safe sessions, request-only credential handling, deterministic
AWS/Azure/GCP adapter behavior, encrypted generated `thesis-demo-v2`
CloudConnections, Deployer admission, and one shared Flutter flow from Settings
and Prepare deployment. Production remains fail-closed: no live provider
adapter is enabled, no cloud identity was created, and the existing reviewed
manual script/import path remains the supervised provider path. The isolated
OrbStack gate proved that the submitted sentinel was absent from Management
logs and SQLite persistence.

## Immediate Next Action

Do not activate a profile. Complete these boundaries in order:

1. retain the committed concept, cross-stack execution plans, immutable
   complete-service decision, reviewed dark Phase 8.6 compiler, zero-finding
   Phase 8.7 workflow, and reviewed offline guided-bootstrap boundary;
2. keep `five-layer-baseline@1`, Phase 8.5 admission, and all new profile
   execution default-off throughout that gate;
3. implement and review `five-layer-baseline@2` / 8.9A including Layer Access;
4. freeze the reviewed Five-layer v2 digest before starting the separate
   Six-layer delta; then complete Phase 8.10 evaluation.

## Required Reading Order

Read these sources before implementation:

1. [`README.md`](README.md), the Phase 8 mini-roadmap and execution order.
2. The implementation plan for the current issue.
3. [`phase_08_guided_cloud_bootstrap.md`](phase_08_guided_cloud_bootstrap.md),
   before any layer-access or deployment-credential work.
4. [`docs/research/digital_twin_architecture_and_eventing_layer.md`](../../research/digital_twin_architecture_and_eventing_layer.md).
5. [`docs/research/research_questions_and_evaluation_design.md`](../../research/research_questions_and_evaluation_design.md).
6. [`docs/research/related_work_multicloud_cost_comparability_eventing.md`](../../research/related_work_multicloud_cost_comparability_eventing.md).
7. [`docs/plans/resolved_deployment_specification/README.md`](../resolved_deployment_specification/README.md).
8. [`docs-site/docs/contracts-and-data-flow/system-boundaries.md`](../../../docs-site/docs/contracts-and-data-flow/system-boundaries.md).
9. [`docs-site/docs/architecture/refactoring-roadmap.md`](../../../docs-site/docs/architecture/refactoring-roadmap.md).
10. `FRONTEND_ARCHITECTURE.md`, `integration_vision.md`, `ONBOARDING.md`, and
   each touched project's README before project-specific changes.
11. Current source, tests, migrations, generated contracts, and GitHub issue
    state. Code is evidence of current behavior, not automatically the target.

For provider services, prices, permissions, quotas, and APIs, verify current
primary provider sources during the phase that owns the decision. Do not rely
on remembered provider behavior.

## Source-Of-Truth Hierarchy

If sources disagree, use this order:

1. the user's latest explicit instruction;
2. GitHub issues, milestones, and native blocker relationships;
3. reviewed implementation plans in this directory;
4. versioned repository contracts, schemas, fixtures, and semantic registries;
5. current code, migrations, tests, and generated artifacts;
6. current user/developer documentation in `docs-site/`;
7. research reasoning and evaluation design in `docs/research/`;
8. assessment and narrative roadmap material;
9. historical HTML, task trackers, Future Work, and predecessor artifacts as
   provenance only.

GitHub is the operational SSOT for status and dependencies. The plan files are
the implementation contract. Neither replaces the other.

## Non-Negotiable Scope

Phase 8 is a bounded architecture refactoring for the thesis. It must:

- preserve `five-layer-baseline@1` as paper-compatible, immutable historical
  evidence with read/verify/destroy compatibility only;
- add `five-layer-baseline@2` with mandatory embedded rule evaluation,
  extension actions, notification workflows, and device-command feedback;
- keep local direct-edge transport and topology-conditional cross-cloud
  outboxes/forwarders owned by the five-layer L1/L2 responsibilities;
- separate logical responsibilities from provider resources;
- encode reviewed architectures as versioned closed-world profiles;
- model provider implementations and deployment components explicitly;
- prove functional completeness before comparing costs;
- persist one immutable resolved architecture per accepted calculation run;
- derive deployment packages and Terraform inputs from a validated graph;
- keep platform wrappers, resource names, bindings, identities, permissions,
  and runtime policy out of user code;
- support one later, evidence-gated `six-layer-eventing@1` profile with the
  same domain-event behavior as `five-layer-baseline@2`;
- remove the three legacy Eventing feature flags from both new profiles while
  preserving historical read/destroy compatibility;
- retain Web, macOS, Windows, and Linux Flutter support;
- keep product documentation, research evidence, and LaTeX separate.

Phase 8 must not:

- become a free-form architecture or graph editor;
- allow users to add arbitrary layers or services at runtime;
- generate Terraform dynamically;
- assume provider services are one-to-one equivalents;
- let Flutter or clients author resolved architecture evidence;
- insert brokers between every helper function;
- hide unsupported paths or incomplete capabilities behind defaults;
- use stale/static prices as silent live fallbacks;
- run paid provider operations during ordinary tests;
- modify the LaTeX thesis without approval.

The result is a closed-world model: runtime choices are limited to reviewed
profile versions, while developers can add another version through explicit
contracts, provider profiles, catalog entries, tests, and documentation.

## Canonical Architecture Model

The target consists of four separate records:

```text
ArchitectureProfile
  logical responsibilities, components, edges, workload fields,
  extension slots, graph policy, and optimization bundle

ProviderImplementationProfile
  reviewed AWS/Azure/GCP implementation of those logical components

DeploymentComponentCatalog
  provider adapter, package, Terraform module/resource, ports,
  outputs, permissions, and binding contract for each component

ResolvedTwinArchitecture
  immutable concrete profile resolution for one calculation run
```

The architecture result references, but does not duplicate,
`ResolvedDeploymentSpecification`. The architecture contract answers what
components and edges exist and which provider implementations were selected.
The deployment specification answers the exact provider-specific dimensions
such as SKU, runtime, memory, storage class, capacity, schedule, and billing
mode.

Terraform remains explicit static HCL. The change is that resource references
and values are derived from registered components, declared outputs, and
validated bindings before planning. Terraform must not depend on duplicated
string conventions or user functions constructing another resource's identity.

## Phase And Issue Order

| Phase | Issue | Full outcome |
|---|---|---|
| Prerequisite | [#113 Define and harden the user-function extension and packaging contract](https://github.com/TVJunkie724/master-thesis/issues/113) | Deterministic v1 extension boundary with typed non-secret configuration |
| 8.0 | [#144 Inventory the current Twin deployment graph and Function-and-Edge Matrix](https://github.com/TVJunkie724/master-thesis/issues/144) | Code-verified Function-and-Edge Matrix |
| 8.1 | [#139 Harden and freeze the five-layer-baseline@1 architecture profile](https://github.com/TVJunkie724/master-thesis/issues/139) | Normative `five-layer-baseline@1` decision |
| 8.2 | [#149 Define versioned architecture profile contracts](https://github.com/TVJunkie724/master-thesis/issues/149) | Implemented shared schemas, semantic registry, fixtures, dark readers, and drift gates |
| 8.3 | [#150 Register provider implementation profiles and deployment component catalog](https://github.com/TVJunkie724/master-thesis/issues/150) | Explicit provider and deployer realization |
| 8.4 | [#142 Persist resolved Twin architectures and migrate fixed layer assignments](https://github.com/TVJunkie724/master-thesis/issues/142) | Runtime SSOT and migration |
| 8.5 | [#151 Resolve architecture profiles in the Optimizer with functional completeness](https://github.com/TVJunkie724/master-thesis/issues/151) | Functional-total path optimization |
| 8.6 | [#152 Build the Deployer graph resolver and staged binding preflight](https://github.com/TVJunkie724/master-thesis/issues/152) | Implemented dark deterministic Deployer graph, binding/package preflight, typed Terraform projection, and frozen graph evidence |
| 8.7 | [#138 Implement the Flutter architecture profile workflow](https://github.com/TVJunkie724/master-thesis/issues/138) | Compact profile workflow |
| 8.8 | [#146 Complete the Eventing functional and cost decision gate](https://github.com/TVJunkie724/master-thesis/issues/146) | Shared domain-event contract plus approved or rejected embedded/Event-Layer decision package |
| Service closure | [#155 Implement complete five-layer-baseline@2 across the platform](https://github.com/TVJunkie724/master-thesis/issues/155) | Complete AWS/Azure/provider-hosted-GCP bundles, storage routes, workload/capacity semantics, and immutable decision package |
| Guided bootstrap | [#154 Implement guided cloud access bootstrap for bounded deployment identities](https://github.com/TVJunkie724/master-thesis/issues/154) | Request-scoped bootstrap authority and reusable bounded CloudConnections |
| 8.9A | [#155 Implement complete five-layer-baseline@2 across the platform](https://github.com/TVJunkie724/master-thesis/issues/155) | Executable `five-layer-baseline@2` with complete service bundles |
| 8.9B | [#140 Implement six-layer-eventing@1 across the platform](https://github.com/TVJunkie724/master-thesis/issues/140) | Planned strict Event Layer delta; branch starts only from reviewed 8.9A |
| 8.10 | [#148 Produce Phase 8 evaluation evidence and final documentation](https://github.com/TVJunkie724/master-thesis/issues/148) | Planned after reviewed Six-layer; historical `@1` reproduction plus fair `@2` versus Six-layer evaluation |

Native dependency direction:

```text
#144 -> #139 -> #149 -> #150 -> #142 -> #151 -> #152
                     ^                                  |
                     |                                  +-> #138 --------+
                    #113                                                 |
            #146 -> complete-service decision ---------------------------+-> 8.9A -> #140 -> #148 -> #112
```

Do not replace native blockers with comments or body text. Do not add a blocker
merely because two issues are related.

## Plan Index

| Work item | Reviewed plan |
|---|---|
| #113 prerequisite | [`prerequisite_user_function_extension_contract.md`](prerequisite_user_function_extension_contract.md) |
| #144 / Phase 8.0 | [`phase_08_0_current_graph_reconstruction.md`](phase_08_0_current_graph_reconstruction.md) |
| #139 / Phase 8.1 | [`phase_08_1_five_layer_baseline.md`](phase_08_1_five_layer_baseline.md) |
| #149 / Phase 8.2 | [`phase_08_2_profile_contracts.md`](phase_08_2_profile_contracts.md) |
| #150 / Phase 8.3 | [`phase_08_3_provider_profiles_component_catalog.md`](phase_08_3_provider_profiles_component_catalog.md) |
| #142 / Phase 8.4 | [`phase_08_4_management_persistence_migration.md`](phase_08_4_management_persistence_migration.md) |
| #151 / Phase 8.5 | [`phase_08_5_optimizer_profile_resolution.md`](phase_08_5_optimizer_profile_resolution.md) |
| #152 / Phase 8.6 | [`phase_08_6_deployer_graph_resolver.md`](phase_08_6_deployer_graph_resolver.md) |
| #138 / Phase 8.7 | [`phase_08_7_flutter_profile_workflow.md`](phase_08_7_flutter_profile_workflow.md) |
| #146 / Phase 8.8 | [`phase_08_8_eventing_decision_gate.md`](phase_08_8_eventing_decision_gate.md) |
| Complete-service closure | [`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md) |
| #140 / Phase 8.9 | [`phase_08_9_six_layer_eventing_implementation.md`](phase_08_9_six_layer_eventing_implementation.md) |
| #148 / Phase 8.10 | [`phase_08_10_evaluation_and_documentation.md`](phase_08_10_evaluation_and_documentation.md) |

Each file is a complete implementation plan. Its contracts, failure behavior,
test matrix, documentation tasks, rollout rules, and Definition of Done are
mandatory.

## User-Function Boundary

Issue #113 is deliberately narrower than a general serverless platform:

- v1 supports Python 3.11 only;
- a user supplies domain source, a deterministic dependency lock, and typed
  non-secret configuration;
- the platform owns wrappers, handler names, resources, topology, permissions,
  observability, and runtime policy;
- source is never rewritten or executed during packaging;
- identical canonical inputs produce identical logical artifact and provider
  package digests;
- user-managed secret values and secret references are rejected in v1;
- existing unvalidated source remains readable but cannot be used for a new
  deployment without explicit import and validation.

[Issue #153 Design provider-managed secrets for user-function extensions](https://github.com/TVJunkie724/master-thesis/issues/153)
owns that separate hardening work. It is not a hidden part of Phase 8. Adding
it requires provider secret stores, runtime identities, permissions, rotation,
lifecycle, pricing, audit, and a write-only UI contract. Never reuse
`CloudConnection` secrets as function runtime configuration.

## Flutter Boundary

Flutter talks only to the Management API. The app retains its existing hybrid
state split:

- Riverpod owns runtime composition, environment mode, authentication/theme
  composition, and API adapter injection;
- feature BLoCs own complex workflows and transitions such as the
  configuration workspace and deployment lifecycle;
- widgets render typed state and never call Dio directly.

Phase 8.7 adds an `ArchitectureApi` capability interface to the existing
`ManagementApi` composition. `ApiService` and `DemoManagementApi` implement the
same interface. Integration tests use the real local Management API; only unit
tests may substitute the capability interface.

The profile workflow remains compact:

```text
Architecture
  -> Workload
  -> User Logic
  -> Optimize And Review
  -> Deployment Review
```

The UI is a read-only architecture review and supported-field editor, not an
infrastructure designer. Server DTOs determine active profiles, workload
fields, extension slots, invalidation impact, and resolved evidence.

All UI work must preserve Web, macOS, Windows, and Linux gates. Mobile remains
out of scope.

## Profile-Change Safety

Profile changes use a server-derived preview:

```text
POST /twins/{twin_id}/architecture-profile/change-preview
  -> invalidated workload categories
  -> incompatible extension bindings
  -> selected-run and readiness invalidation
  -> deterministic invalidation_digest

PUT /twins/{twin_id}/architecture-profile
  + expected revision
  + invalidation_digest
```

The server recomputes the digest in the write transaction. A stale digest fails
with `ARCH_SELECTION_INVALIDATION_STALE`; Flutter reloads the preview and
requires confirmation again. Changing a profile may unbind only incompatible
Twin-scoped values. It never deletes CloudConnections, credentials, source
artifacts, or historical run evidence.

## Eventing Boundary

Phase 8.8 is an approved decision gate, not implementation. It establishes:

- the immutable role of `five-layer-baseline@1`;
- one shared domain-event behavior contract for
  `five-layer-baseline@2` and `six-layer-eventing@1`;
- mandatory embedded rule/action/workflow/command components in both new
  profiles without the legacy Eventing feature flags;
- exact immutable Eventing workload fields and normalized units, selected for
  runtime through one server-resolved `eventingScenarioId` rather than inline
  caller values;
- graph-derived per-channel fan-out and directed cross-cloud routes;
- mandatory and optional functional capabilities;
- current primary-source evidence per provider;
- complete provider bundles rather than false service equivalence;
- exact fixed, usage, tier, retention, replay, transfer, bridge, and
  observability cost ownership;
- one provider-neutral event envelope and edge contract;
- retry, DLQ, replay, idempotency, ordering, schema, trust, and observability
  semantics;
- one exact multi-cloud bridge decision with source-broker triggers,
  provider-specific forwarder runtimes, destination broker data-plane APIs,
  short-lived identity exchanges, and destination-acceptance acknowledgement;
- reproducible scenario calculations;
- capacity evidence for Small, Medium, and Large before cost reporting;
- same-cloud, all six directed provider-pair, and admissible three-provider
  scenarios;
- rejected alternatives and residual uncertainty.

Official static provider prices are allowed when the provider offers no
machine-readable source, but they are reviewed, versioned evidence. They are
never a silent fallback.

`decision.json` is explicitly approved and all
AWS, Azure, and GCP embedded-event and Event-Layer bundles satisfy their
applicable offline capability contracts. Phase 8.9 still waits for Phase 8.7,
its new 8.9A issue, and closed native blockers. 8.9A and 8.9B use separate
branches, reviews, and clean commits. That Event-domain approval alone does not
imply that an all-GCP whole Twin path exists. The complete-service closure now
makes provider-hosted all-GCP a mandatory new-profile implementation target;
whole paths become positive only after its full capability matrix supports
every responsibility.

Phase 8.8 also produced
`implementation-component-manifest.json`. It pins every selected service,
resource type, catalog/component ID, adapter, package, permission, formula,
port, binding, repository file target, and test owner within the Event-domain
scope. The separate complete-service manifest owns storage, the L3-hot/L5
bundles, independent L4, raw-visualization and Twin-projection edges, workload,
and whole-profile capacity targets. Phase 8.9A may not start with an unresolved
entry in either manifest or substitute another provider service.

## Contract Evolution

The reviewed version sequence is:

| Contract | Baseline phase | Eventing phase |
|---|---|---|
| `ResolvedTwinArchitecture` | v1, already generic by responsibility/component | v1 remains valid |
| `ResolvedDeploymentSpecification` | v1 for baseline slot-based historical compatibility | v2 adds generic component deployment selections |
| `DeploymentManifest` | Current v2 remains historical; v3 carries RTA v1 and RDS v1 | v4 carries RTA v1 and RDS v2; v2/v3 remain historical read/destroy |
| `ResolvedDeploymentGraph` | v1 generic graph | v1 extended through catalog data |

New operations use the current version only. Historical versions remain
readable and destroyable. Invalid current contracts never fall back silently to
an older executable path.

## Documentation Ownership

Every implementation phase must update documentation:

| Information | Destination |
|---|---|
| Current setup, operation, configuration, troubleshooting | `docs-site/docs/` |
| Current contracts, data flows, profile extension, deployment behavior | `docs-site/docs/contracts-and-data-flow/` and developer guide pages |
| Architecture reasoning, alternatives, limitations, research questions, evaluation | `docs/research/` |
| Reviewed implementation contract | `docs/plans/` or project `implementation_plans/` |
| Status, dependencies, review evidence | GitHub issues and milestones |
| Thesis prose | `twin2multicloud-latex`, only after explicit approval |

Current product documentation must never describe a target profile as already
implemented. Research conclusions must not be mixed into setup or developer
instructions.

## Safe Verification Policy

Ordinary Phase 8 verification must be credential-free and no-apply.

Repository entry points include:

```bash
./thesis.sh test deployment-contract
./thesis.sh test backend
./thesis.sh test frontend
./thesis.sh test frontend-integration
docker compose --profile docs run --rm docs mkdocs build --strict
```

Each phase plan lists narrower commands and fixtures. Before running Docker
commands, resolve current Compose service names yourself. Do not ask the user
to execute commands.

Run Management pytest commands that use the default repository-local
`./test.db` serially with `./thesis.sh test deployment-contract` in one
worktree. Their create/drop lifecycle is not a parallel-safe shared database
boundary.

Never run:

- `terraform apply` or destroy against a real provider;
- provider bootstrap/import with live credentials;
- pricing refresh that requires paid or account-scoped operations unless the
  phase explicitly permits a safe read and the user has approved it;
- `tests/e2e/` or final full-application E2E;
- any operation that can create cloud resources or costs.

The final supervised E2E protocol is prepared in Phase 8.10 but remains
unexecuted until the user explicitly decides to run it after the manual visual
UI audit.

## Security And Quality Rules

Every phase must preserve:

- typed and versioned cross-project contracts;
- fail-closed unknown-version and unsupported-path behavior;
- deterministic canonical JSON and digest chains;
- idempotent, tested migrations;
- immutable accepted calculation and architecture evidence;
- ownership checks and optimistic revisions for mutable Twin selections;
- secret-free schemas, fixtures, API errors, logs, manifests, tfvars,
  deterministic function/artifact packages, package evidence, and
  documentation;
- credential-bearing deployment operation packages only inside the existing
  private, short-lived, one-use package boundary with owner-only permissions,
  redaction, acquisition, TTL, and cleanup guarantees;
- structured errors, correlation, redaction, and bounded diagnostic evidence;
- deterministic package and Terraform input generation;
- cleanup, retry, recovery, and destroy behavior for historical operations;
- broad unit, contract, integration, migration, security, provider-adapter,
  package, Terraform no-apply, Flutter, and documentation tests proportional
  to the phase.

No stub, fake production implementation, permissive fallback, or quick patch is
an acceptable target. Demo adapters are allowed only behind the existing demo
runtime provider boundary and must implement the same typed contract.

## Per-Phase Working Protocol

For every phase:

1. confirm issue state, full title, milestone, labels, and native blockers;
2. read the entire plan and all predecessor artifacts;
3. create the recommended feature branch from current `master`;
4. implement only the declared scope;
5. run focused tests first;
6. run all relevant safe project and cross-contract gates;
7. review implementation against the plan from architect and builder
   perspectives;
8. perform a second review for code quality, security, errors, migrations,
   compatibility, regression, and documentation drift;
9. fix all findings and rerun affected gates;
10. update current documentation, research evidence, roadmap, and issue body or
    comment with named evidence;
11. create a structured commit with `Refs #<issue>` or `Closes #<issue>` only
    when the issue is genuinely complete;
12. merge and push only according to the active user instruction;
13. begin the next phase only when zero findings remain.

Do not combine multiple Phase 8 implementation phases into one giant commit.
Shared contract changes can span projects, but the phase boundary must remain
auditable and reversible.

## Definition Of Ready

The planning package is ready for implementation when:

- every plan file and link exists;
- every phase has exact scope, non-goals, ownership, data contracts, failure
  behavior, security, observability, migration/compatibility rules, test
  commands, documentation tasks, and a verifiable Definition of Done;
- GitHub issues use full descriptive titles and correct milestones/labels;
- native blockers match the roadmap graph;
- #113 reflects the non-secret v1 boundary;
- provider-managed user-function secrets are tracked separately;
- strict local documentation and plan-link validation passes;
- the planning commit is reachable by the next agent.

## Definition Of Done For Phase 8

Phase 8 is complete only when:

- `five-layer-baseline@1` remains immutable historical
  read/verify/destroy evidence;
- `five-layer-baseline@2` is executable with mandatory embedded domain-event
  behavior;
- all four architecture contracts are versioned and drift-gated;
- provider implementations and deployment components are explicit;
- the Management API is the normalized runtime SSOT;
- the Optimizer ranks only complete paths within one profile;
- the Deployer resolves every graph and binding before Terraform;
- Flutter exposes compact profile selection and read-only evidence through the
  Management API;
- the user-function v1 extension boundary is deterministic and secure;
- the Eventing decision package is reproducible and approved;
- the approved Eventing implementation-component manifest pins every
  cross-project implementation target and remains in the evaluation digest
  chain;
- the approved complete-service manifest pins every finite storage job,
  L3-hot/L5 bundle, independent L4 placement, raw-history query, Twin
  projection, provider-hosted GCP, Cosmos capacity mode, workload, identity,
  and cost target;
- `six-layer-eventing@1` is eventually executable only from a separate plan
  reviewed against the committed Five-layer v2 baseline;
- `five-layer-baseline@2` and `six-layer-eventing@1` implement the same
  rule/action/workflow/command contract without legacy feature flags;
- evaluation evidence maps RQ1, RQ2, RQ3, RQ3.1, and RQ3.2 to reproducible
  artifacts;
- current product/developer documentation is complete;
- research evidence remains separate from current-system docs and LaTeX;
- all safe gates pass and no review finding remains;
- final live E2E remains separately approved and supervised.

## Suggested First User Update

The next agent can begin with:

> Phase 8.0 bis 8.5 und das User-Function-Prerequisite #113 sind implementiert
> und reviewt; Phase 8.8 ist als Offline-Entscheidungspaket freigegeben.
> `five-layer-baseline@1` bleibt historische Evidenz,
> `five-layer-baseline@2` und `six-layer-eventing@1` teilen dieselben
> verpflichtenden Rule-/Action-/Workflow-/Feedback-Funktionen, und nur das
> Six-Layer-Profil besitzt eine unabhaengige Eventing-Verantwortung. Als
> naechstes benoetigt der korrigierte Service-Plan die Benutzerfreigabe;
> danach folgt das immutable Complete-Service-Entscheidungspaket und erst dann
> der Abschluss von Phase 8.6. Danach folgen 8.7 und 8.9A; 8.9B wird erst auf
> dem reviewten Five-Layer-Stand neu geplant. Live-Cloud-E2E und LaTeX bleiben
> unangetastet.
