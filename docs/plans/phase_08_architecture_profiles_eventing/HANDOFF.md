# Phase 8 Architecture Profiles And Eventing Handoff

## Handoff Metadata

| Field | Value |
|---|---|
| Prepared | 2026-07-19 |
| Repository | `TVJunkie724/master-thesis` |
| Primary local checkout at handoff time | `/Users/caroline/development/private/master-thesis` |
| Current branch at handoff time | `codex/contract-dataflow-diagrams` |
| Latest functional commit before this handoff | `b61f98a6 docs(architecture): add contract data flow reference` |
| Base branch | `master` at `ccf7c124` |
| Current branch relation to `master` | 67 commits ahead, 0 behind |
| Remote state | `codex/pricing-tier-finalization` is pushed at `154cf32a`; `codex/contract-dataflow-diagrams` is not pushed at handoff time |
| Main Phase 8 issue | [#112 Audit and redesign the Digital Twin reference architecture beyond the bachelor baseline](https://github.com/TVJunkie724/master-thesis/issues/112) |
| Active prerequisite | [#113 Define and harden the user-function extension and packaging contract](https://github.com/TVJunkie724/master-thesis/issues/113) |
| Live E2E status | Deliberately deferred; do not run without explicit user approval |

This document is the operational handoff for the next agent. It is not a
replacement for the canonical product documentation, GitHub Issues, research
notes, or future Phase 8 implementation plans.

## Start Here

The next agent should:

1. communicate with the user in German;
2. work calmly and autonomously without asking the user to run Docker or Git
   commands;
3. inspect the current checkout and branch before changing anything;
4. preserve all existing user changes and local credential files;
5. read the documents listed under [Required Reading Order](#required-reading-order);
6. reconcile the current branch before creating another feature branch;
7. finish the remaining current-platform work before implementing the Eventing
   profile;
8. create and review one bounded Phase 8 implementation plan at a time;
9. implement one phase, test it, review it twice, fix all findings, update
   documentation and roadmap status, and commit before starting the next phase;
10. keep real-cloud E2E and final application E2E deferred until the user
    explicitly approves them.

Do not begin by inventing new architecture contracts from chat memory. The
research decisions are already recorded and must be translated into explicit
implementation contracts.

## Source-Of-Truth Hierarchy

Use the following hierarchy when sources appear to disagree:

1. the user's latest instruction;
2. GitHub Issues and native dependency relationships for active work;
3. reviewed plans in `docs/plans/` and project `implementation_plans/`;
4. current code, schemas, tests, migrations, and generated contract fixtures;
5. canonical product and developer documentation in `docs-site/`;
6. thesis research reasoning in `docs/research/`;
7. `ASSESSMENT.md` and the narrative roadmap;
8. historical HTML, TODO, future-work, and predecessor files as provenance only.

The current `.agent/workflows/onboarding.md` branch rules supersede the older
project skill text that still mentions `ai/dev`. Continue an existing feature
branch when appropriate. For new isolated work, branch from the intended
integration head using the `codex/` prefix. Never work directly on `master`.

## User Expectations

These expectations have been consistent throughout the project and are
non-negotiable:

- The result should be enterprise-grade and thesis-ready, but remain bounded to
  the actual thesis objective.
- Do not build a general dynamic cloud-architecture engine.
- Do not use stubs, fake implementations, silent fallbacks, quick fixes, or
  temporary patches as the target design.
- Preserve existing functionality and prove it with broad, risk-based tests.
- Use typed contracts, explicit ownership, fail-closed validation, uniform
  error handling, redaction, structured logging, deterministic artifacts, and
  auditable migrations.
- Keep Flutter thin. Flutter calls only the Management API, never the Optimizer
  or Deployer directly.
- Keep UI screens compact and progressive. Detailed evidence belongs in
  collapsed diagnostics or dedicated review views, not in an overloaded primary
  workflow.
- Keep Web, macOS, Windows, and Linux within the supported Flutter application
  contract.
- Keep the offline demo path functional and representative through fake
  repository/provider adapters, not scattered mock conditionals.
- Update documentation with every behavioral or architectural change.
- Product/developer documentation explains the implemented system. Thesis
  decisions, evaluation reasoning, limitations, and research interpretation
  remain in `docs/research/` until explicitly moved into LaTeX.
- Do not edit `twin2multicloud-latex` without explicit user approval.
- Do not print, inspect in chat, delete, move, or commit real credentials.
- Do not run live-cloud E2E or tests that may create resources or costs without
  explicit user approval.

## Current System Boundary

```text
Flutter (Web and desktop)
    |
    | typed HTTP/SSE contracts
    v
Management API :5005
    |                         |
    | typed optimizer client  | typed deployer client
    v                         v
Optimizer :5003              Deployer :5004
    |                         |
    | pricing evidence        | DeploymentManifest
    | calculation result      | resolved specification
    | resolved selection      | ephemeral workspace
    v                         v
Management persistence       Terraform providers
```

Project responsibilities:

| Project | Owns | Must not own |
|---|---|---|
| `twin2multicloud_flutter` | User interaction, local presentation state, typed Management API adapters, read-only evidence review | Cloud credentials, cost formulas, provider deployment decisions, direct Optimizer/Deployer access |
| `twin2multicloud_backend` | User/twin/configuration persistence, CloudConnection SSOT, calculation-run selection, orchestration, lifecycle, API projection | Provider-specific Terraform knowledge or independent cost decisions |
| `2-twin2clouds` | Workload/pricing intents, provider evidence, formulas, optimization strategies, capability gates, resolved deployment selections | Deployment execution, user persistence, arbitrary topology generation |
| `3-cloud-deployer` | Manifest validation, provider adapters, deployment graph realization, ephemeral workspaces, Terraform execution, deployment evidence | User state, cost optimization, client-authored resource decisions |
| `docs-site` | Current user, operator, developer, contract, setup, and architecture documentation | Thesis argumentation or unpublished research conclusions |
| `docs/research` | Research questions, predecessor analysis, reasoning, evaluation design, related work, and threats to validity | Claims that unimplemented research candidates are current product behavior |

The dedicated current contract documentation starts at:

- local: `http://localhost:5010/contracts-and-data-flow/`
- source: `docs-site/docs/contracts-and-data-flow/`

The branch adds seven contract/data-flow pages and preserves the existing ASCII
diagrams. It does not replace those diagrams.

## Git State And Integration Warning

At handoff time:

```text
master
  ccf7c124 merge: document twin architecture research direction
       \
        ... 66 commits ...
          154cf32a docs(roadmap): close deployment drift phase
               \
                b61f98a6 docs(architecture): add contract data flow reference
```

Important consequences:

- The current branch contains the complete resolved-deployment-specification
  work plus the new contract documentation.
- Creating a fresh Phase 8 branch directly from `master` now would omit 67
  commits of completed work.
- Do not reimplement missing behavior merely because it is absent on `master`.
- First review the current feature history and working tree.
- Integrate the current branch according to the user's instruction before
  starting an unrelated feature branch.
- The current contract-doc branch was not pushed when this handoff was written.
- `codex/pricing-tier-finalization` is pushed and is the parent branch at
  `154cf32a`.

Recommended inspection commands:

```bash
git status --short --branch
git log --oneline --decorate -15
git rev-list --left-right --count master...HEAD
git diff --stat master...HEAD
```

Do not reset, checkout files destructively, or discard local untracked
credentials.

Ignored real credential files are present locally at the repository root and
under `3-cloud-deployer/upload/template/`. Their contents were not inspected
for this handoff. Preserve them until the final supervised provider-validation
path no longer needs them.

There is no remaining local or tracked `pricing_dynamic_azure.json` at handoff
time. The reviewed Azure catalog baselines are versioned under
`2-twin2clouds/json/pricing_catalog_baselines/azure/westeurope/`. Do not recreate
an ad hoc dynamic-pricing file as a parallel source of truth.

## What Is Complete

### Cross-Project Refactoring Baseline

The following foundations are implemented or substantially hardened:

- Management API route, repository, service, client, lifecycle, and deployment
  orchestrator boundaries.
- Typed Optimizer and Deployer client contracts.
- CloudConnection credential SSOT with purpose-aware pricing/deployment use.
- Removal of legacy runtime credential fallback.
- Secret-free bootstrap planning/import and provider permission preflight.
- Deployment context, ProjectStorage abstraction, and ephemeral deployment
  workspaces.
- Typed deployment manifests and explicit operation state.
- Deployer logging, correlation, redaction, error taxonomy, and operation-scoped
  evidence.
- Optimizer calculation/profile/provider patterns and explicit unsupported
  capability handling.
- Pricing intent, evidence, reviewed-decision, catalog, run-history, and
  traceability models.
- Route-aware transfer pricing and durable calculation runs.
- Flutter typed API boundaries, feature decomposition, compact configuration
  workspace, provider pricing review, offline demo mode, and all-desktop gates.
- Canonical MkDocs user, operator, developer, architecture, security, cloud
  setup, contract, and troubleshooting documentation.

This does not mean every open umbrella issue is complete. The current code and
roadmap must be checked against the narrower remaining scopes below.

### Resolved Deployment Specification

The mini-roadmap under `docs/plans/resolved_deployment_specification/` is
implemented through its safe cross-stack gate.

The canonical data flow is:

```text
pricing evidence + workload intent
    |
    v
Optimizer formula and strategy contracts
    |
    v
ResolvedDeploymentSpecification
    |  schema version
    |  stable component IDs
    |  provider/service model
    |  deployable SKU/capacity/runtime/storage selections
    |  formula and evidence references
    |  deterministic digest
    v
Management API validation, immutable persistence, and run selection
    |
    v
DeploymentManifest v2
    |
    v
Deployer preflight and allowlisted typed tfvars
    |
    v
Terraform validate and offline plan drift gate
```

The gate covers 50 target bindings, 27 storage paths, provider lock files,
native mock plans, and secrets-free contract comparison. Issue
[#118](https://github.com/TVJunkie724/master-thesis/issues/118) remains open only
because real-provider deployment and final application E2E are deliberately
deferred.

### Architecture Research Direction

The following decisions are recorded and should not be reopened without new
evidence:

1. The five functional/cost layers remain necessary as the paper-compatible
   baseline.
2. Cost ranking is valid only after a functional-completeness gate. A cheaper
   candidate that provides less required functionality must not win.
3. Provider services are not assumed to be one-to-one equivalents.
4. Provider-specific service bundles may implement the same logical layer when
   the required capabilities are complete and all costs are owned.
5. The inherited direct function-call topology is architecture debt, not a
   scientific requirement of the five-layer model.
6. The five-layer baseline must remain executable and be hardened before it is
   used as an evaluation baseline.
7. Eventing and Messaging is a valid nonlinear logical layer candidate. A layer
   is a responsibility and cost boundary; it does not need to be one step in a
   linear pipeline.
8. The thesis should expose two reviewed, versioned architecture profiles:
   `five-layer-baseline@1` and, after its contract is proven,
   `six-layer-eventing@1`.
9. Runtime users select a reviewed profile. They do not create layers, edit a
   graph, or freely compose provider services.
10. Developers extend the closed-world profile catalog through versioned code
    and data contracts.
11. Architecture profiles, provider implementations, deployment components,
    and resolved Twin instances are distinct models.
12. Terraform modules are deployment implementation units, not logical layers.
13. Function templates remain explicit implementation artifacts behind
    registered deployment components.
14. The Deployer must resolve physical names, references, provider outputs, and
    bindings from a validated graph. User code and Flutter must not construct
    cloud resource identifiers.
15. Eventing must not be inserted between every helper function. Component
    boundaries follow responsibility, trust, failure isolation, fan-out,
    delivery, and lifecycle requirements.
16. The Eventing evaluation requires both a functional/pricing-model matrix and
    a fixed-scenario cost matrix.
17. Only one curated, functionally admissible Eventing implementation profile
    per provider is required for the thesis.
18. The multi-cloud Eventing bridge is not yet decided. Authentication,
    delivery, retries, dead-letter behavior, idempotency, ordering,
    observability, data transfer, and cost ownership must be designed
    explicitly.
19. A general topology optimizer or arbitrary architecture generator is out of
    scope.

### Working Research Questions

The current working questions are:

- **RQ1:** How can a configuration-driven platform operationalize a layered,
  cost-aware Digital Twin model into reproducible deployments across AWS,
  Azure, and Google Cloud?
- **RQ2:** How can provider-specific cloud services be mapped to functionally
  complete and cost-comparable Digital Twin architecture profiles without
  assuming one-to-one service equivalence?
- **RQ3:** To what extent can layer-wise multi-cloud service selection reduce
  estimated operational cost compared with functionally equivalent
  single-cloud baselines?
- **RQ3.1:** How do single-cloud and multi-cloud configurations compare under
  identical workload and functional requirements?
- **RQ3.2:** How does introducing an explicit Eventing and Messaging Layer
  affect functional coverage, architecture topology, and total estimated cost?

The four evaluation instruments are:

1. a functional total matrix;
2. single-provider total-cost baselines;
3. the bounded Eventing deep dive with two matrices;
4. a separate best admissible multi-cloud result per architecture profile.

Do not rank five-layer and Eventing candidates in one undifferentiated pool.
Report functional, topology, and estimated-cost deltas between the separately
validated profiles.

## Required Reading Order

Read these files before Phase 8 planning or implementation:

1. `.agent/workflows/onboarding.md`
2. `integration_vision.md`
3. `ASSESSMENT.md`
4. `docs-site/docs/architecture/refactoring-roadmap.md`
5. `docs-site/docs/contracts-and-data-flow/index.md`
6. `docs-site/docs/contracts-and-data-flow/system-boundaries.md`
7. `docs-site/docs/contracts-and-data-flow/contract-map.md`
8. `docs-site/docs/contracts-and-data-flow/state-ownership.md`
9. `docs-site/docs/contracts-and-data-flow/pricing-optimization.md`
10. `docs-site/docs/contracts-and-data-flow/deployment-lifecycle.md`
11. `docs-site/docs/contracts-and-data-flow/credentials-and-trust.md`
12. `docs/plans/resolved_deployment_specification/README.md`
13. `docs/research/digital_twin_architecture_and_eventing_layer.md`
14. `docs/research/research_questions_and_evaluation_design.md`
15. `docs/research/related_work_multicloud_cost_comparability_eventing.md`
16. GitHub issue #112 including comments and native blockers
17. GitHub issue #113 including its relationship to #36

Then inspect the actual Optimizer, Management API, Deployer, Terraform, template,
and Flutter code. Documentation is a guide, not a substitute for code-level
verification.

## Current Open Work Before Phase 8 Implementation

The architecture audit may begin as analysis, but implementation of architecture
profiles should not leapfrog current-system hardening.

### Pricing Umbrellas

- [#31 Implement tiered pricing for additional optimizer services](https://github.com/TVJunkie724/master-thesis/issues/31)
  remains open for the exact residual provider billing-model scope. Major child
  slices are complete, but the parent must be reconciled against its remaining
  acceptance criteria.
- [#32 Refresh optimizer pricing schema and provider fetchers for expanded services](https://github.com/TVJunkie724/master-thesis/issues/32)
  remains open for provider-specific mapping/fetcher finalization and later live
  validation. Do not claim all live provider strings or credentials are final.
- [#33 Show pricing and region data freshness with refresh controls](https://github.com/TVJunkie724/master-thesis/issues/33)
  and [#34 Allow manual provider override after optimization with cost warnings](https://github.com/TVJunkie724/master-thesis/issues/34)
  are still open product capabilities.

### Current UI And Operations

- [#40 Build Twin operations dashboard](https://github.com/TVJunkie724/master-thesis/issues/40)
  and [#41 Implement centralized error notification and UI alerts](https://github.com/TVJunkie724/master-thesis/issues/41)
  remain open even though substantial Twin Overview and lifecycle hardening is
  complete. Reconcile the issue bodies with current code before implementing
  additional UI.
- [#111 Run final manual visual audit of the Flutter application](https://github.com/TVJunkie724/master-thesis/issues/111)
  is intentionally user-led and occurs after functional issue work, before
  final E2E.

### Credentials And Permissions

- [#79 Finalize versioned least-privilege permission sets](https://github.com/TVJunkie724/master-thesis/issues/79)
  has a hardened pre-E2E baseline. Final provider-specific least-privilege
  validation remains supervised work.
- Cloud admin credentials are transient bootstrap inputs. They are not the
  runtime credential SSOT.
- Deployment and pricing credentials are purpose-specific CloudConnections.
- OpenAI API configuration, if later enabled for diagnostic pricing review, is
  process-level configuration and not a per-Twin CloudConnection.

### User Functions

[#113](https://github.com/TVJunkie724/master-thesis/issues/113) is the active
current-thesis hardening issue, not post-thesis future work.

The target boundary is:

- the platform owns names, handlers, provider adapters, topology bindings,
  identities, permissions, lifecycle, observability, retries, limits, and
  infrastructure references;
- the user supplies only approved domain logic, dependencies, typed non-secret
  configuration, and declared secret references through versioned extension
  slots;
- packaging is deterministic and does not rewrite user source;
- invalid dependencies, handlers, schemas, runtimes, secrets, artifacts, or
  bindings fail before Terraform;
- Flutter exposes only the allowed user-editable surface.

The narrower
[#36 Validate user function requirements.txt before deployment](https://github.com/TVJunkie724/master-thesis/issues/36)
must be completed or explicitly superseded by #113.

## GitHub Dependency Correction Required

At handoff time, issue #112 has two native blockers:

- #118, open;
- #117, closed.

This graph no longer represents the agreed sequence:

- #117 is complete and should not remain a blocker.
- #118 has completed all safe implementation phases and remains open only for
  final live E2E. Waiting for that E2E before Phase 8 would contradict the
  deliberate decision to defer E2E until after architecture-profile work.
- #113 is the true prerequisite for safely binding user logic into resolved
  architecture profiles, but the architecture inventory and Function-and-Edge
  audit can start before #113 is fully implemented.

Recommended correction:

1. remove #117 as a blocker of #112;
2. remove #118 as a blocker of #112 and record it as related baseline/final-E2E
   work instead;
3. update #112 to the final closed-world scope recorded in the research notes;
4. create bounded Phase 8 child issues;
5. make the first implementation child that binds extension slots depend on
   #113, rather than blocking the entire architecture audit;
6. preserve final E2E as a separate finalization dependency after the manual UI
   audit and architecture-profile implementation.

Use native GitHub blocker relationships, not only body text or comments.

## Phase 8 Planning Gap

Phase 8 is not yet implementation-ready.

The research direction is detailed, but the following implementation artifacts
do not yet exist:

- a Phase 8 mini-roadmap with bounded child phases;
- a verified current Function-and-Edge Matrix;
- the approved hardened five-layer baseline graph;
- field-level schemas for all four architecture models;
- model ownership, persistence, migration, and compatibility rules;
- generic assignment-row migration from fixed `cheapest_l1` through
  `cheapest_l5` fields;
- a deterministic Deployer graph resolver contract;
- staged provider-output and binding rules;
- provider-profile/component-catalog registration contracts;
- exact Flutter profile selection and read-only graph contracts;
- selected Eventing service bundles and formulas;
- the multi-cloud Eventing bridge design;
- per-phase tests, verification gates, rollback/compatibility rules, and
  documentation deltas.

Do not treat the long research note as an executable implementation plan.

## Recommended Phase 8 Mini-Roadmap

Create a mini-roadmap under:

```text
docs/plans/phase_08_architecture_profiles_eventing/
```

Keep this `HANDOFF.md` as the transition snapshot. Add a `README.md` and one
reviewed plan per bounded phase.

### Phase 8.0: Current Graph Reconstruction

Goal:

- reconstruct every current deployable component, function/template, Terraform
  resource, provider mapping, synchronous call, asynchronous event, storage
  transition, trust boundary, and cross-cloud edge.

Required artifact:

- a Function-and-Edge Matrix with stable IDs.

Each edge must record:

- source and destination component;
- owning logical layer/responsibility;
- current provider-specific implementation;
- protocol and payload/envelope;
- sync/async semantics;
- delivery/retry/dead-letter/idempotency/ordering behavior;
- identity and trust boundary;
- data transfer and cost owner;
- current hardcoded resource-name/reference mechanism;
- observability and correlation;
- whether it is baseline-required, implementation-internal, unsafe debt, or
  candidate Eventing responsibility.

Gate:

- the matrix matches actual AWS, Azure, GCP, Terraform, package, Optimizer,
  Management API, and Flutter code;
- no topology decision is made from layer labels alone.

### Phase 8.1: Harden And Freeze `five-layer-baseline@1`

Goal:

- preserve the five scientific functional/cost contracts while deciding every
  current edge deliberately.

Decisions:

- which helper functions belong in one deployable component;
- which direct calls remain typed synchronous ports;
- which transitions use provider-native lifecycle/workflow features;
- which cross-responsibility or cross-cloud edges need explicit adapters;
- how all observable behavior and costs remain represented.

Gate:

- the baseline remains paper-comparable and executable;
- no inherited direct call remains merely because it existed in the bachelor
  implementation;
- no Eventing profile behavior is silently folded into the baseline experiment.

### Phase 8.2: Architecture Profile Contracts

Define field-level, versioned contracts for:

```text
ArchitectureProfile
ProviderImplementationProfile
DeploymentComponentCatalog
ResolvedTwinArchitecture
```

At minimum define:

- stable profile/component/edge/slot identifiers;
- schema and profile versions;
- logical responsibilities and required capabilities;
- provider implementation bundles;
- workload, pricing, formula, deployment, and extension-slot references;
- compatibility and lifecycle rules;
- immutable resolution identity and digest;
- validation errors and unsupported states.

Gate:

- contracts are provider-neutral at the architecture level;
- provider details remain behind implementation profiles and component
  adapters;
- runtime users cannot submit arbitrary nodes, edges, provider services, or
  Terraform values.

### Phase 8.3: Provider Profiles And Component Catalog

Goal:

- register the existing AWS, Azure, and GCP baseline components explicitly.

The catalog owns:

- provider adapter identity;
- package/template identity and hash;
- Terraform module/resource mapping;
- supported runtime/configuration schema;
- required capabilities and permission-set version;
- emitted outputs and accepted bindings;
- pricing/formula/deployment-spec references;
- tests and compatibility metadata.

Gate:

- templates and Terraform references are explicit catalog data or typed adapter
  code;
- there is no source rewriting or hidden cross-resource naming convention;
- adding a component is a modular cross-project extension, not edits scattered
  through fixed layer slots.

### Phase 8.4: Management Persistence And API Migration

Goal:

- persist profile identity, profile version, resolved assignments, components,
  edges, bindings, and digest as server-owned data.

Replace fixed architecture assumptions such as:

```text
cheapest_l1
cheapest_l2
cheapest_l3
cheapest_l4
cheapest_l5
```

with generic assignment rows or an equally explicit normalized model:

```text
calculation_run
  -> resolved_architecture
       -> responsibility/component assignments
       -> resolved edges and bindings
       -> immutable profile and evidence references
```

Define:

- database migration and backfill;
- old-run compatibility and read-only legacy projection;
- API schema versioning;
- selection/invalidation rules;
- ownership and authorization;
- redaction and audit behavior.

Gate:

- clients cannot author or alter resolved architecture evidence;
- old runs fail or project explicitly, never silently;
- migration is repeatable and tested.

### Phase 8.5: Optimizer Profile Resolution

Goal:

- optimize within one selected, validated architecture profile.

The Optimizer must:

- load the reviewed profile and provider implementations;
- apply the functional-completeness gate before cost ranking;
- resolve provider/service bundles, workload/formula/pricing references, and
  transfer edges;
- emit a complete `ResolvedTwinArchitecture` plus the existing
  `ResolvedDeploymentSpecification`;
- keep optimization strategy and calculation strategy compatible through a
  versioned profile bundle;
- fail closed on missing capabilities, formulas, evidence, provider
  implementations, or deployment contracts.

Gate:

- incomplete candidates cannot win;
- five-layer and Eventing profiles are calculated and evaluated separately;
- results remain reproducible from frozen inputs and evidence.

### Phase 8.6: Deployer Graph Resolver And Preflight

Goal:

- convert the resolved architecture into an ordered, validated deployment graph
  before Terraform.

The Deployer must:

- resolve components, outputs, inputs, edges, provider boundaries, and
  extension slots;
- reject missing, duplicate, cyclic where forbidden, incompatible, or
  unauthorized bindings;
- stage provider outputs explicitly;
- build deterministic package and Terraform inputs;
- keep ephemeral workspaces and secret handling intact;
- preserve operation correlation and typed errors.

Gate:

- no function constructs another resource's name, ARN, URL, topic, or handler
  from duplicated strings;
- unresolved references fail before `terraform plan`;
- graph and generated-input golden tests cover all curated baseline provider
  profiles without live credentials.

### Phase 8.7: Flutter Profile Workflow

Goal:

- provide a compact profile-oriented configuration experience.

Target flow:

```text
Architecture
  -> choose one reviewed profile
  -> inspect a read-only flowchart and functional summary

Workload
  -> enter profile-supported scenario inputs

User Logic
  -> bind approved code/configuration to declared extension slots

Optimize And Review
  -> compare valid provider assignments, cost, evidence, and warnings

Deployment Review
  -> inspect resolved components, regions, tiers, bindings, and provenance
```

Rules:

- no arbitrary graph editor;
- no per-layer enable/disable controls unless a later profile explicitly
  defines a bounded optional feature;
- no provider infrastructure names or free-form SKU editing;
- detailed graph/evidence diagnostics are collapsed or on dedicated review
  screens;
- demo repositories expose both profiles only when their contracts are
  implemented honestly;
- widget/model/repository tests cover Web and all desktop targets.

### Phase 8.8: Eventing Research Decision Gate

Do not implement Eventing resources before this gate.

Produce:

1. a functional and pricing-model matrix;
2. a fixed-scenario cost matrix;
3. one curated functionally admissible service bundle per provider;
4. an explicit Eventing workload schema;
5. explicit ownership of broker, queue, workflow, glue function, transfer, and
   cross-cloud costs;
6. the multi-cloud bridge architecture and security/delivery contract.

Required bridge decisions:

- bridge placement and provider ownership;
- producer/consumer trust and credential exchange;
- event envelope and schema versioning;
- at-least-once/exactly-once claims and realistic limitations;
- retries, dead-letter queues, replay, retention, and poison-message handling;
- idempotency and ordering scope;
- observability and correlation;
- transfer paths, units, regions, and costs;
- failure domains and recovery;
- which edges connect L1, L2, L3, L4, and L5.

Gate:

- service bundles satisfy the same mandatory scenario capabilities;
- non-equivalent functionality remains visible;
- global/static/non-fetchable price inputs are reviewed, versioned evidence,
  never silent fallbacks;
- formulas normalize provider-specific billing units without erasing their
  semantics.

### Phase 8.9: `six-layer-eventing@1` Implementation

Goal:

- add Eventing through the same profile, capability, pricing, formula,
  persistence, graph, deployment, security, evidence, and UI extension points.

Gate:

- upstream domain functions do not reference downstream function identities;
- adding an independent consumer does not require editing the producer;
- every Eventing edge has explicit delivery, security, observability, transfer,
  and cost ownership;
- provider adapters implement the same canonical event envelope and error
  behavior;
- no general topology generator is introduced.

### Phase 8.10: Evaluation Evidence And Documentation

Goal:

- produce reproducible evidence for RQ1, RQ2, RQ3, RQ3.1, and RQ3.2.

Required outputs:

- baseline/current/target architecture diagrams;
- functional total matrix;
- single-provider and multi-cloud baseline cost tables;
- Eventing functional/pricing and scenario matrices;
- resolved architecture and deployment evidence;
- limitations and threats to validity;
- product/developer docs for implemented profile extension and operation;
- research notes for thesis interpretation.

Do not copy research conclusions into user documentation. Do not modify LaTeX
without explicit approval.

## Decisions Still Open

The next agent must not guess these:

1. The exact current Function-and-Edge Matrix.
2. Which direct baseline calls remain synchronous, become internal in-process
   calls, use provider workflows/lifecycle policies, or require explicit
   adapters.
3. Whether user L2 logic runs in-process with a platform wrapper or in an
   isolated worker. This depends on trust and failure-isolation requirements.
4. The exact field-level architecture-profile schemas and versioning policy.
5. The exact database migration from fixed layer fields to generic assignments.
6. The exact Deployer graph ordering, cycle, output, and staged-binding rules.
7. The curated Eventing service bundle for AWS.
8. The curated Eventing service bundle for Azure.
9. The curated Eventing service bundle for GCP.
10. The multi-cloud bridge topology and security/delivery contract.
11. Eventing pricing intents, normalized units, formulas, and ownership of glue
    and transfer costs.
12. The fixed workload scenarios and thresholds used in the thesis evaluation.

Resolve these through evidence, code inspection, provider documentation, and
reviewed plans. For current provider services, pricing, permissions, and APIs,
verify primary sources because they are time-sensitive.

## Forbidden Shortcuts

Do not:

- replace the closed-world profile catalog with a free-form graph editor;
- let Flutter or the Management API client author resolved architecture data;
- encode architecture in `cheapest_l1` through `cheapest_l5` forever;
- treat every Function as a layer or every Function call as an Eventing edge;
- add a broker between every helper function;
- compare Event Grid, Event Hubs, Service Bus, EventBridge, SQS, SNS, Pub/Sub,
  Cloud Tasks, or similar services as if they were interchangeable;
- allow a function to construct another function's identifier;
- depend on duplicated Terraform string conventions for cross-resource
  references;
- silently use stale/static/fallback prices as live provider evidence;
- use AI confidence as an automatic publish or deployment decision;
- store cloud admin credentials as runtime CloudConnections;
- expose secrets in logs, API errors, evidence, manifests, tfvars, fixtures, or
  documentation;
- hide unsupported provider/profile combinations behind default values;
- delete predecessor material or credentials during cleanup;
- claim production readiness from unit tests alone;
- run paid/live E2E without explicit approval.

## Review And Commit Discipline

For every phase:

1. write the plan with exact scope, non-goals, ownership, contracts, files,
   migrations, failure behavior, security, observability, tests, documentation,
   compatibility, and acceptance criteria;
2. review the plan for completeness, enterprise quality, thesis scope, and
   interpretive ambiguity;
3. fix all plan findings before implementation;
4. create or update the corresponding GitHub issue and native blockers;
5. implement only that phase;
6. run focused tests first, then the relevant safe project suites;
7. review the implementation against the plan;
8. perform a second code-quality, security, error-handling, migration, and
   regression review;
9. fix every finding;
10. update product docs, research evidence, roadmap, and issue status;
11. create a structured conventional commit with `Refs #<issue>` or
    `Closes #<issue>` only when accurate;
12. start the next phase only after the current phase is clean.

Avoid giant cross-project commits. Contract fixtures may need coordinated
changes, but commit boundaries should remain understandable and reversible.

## Safe Verification

Never run `tests/e2e/` by default.

Useful safe commands:

```bash
# Canonical resolved deployment contract gate
./thesis.sh test deployment-contract

# Management API
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest tests/ -v

# Optimizer
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest tests/ -v

# Deployer without live E2E
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/ --ignore=tests/e2e -v

# Flutter
cd twin2multicloud_flutter
flutter analyze
flutter test

# Strict documentation build
docker compose --profile docs run --rm docs mkdocs build --strict
```

Before using a command, verify service names with the current Compose
configuration. The user has OrbStack available. Run required commands yourself;
do not ask the user to execute Docker commands.

Use provider documentation and safe API reads for time-sensitive architecture,
pricing, and permission research. Never create billable resources as part of
ordinary verification.

## Documentation Rule

Every phase must update the correct documentation boundary:

| Change | Destination |
|---|---|
| Current setup, runtime, configuration, operation, troubleshooting | `docs-site/docs/` |
| Current contracts, ownership, data flows, extension process | `docs-site/docs/contracts-and-data-flow/` or `docs-site/docs/developer-guide/` |
| Architecture reasoning, alternatives, research questions, evaluation, limitations | `docs/research/` |
| Approved implementation contract and phase gates | `docs/plans/` or project `implementation_plans/` |
| Operational status and dependencies | GitHub Issues and Milestones |
| Thesis prose | `twin2multicloud-latex`, only with explicit user approval |

The documentation must let a future human developer understand setup,
architecture, contracts, configuration, credentials, data flow, extension
points, failure handling, testing, and known gaps without reading the chat.

## Definition Of Ready For Phase 8 Implementation

Phase 8 implementation may start only when:

- the current branch history is integrated intentionally;
- #112 scope and blocker relationships reflect the final decisions;
- the remaining pre-Phase-8 issue scope is reconciled;
- the Function-and-Edge Matrix is code-verified;
- `five-layer-baseline@1` has an approved edge/component contract;
- architecture models have field-level schemas and owners;
- migration and backward-compatibility behavior is explicit;
- the user-function extension boundary is complete before extension-slot
  binding;
- the first bounded implementation plan has passed review;
- all verification can run without live cloud resources.

## Definition Of Done For Phase 8

Phase 8 is not complete merely because profile classes exist.

Completion requires:

- an executable hardened `five-layer-baseline@1`;
- versioned profile, provider implementation, component catalog, and resolved
  architecture contracts;
- normalized persistence and API projections;
- an Optimizer that ranks only functionally complete candidates within a
  selected profile;
- a Deployer that resolves and validates the graph before Terraform;
- a compact Flutter profile and review workflow;
- a reviewed user-function extension-slot contract;
- two completed Eventing matrices;
- one curated Eventing implementation profile per provider;
- an explicit multi-cloud bridge contract;
- executable `six-layer-eventing@1`;
- broad offline contract, unit, integration, migration, security, package,
  Terraform validation/plan, Flutter, and documentation gates;
- complete current product/developer docs and separate research evidence;
- no unresolved review findings;
- final live E2E still run only when explicitly approved.

## Suggested First Message To The User

After verifying the repository, the next agent can report:

> Ich habe den Handoff, den aktuellen Branch, die Phase-8-Research-Dokumente
> und die GitHub-Issues geprueft. Die Architekturentscheidung ist als
> Closed-World-Modell mit `five-layer-baseline@1` und dem spaeteren
> `six-layer-eventing@1` festgehalten. Noch nicht implementation-ready sind die
> Function-and-Edge-Matrix, die feldgenauen Profilvertraege, Migration und der
> Deployer-Graph-Resolver. Ich beginne deshalb mit der Branch-/Issue-
> Bereinigung und plane danach Phase 8.0 als code-verifizierte Rekonstruktion
> der aktuellen Topologie. Live-E2E bleibt unangetastet.

Then proceed autonomously unless the repository state contradicts this
handoff.
