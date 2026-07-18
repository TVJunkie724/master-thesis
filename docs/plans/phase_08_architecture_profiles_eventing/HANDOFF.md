---
title: "Phase 8 Architecture Profiles And Eventing Handoff"
description: "Operational handoff for implementing the reviewed Phase 8 architecture-profile and Eventing roadmap without reinterpreting its scope."
tags: [architecture, eventing, handoff, roadmap, contracts, thesis]
lastUpdated: "2026-07-19"
version: "2.0"
---

<!-- SOURCES:
- docs/plans/phase_08_architecture_profiles_eventing/README.md
- docs/research/digital_twin_architecture_and_eventing_layer.md
- docs/research/research_questions_and_evaluation_design.md
- docs/research/related_work_multicloud_cost_comparability_eventing.md
- docs-site/docs/architecture/refactoring-roadmap.md
- Current repository code, contracts, tests, migrations, and Git history at master commit 5e675e77
- GitHub Phase 8 issue and native dependency graph
EXTRACTED: 2026-07-19 | VERSION: 2.0
-->

# Phase 8 Architecture Profiles And Eventing Handoff

## Handoff Status

| Field | Value |
|---|---|
| Repository | `TVJunkie724/master-thesis` |
| Integration branch | `master` |
| Planning base | `5e675e77` |
| Planning branch | `codex/phase-8-implementation-plans` |
| Parent issue | [#112 Audit and redesign the Digital Twin reference architecture beyond the bachelor baseline](https://github.com/TVJunkie724/master-thesis/issues/112) |
| Active prerequisite | [#113 Define and harden the user-function extension and packaging contract](https://github.com/TVJunkie724/master-thesis/issues/113) |
| Plan index | [`README.md`](README.md) |
| Planning status | Complete and reviewed; implementation has not started |
| First implementation phase | Phase 8.0 / [#144 Inventory the current Twin deployment graph and Function-and-Edge Matrix](https://github.com/TVJunkie724/master-thesis/issues/144) |
| Live cloud E2E | Deliberately deferred; never run without explicit user approval |
| LaTeX | Do not modify without separate user approval |

This document replaces the earlier pre-planning snapshot. The Phase 8 scope,
subphases, contract boundaries, blocker graph, verification gates, and
documentation ownership are now explicit. A future agent must start from the
reviewed plan for the current issue, not recreate a plan from chat history.

## Immediate Next Action

The next agent must begin with Phase 8.0 only:

1. verify that `master` contains this planning package;
2. confirm issue #144 is open and has no native blocker;
3. create `codex/phase-8-current-graph` from current `master`;
4. read
   [`phase_08_0_current_graph_reconstruction.md`](phase_08_0_current_graph_reconstruction.md)
   in full;
5. implement the source-backed inventory and checker exactly as planned;
6. run its safe verification gates;
7. review the implementation twice and fix every finding;
8. update the roadmap, current-system documentation, research evidence, and
   issue #144;
9. create a structured commit that references #144;
10. do not start Phase 8.1 while any Phase 8.0 finding remains.

The user-function prerequisite #113 can be implemented in parallel at the
project level, but Phase 8.3 must not finalize extension-slot catalog bindings
until #113 is complete.

## Required Reading Order

Read these sources before implementation:

1. [`README.md`](README.md), the Phase 8 mini-roadmap and execution order.
2. The implementation plan for the current issue.
3. [`docs/research/digital_twin_architecture_and_eventing_layer.md`](../../research/digital_twin_architecture_and_eventing_layer.md).
4. [`docs/research/research_questions_and_evaluation_design.md`](../../research/research_questions_and_evaluation_design.md).
5. [`docs/research/related_work_multicloud_cost_comparability_eventing.md`](../../research/related_work_multicloud_cost_comparability_eventing.md).
6. [`docs/plans/resolved_deployment_specification/README.md`](../resolved_deployment_specification/README.md).
7. [`docs-site/docs/contracts-and-data-flow/system-boundaries.md`](../../../docs-site/docs/contracts-and-data-flow/system-boundaries.md).
8. [`docs-site/docs/architecture/refactoring-roadmap.md`](../../../docs-site/docs/architecture/refactoring-roadmap.md).
9. `FRONTEND_ARCHITECTURE.md`, `integration_vision.md`, `ONBOARDING.md`, and
   each touched project's README before project-specific changes.
10. Current source, tests, migrations, generated contracts, and GitHub issue
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

- preserve an executable, paper-compatible `five-layer-baseline@1`;
- separate logical responsibilities from provider resources;
- encode reviewed architectures as versioned closed-world profiles;
- model provider implementations and deployment components explicitly;
- prove functional completeness before comparing costs;
- persist one immutable resolved architecture per accepted calculation run;
- derive deployment packages and Terraform inputs from a validated graph;
- keep platform wrappers, resource names, bindings, identities, permissions,
  and runtime policy out of user code;
- support one later, evidence-gated `six-layer-eventing@1` profile;
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
| 8.2 | [#149 Define versioned architecture profile contracts](https://github.com/TVJunkie724/master-thesis/issues/149) | Shared schemas and semantic validators |
| 8.3 | [#150 Register provider implementation profiles and deployment component catalog](https://github.com/TVJunkie724/master-thesis/issues/150) | Explicit provider and deployer realization |
| 8.4 | [#142 Persist resolved Twin architectures and migrate fixed layer assignments](https://github.com/TVJunkie724/master-thesis/issues/142) | Runtime SSOT and migration |
| 8.5 | [#151 Resolve architecture profiles in the Optimizer with functional completeness](https://github.com/TVJunkie724/master-thesis/issues/151) | Functional-total path optimization |
| 8.6 | [#152 Build the Deployer graph resolver and staged binding preflight](https://github.com/TVJunkie724/master-thesis/issues/152) | Deterministic Deployer graph |
| 8.7 | [#138 Implement the Flutter architecture profile workflow](https://github.com/TVJunkie724/master-thesis/issues/138) | Compact profile workflow |
| 8.8 | [#146 Complete the Eventing functional and cost decision gate](https://github.com/TVJunkie724/master-thesis/issues/146) | Approved or rejected Eventing decision package |
| 8.9 | [#140 Implement six-layer-eventing@1 across the platform](https://github.com/TVJunkie724/master-thesis/issues/140) | Executable `six-layer-eventing@1` |
| 8.10 | [#148 Produce Phase 8 evaluation evidence and final documentation](https://github.com/TVJunkie724/master-thesis/issues/148) | Evaluation package and final current docs |

Native dependency direction:

```text
#144 -> #139 -> #149 -> #150 -> #142 -> #151 -> #152
                     ^                          |       |
                     |                          |       +-> #146 --+
                    #113                        +-> #138 -----------+-> #140 -> #148 -> #112
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

Phase 8.8 is a decision gate, not implementation. It must establish:

- exact workload fields and normalized units;
- mandatory and optional functional capabilities;
- current primary-source evidence per provider;
- complete provider bundles rather than false service equivalence;
- exact fixed, usage, tier, retention, replay, transfer, bridge, and
  observability cost ownership;
- one provider-neutral event envelope and edge contract;
- retry, DLQ, replay, idempotency, ordering, schema, trust, and observability
  semantics;
- one explicit multi-cloud bridge decision;
- reproducible scenario calculations;
- rejected alternatives and residual uncertainty.

Official static provider prices are allowed when the provider offers no
machine-readable source, but they are reviewed, versioned evidence. They are
never a silent fallback.

Phase 8.9 may start only after `decision.json` is explicitly approved and all
AWS, Azure, and GCP Eventing bundles satisfy the same mandatory capability
contract. This does not imply that an all-GCP whole Twin path exists. Whole
paths remain positive only where the full profile capability matrix supports
every responsibility.

Phase 8.8 must also produce
`implementation-component-manifest.json`. It pins every selected service,
resource type, catalog/component ID, adapter, package, permission, formula,
port, binding, repository file target, and test owner. Phase 8.9 may not start
with an unresolved manifest entry or substitute another provider service.

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
- secret-free schemas, fixtures, API errors, logs, manifests, packages,
  tfvars, and documentation;
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

- `five-layer-baseline@1` is executable and hardened;
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
- `six-layer-eventing@1` is executable through the same generic boundaries;
- evaluation evidence maps RQ1, RQ2, RQ3, RQ3.1, and RQ3.2 to reproducible
  artifacts;
- current product/developer documentation is complete;
- research evidence remains separate from current-system docs and LaTeX;
- all safe gates pass and no review finding remains;
- final live E2E remains separately approved and supervised.

## Suggested First User Update

The next agent can begin with:

> Ich habe den finalen Phase-8-Handoff, die Mini-Roadmap, den GitHub-
> Blockergraph und den Plan fuer Phase 8.0 geprueft. Die Planung ist als
> begrenztes Closed-World-Modell mit einer gehaerteten
> `five-layer-baseline@1` und einem spaeteren, evidenz-gegateten
> `six-layer-eventing@1` abgeschlossen. Ich starte jetzt ausschliesslich mit
> der code-verifizierten Rekonstruktion des bestehenden Function-and-Edge-
> Graphen in #144. Live-Cloud-E2E und LaTeX bleiben unangetastet.
