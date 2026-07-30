---
title: "Phase 8 Architecture Profiles And Eventing Mini-Roadmap"
description: "Ordered implementation roadmap for closed-world Twin architecture profiles, the hardened five-layer baseline, and the bounded Eventing extension."
tags: [architecture, eventing, roadmap, optimizer, deployer, management-api, flutter, thesis]
lastUpdated: "2026-07-30"
version: "2.5"
---

<!-- SOURCES:
- docs/plans/phase_08_architecture_profiles_eventing/HANDOFF.md
- docs/research/digital_twin_architecture_and_eventing_layer.md
- docs/research/research_questions_and_evaluation_design.md
- docs/research/related_work_multicloud_cost_comparability_eventing.md
- docs/plans/resolved_deployment_specification/README.md
- GitHub issues #112, #113, #138, #139, #140, #142, #144, #146, #148, #149, #150, #151, #152, and #153
- User-approved closed-world profile, baseline-first, Eventing-gate, documentation, and E2E boundaries
EXTRACTED: 2026-07-30 | VERSION: 2.5
-->

# Phase 8 Architecture Profiles And Eventing Mini-Roadmap

| Field | Value |
|---|---|
| Parent issue | [#112](https://github.com/TVJunkie724/master-thesis/issues/112) |
| Base branch | `master` |
| Planning branch | `codex/phase-8-service-bundle-closure` |
| Status | Phases 8.0 through 8.5 and prerequisite #113 implemented and locally reviewed; Phase 8.8 Eventing evidence approved; Five-layer v2 service closure has two fresh zero-finding reviews and awaits user approval; Phase 8.6 compiler work remains dark; Six-layer planning is deferred |
| Final live E2E | Deliberately deferred and not part of the default gates |

## Purpose

Phase 8 replaces architecture knowledge scattered across fixed layer slots,
templates, Terraform names, database columns, and Flutter models with a bounded
closed-world profile model. It does not create a general topology engine.

The phase preserves the paper-compatible `five-layer-baseline@1` as immutable
historical read/verify/destroy evidence; it is not selectable for a new
calculation or deployment. The Eventing decision
gate then freezes one shared domain-event contract and evaluates two new,
functionally aligned profiles:

- `five-layer-baseline@2`, with rule evaluation, event actions, notification
  workflows, and device feedback embedded in the existing L1/L2
  responsibilities, including local direct-edge transport and
  topology-conditional source-owned bridges for remote responsibility edges;
- `six-layer-eventing@1`, with the same domain behavior plus an independent
  Eventing and Messaging responsibility for routing, buffering, fan-out,
  retry/DLQ, replay, and cross-cloud transport.

The legacy Eventing feature booleans remain readable only for historical
`five-layer-baseline@1` inputs. They are not part of either new profile.

```text
current deployed graph
        |
        v
Function-and-Edge Matrix
        |
        v
five-layer-baseline@1 decision contract
        |
        v
versioned profile + component + resolution contracts
        |
        +--> Management API persistence and APIs
        +--> Optimizer functional-completeness resolution
        +--> Deployer graph resolution and binding preflight
        +--> compact Flutter profile workflow
        |
        v
Eventing decision gate
        |
        +--> shared domain-event contract
        +--> five-layer-baseline@2 decision
        +--> Event-domain provider/service/capacity evaluation
        |
        v
complete-service closure
        |
        +--> complete AWS/Azure/provider-hosted-GCP bundles
        +--> finite scheduled storage transition jobs
        +--> provider-local L3-hot/L5 raw-visualization bundles
        +--> independently placed L4
        +--> typed L3-hot-to-L5 read and L3-hot-to-L4 projection
        +--> corrected workload and capacity semantics
        |
        v
five-layer-baseline@2
        |
        v
frozen Five-layer evidence
        |
        v
later separately planned six-layer-eventing@1
```

## Fixed Scope Boundary

Phase 8 must:

- model logical responsibilities independently from provider resources;
- keep provider implementations explicit and registered;
- resolve one immutable architecture per selected calculation run;
- prove functional completeness before cost ranking;
- resolve every deployment binding before Terraform;
- expose only reviewed profiles and extension slots to runtime users;
- retain `five-layer-baseline@1` as historical evidence and separate the
  functionally aligned `five-layer-baseline@2` and
  `six-layer-eventing@1` experiments;
- keep product documentation and thesis reasoning separate.

Phase 8 must not:

- expose a graph editor or arbitrary user-defined layers;
- generate Terraform dynamically;
- let Flutter or clients author resolved architecture evidence;
- insert an event broker between every helper function;
- claim unlike provider services are equivalent;
- use static or stale prices as silent live fallbacks;
- run paid/live cloud deployments without explicit approval;
- modify `twin2multicloud-latex` without explicit approval.

## Prerequisite

| Issue | Plan | Required Before |
|---|---|---|
| [#113 Define and harden the user-function extension and packaging contract](https://github.com/TVJunkie724/master-thesis/issues/113) | [`prerequisite_user_function_extension_contract.md`](prerequisite_user_function_extension_contract.md) | Phase 8.3 extension-slot catalog binding |

The graph inventory and baseline decision proceeded before #113. The
prerequisite now passes its complete local offline gate and provides the
versioned non-secret execution boundary consumed by Phase 8.3. Provider
component catalog entries still own the exact executable resource mapping.

## Phase Order

| Phase | Issue | Plan | Outcome | Native Blocker |
|---|---|---|---|---|
| 8.0 | [#144 Inventory the current Twin deployment graph and Function-and-Edge Matrix](https://github.com/TVJunkie724/master-thesis/issues/144) | [`phase_08_0_current_graph_reconstruction.md`](phase_08_0_current_graph_reconstruction.md) | Implemented code-verified [Function-and-Edge Matrix](../../research/phase_08_current_function_edge_matrix.md) | None |
| 8.1 | [#139 Harden and freeze the five-layer-baseline@1 architecture profile](https://github.com/TVJunkie724/master-thesis/issues/139) | [`phase_08_1_five_layer_baseline.md`](phase_08_1_five_layer_baseline.md) | Implemented [five-layer target decision](../../research/five_layer_baseline_target_decision.md) with 114 component and 90 edge decisions | #144 |
| 8.2 | [#149 Define versioned architecture profile contracts](https://github.com/TVJunkie724/master-thesis/issues/149) | [`phase_08_2_profile_contracts.md`](phase_08_2_profile_contracts.md) | Implemented four versioned contracts, semantic registry, fixtures, dark readers, and drift gates | #139 |
| 8.3 | [#150 Register provider implementation profiles and deployment component catalog](https://github.com/TVJunkie724/master-thesis/issues/150) | [`phase_08_3_provider_profiles_component_catalog.md`](phase_08_3_provider_profiles_component_catalog.md) | Implemented dark/read-only provider profiles, exact component/edge/package/Terraform registries, unsupported fixtures, and #113 slot mapping | #149, #113 |
| 8.4 | [#142 Persist resolved Twin architectures and migrate fixed layer assignments](https://github.com/TVJunkie724/master-thesis/issues/142) | [`phase_08_4_management_persistence_migration.md`](phase_08_4_management_persistence_migration.md) | Implemented migration 022, revisioned profile selection, immutable resolution persistence/API, and tracked compatibility projections | #150 |
| 8.5 | [#151 Resolve architecture profiles in the Optimizer with functional completeness](https://github.com/TVJunkie724/master-thesis/issues/151) | [`phase_08_5_optimizer_profile_resolution.md`](phase_08_5_optimizer_profile_resolution.md) | Implemented default-off profile-bounded complete-path optimization and immutable architecture output | #142 |
| 8.6 | [#152 Build the Deployer graph resolver and staged binding preflight](https://github.com/TVJunkie724/master-thesis/issues/152) | [`phase_08_6_deployer_graph_resolver.md`](phase_08_6_deployer_graph_resolver.md) | Deterministic deployment graph and preflight | #151 |
| 8.7 | [#138 Implement the Flutter architecture profile workflow](https://github.com/TVJunkie724/master-thesis/issues/138) | [`phase_08_7_flutter_profile_workflow.md`](phase_08_7_flutter_profile_workflow.md) | Compact profile selection and read-only review | #152 |
| 8.8 | [#146 Complete the Eventing functional and cost decision gate](https://github.com/TVJunkie724/master-thesis/issues/146) | [`phase_08_8_eventing_decision_gate.md`](phase_08_8_eventing_decision_gate.md) | Approved offline package: shared domain flow, six provider bundles, exact bridge, S/M/L costs, implementation manifest, and two zero-finding reviews | None for offline evidence; #152/#138 still gate 8.9A |
| Service closure / 8.9A plan | New issue required before implementation | [`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md) | Cosmos-/Firestore-L3-preserving Five-layer v2, provider-local L3-hot/L5, independent L4, nine online placements, one bounded raw/rollup visualization read, Twin projection, finite storage jobs, workload v2, and immutable decision package | User approval; two fresh zero-finding reviews and #146 evidence complete |
| 8.9A | New implementation issue required before execution | [`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md) | Executable `five-layer-baseline@2` with mandatory embedded domain-event behavior and complete service bundles | #138, #146, complete-service decision |
| 8.9B | [#140 Implement six-layer-eventing@1 across the platform](https://github.com/TVJunkie724/master-thesis/issues/140) | [`phase_08_9_six_layer_eventing_implementation.md`](phase_08_9_six_layer_eventing_implementation.md) | Deferred and requires a fresh plan after reviewed 8.9A; the current document is not executable authority | Reviewed 8.9A plus new user-approved Six-layer plan |
| 8.10 | [#148 Produce Phase 8 evaluation evidence and final documentation](https://github.com/TVJunkie724/master-thesis/issues/148) | [`phase_08_10_evaluation_and_documentation.md`](phase_08_10_evaluation_and_documentation.md) | Deferred comparative evaluation; Five-layer v2 first produces frozen standalone evidence | Reviewed Six-layer implementation |

Provider implementation work inside one phase may be parallelized only after
the phase's shared contract is committed. AWS, Azure, and GCP must pass the same
completion gate before the phase is closed.

Phase 8.9A is the only currently planned implementation branch. Its shared
contract and `five-layer-baseline@2` gates must be committed and reviewed
before Six-layer is replanned. No 8.9B branch starts from this planning
package.

Phase 8.8 was completed as an offline evidence activity before Phase 8.6
runtime activation. This does not reorder implementation dependencies:
Phase 8.6 and Phase 8.7 remain mandatory predecessors of Phase 8.9A.
Accordingly, #146 is no longer natively blocked by #152; it still blocks the
Eventing implementation path until its reviewed evidence is published.

## Native Dependency Graph

```text
#144 -> #139 -> #149 -> #150 -> #142 -> #151 -> #152
                     ^                                  |
                     |                                  +-> #138 --------+
                    #113                                                 |
            #146 -> Five-layer service decision -------------------------+-> 8.9A
                                                                          |
                                                                          +-> later Six-layer replan -> #140 -> #148 -> #112
```

The relationship direction is left-to-right: the issue on the right is blocked
by the issue on the left. GitHub native blocker relationships are the
operational SSOT.

## Cross-Project Ownership

| Boundary | Owner |
|---|---|
| Architecture and provider profile schemas | Repository-level `contracts/` |
| Functional completeness and cost resolution | `2-twin2clouds` |
| User/twin/run persistence and API projection | `twin2multicloud_backend` |
| Component binding, packaging, Terraform realization | `3-cloud-deployer` |
| Profile selection and read-only presentation | `twin2multicloud_flutter` |
| Current-system developer/user documentation | `docs-site/` |
| Research reasoning and evaluation interpretation | `docs/research/` |

The Management API remains the only backend boundary used by Flutter.
`ResolvedDeploymentSpecification` remains a referenced deployment-dimension
contract; architecture contracts must not duplicate its values.

## Per-Phase Execution Protocol

Every phase must follow this exact sequence:

1. Confirm the corresponding issue and native blockers.
2. Re-read the approved plan and all required predecessor artifacts.
3. Implement only the declared scope.
4. Run focused unit, schema, contract, migration, package, security, UI, or
   documentation tests named by the plan.
5. Run the relevant safe project suite without `tests/e2e`.
6. Review against the plan from architect and builder perspectives.
7. Perform a second code-quality, security, error, compatibility, and
   regression review.
8. Fix every finding and rerun affected gates.
9. Update docs, research evidence, this roadmap, and the GitHub issue.
10. Commit one understandable phase boundary with `Refs #<issue>` or
    `Closes #<issue>` only when complete.

No next phase may begin while the current phase has unresolved findings.

## Global Verification Gates

The following properties are mandatory throughout Phase 8:

- shared contracts use JSON Schema Draft 2020-12 and deterministic canonical
  JSON hashing;
- unknown schema/profile/component versions fail closed;
- no schema, fixture, manifest, log, tfvars, package metadata, or API error
  contains credential material;
- migrations are idempotent and tested from both a clean and a populated
  pre-migration database;
- provider/profile/component registries reject duplicate and unresolved IDs;
- all selected candidates are functionally complete and reproducible from
  frozen workload, formula, pricing, and catalog references;
- all deployment inputs resolve from declared outputs or platform-owned
  bindings before `terraform plan`;
- demo and live Flutter adapters implement the same typed repository contract;
- Web, macOS, Windows, and Linux remain supported;
- strict MkDocs and link checks pass;
- default verification creates no cloud resources and incurs no provider cost.

## Completion Gate

Phase 8 is complete only when this chain is reproducible for both new approved
profiles and all three complete single-cloud provider bundles, while
historical `five-layer-baseline@1` remains byte-stable and
read/verify/destroy compatible:

```text
reviewed ArchitectureProfile
  == resolved Optimizer architecture
  == immutable Management API architecture
  == DeploymentManifest architecture reference
  == Deployer resolved graph
  == deterministic packages and typed Terraform inputs
  == compact Flutter read model
  == evaluation evidence with identical digests
```

The final supervised live-provider E2E decision remains outside this roadmap's
default execution. It follows the user-led manual UI audit and explicit
approval.

## Supporting Context

- [`HANDOFF.md`](HANDOFF.md) is the implementation-ready operational handoff
  for the next agent.
- [`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md)
  is the corrective activation contract for complete services, identities,
  capacity, and scenario semantics.
- `docs/research/digital_twin_architecture_and_eventing_layer.md` records the
  scientific architecture reasoning.
- `docs/research/research_questions_and_evaluation_design.md` records research
  questions and evaluation design.
- `docs/research/related_work_multicloud_cost_comparability_eventing.md`
  records related-work differentiation.
- `docs/plans/resolved_deployment_specification/README.md` records the completed
  cost-to-Terraform baseline contract that Phase 8 extends.
