---
title: "Phase 8 Architecture Profiles And Eventing Mini-Roadmap"
description: "Ordered implementation roadmap for closed-world Twin architecture profiles, the hardened five-layer baseline, and the bounded Eventing extension."
tags: [architecture, eventing, roadmap, optimizer, deployer, management-api, flutter, thesis]
lastUpdated: "2026-07-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/phase_08_architecture_profiles_eventing/HANDOFF.md
- docs/research/digital_twin_architecture_and_eventing_layer.md
- docs/research/research_questions_and_evaluation_design.md
- docs/research/related_work_multicloud_cost_comparability_eventing.md
- docs/plans/resolved_deployment_specification/README.md
- GitHub issues #112, #113, #138, #139, #140, #142, #144, #146, #148, #149, #150, #151, #152, and #153
- User-approved closed-world profile, baseline-first, Eventing-gate, documentation, and E2E boundaries
EXTRACTED: 2026-07-19 | VERSION: 1.0
-->

# Phase 8 Architecture Profiles And Eventing Mini-Roadmap

| Field | Value |
|---|---|
| Parent issue | [#112](https://github.com/TVJunkie724/master-thesis/issues/112) |
| Base branch | `master` |
| Planning branch | `codex/phase-8-implementation-plans` |
| Status | Planning; implementation must proceed in the order below |
| Final live E2E | Deliberately deferred and not part of the default gates |

## Purpose

Phase 8 replaces architecture knowledge scattered across fixed layer slots,
templates, Terraform names, database columns, and Flutter models with a bounded
closed-world profile model. It does not create a general topology engine.

The phase preserves the executable, paper-compatible
`five-layer-baseline@1`. It then evaluates and, only after a separate decision
gate, implements one curated `six-layer-eventing@1` profile.

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
        v
six-layer-eventing@1
        |
        v
reproducible thesis evaluation evidence
```

## Fixed Scope Boundary

Phase 8 must:

- model logical responsibilities independently from provider resources;
- keep provider implementations explicit and registered;
- resolve one immutable architecture per selected calculation run;
- prove functional completeness before cost ranking;
- resolve every deployment binding before Terraform;
- expose only reviewed profiles and extension slots to runtime users;
- retain separate five-layer and Eventing experiments;
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

The graph inventory and baseline decision can proceed before #113 completes.
Provider component catalog entries that expose user logic must not be finalized
until #113 passes its complete offline gate.

## Phase Order

| Phase | Issue | Plan | Outcome | Native Blocker |
|---|---|---|---|---|
| 8.0 | [#144 Inventory the current Twin deployment graph and Function-and-Edge Matrix](https://github.com/TVJunkie724/master-thesis/issues/144) | [`phase_08_0_current_graph_reconstruction.md`](phase_08_0_current_graph_reconstruction.md) | Code-verified Function-and-Edge Matrix | None |
| 8.1 | [#139 Harden and freeze the five-layer-baseline@1 architecture profile](https://github.com/TVJunkie724/master-thesis/issues/139) | [`phase_08_1_five_layer_baseline.md`](phase_08_1_five_layer_baseline.md) | Approved `five-layer-baseline@1` decision contract | #144 |
| 8.2 | [#149 Define versioned architecture profile contracts](https://github.com/TVJunkie724/master-thesis/issues/149) | [`phase_08_2_profile_contracts.md`](phase_08_2_profile_contracts.md) | Shared versioned architecture contracts | #139 |
| 8.3 | [#150 Register provider implementation profiles and deployment component catalog](https://github.com/TVJunkie724/master-thesis/issues/150) | [`phase_08_3_provider_profiles_component_catalog.md`](phase_08_3_provider_profiles_component_catalog.md) | Explicit provider profiles and component catalog | #149, #113 |
| 8.4 | [#142 Persist resolved Twin architectures and migrate fixed layer assignments](https://github.com/TVJunkie724/master-thesis/issues/142) | [`phase_08_4_management_persistence_migration.md`](phase_08_4_management_persistence_migration.md) | Immutable normalized persistence and API projection | #150 |
| 8.5 | [#151 Resolve architecture profiles in the Optimizer with functional completeness](https://github.com/TVJunkie724/master-thesis/issues/151) | [`phase_08_5_optimizer_profile_resolution.md`](phase_08_5_optimizer_profile_resolution.md) | Profile-bounded, complete-path optimization | #142 |
| 8.6 | [#152 Build the Deployer graph resolver and staged binding preflight](https://github.com/TVJunkie724/master-thesis/issues/152) | [`phase_08_6_deployer_graph_resolver.md`](phase_08_6_deployer_graph_resolver.md) | Deterministic deployment graph and preflight | #151 |
| 8.7 | [#138 Implement the Flutter architecture profile workflow](https://github.com/TVJunkie724/master-thesis/issues/138) | [`phase_08_7_flutter_profile_workflow.md`](phase_08_7_flutter_profile_workflow.md) | Compact profile selection and read-only review | #152 |
| 8.8 | [#146 Complete the Eventing functional and cost decision gate](https://github.com/TVJunkie724/master-thesis/issues/146) | [`phase_08_8_eventing_decision_gate.md`](phase_08_8_eventing_decision_gate.md) | Approved Eventing capability, cost, and bridge contract | #152 |
| 8.9 | [#140 Implement six-layer-eventing@1 across the platform](https://github.com/TVJunkie724/master-thesis/issues/140) | [`phase_08_9_six_layer_eventing_implementation.md`](phase_08_9_six_layer_eventing_implementation.md) | Executable `six-layer-eventing@1` | #138, #146 |
| 8.10 | [#148 Produce Phase 8 evaluation evidence and final documentation](https://github.com/TVJunkie724/master-thesis/issues/148) | [`phase_08_10_evaluation_and_documentation.md`](phase_08_10_evaluation_and_documentation.md) | Reproducible evaluation package and complete docs | #140 |

Provider implementation work inside one phase may be parallelized only after
the phase's shared contract is committed. AWS, Azure, and GCP must pass the same
completion gate before the phase is closed.

## Native Dependency Graph

```text
#144 -> #139 -> #149 -> #150 -> #142 -> #151 -> #152
                     ^                          |       |
                     |                          |       +-> #146 --+
                    #113                        +-> #138 -----------+-> #140 -> #148 -> #112
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

Phase 8 is complete only when this chain is reproducible for both approved
profiles:

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
- `docs/research/digital_twin_architecture_and_eventing_layer.md` records the
  scientific architecture reasoning.
- `docs/research/research_questions_and_evaluation_design.md` records research
  questions and evaluation design.
- `docs/research/related_work_multicloud_cost_comparability_eventing.md`
  records related-work differentiation.
- `docs/plans/resolved_deployment_specification/README.md` records the completed
  cost-to-Terraform baseline contract that Phase 8 extends.
