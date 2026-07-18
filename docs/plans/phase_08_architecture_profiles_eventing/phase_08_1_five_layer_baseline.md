---
title: "Phase 8.1: Harden And Freeze five-layer-baseline@1"
description: "Implementation plan for the explicit, executable, paper-compatible five-layer baseline decision contract."
tags: [architecture, baseline, five-layer, decisions, thesis, issue-139]
lastUpdated: "2026-07-19"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #139
- Phase 8.0 current graph artifacts defined by issue #144
- docs/research/digital_twin_architecture_and_eventing_layer.md
- docs/research/research_questions_and_evaluation_design.md
- docs/plans/resolved_deployment_specification/README.md
- EDTConf CloudDT paper and predecessor implementation provenance retained in the repository
EXTRACTED: 2026-07-19 | VERSION: 1.0
-->

# Phase 8.1: Harden And Freeze `five-layer-baseline@1`

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#139 Harden and freeze the five-layer-baseline@1 architecture profile](https://github.com/TVJunkie724/master-thesis/issues/139) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-five-layer-baseline` |
| Base branch | `master` |
| Blocked by | Phase 8.0 / #144 |
| Produces | Normative input for Phases 8.2-8.7 |
| Runtime behavior change | No; target decisions are implemented in later phases |
| Live cloud E2E | Forbidden |

Every edge and component from the approved Phase 8.0 inventory must receive a
decision. Partial decision coverage is a blocking failure.

## 1. Outcome

Freeze one explicit, executable target definition for
`five-layer-baseline@1`. It preserves the five paper-compatible functional and
cost responsibilities while rejecting the assumption that every inherited
function, direct call, name convention, or provider mapping is scientifically
required.

This phase decides the target graph and its invariants. It does not add the
shared profile classes or modify runtime wiring. Phases 8.2-8.7 implement the
approved decision through common contracts, provider catalogs, persistence,
optimization, deployment resolution, and Flutter.

### Scope Boundary

| Included | Excluded |
|---|---|
| Evidence-backed retain/internalize/replace/remove decisions for every current component and edge, five-layer invariants, provider admissibility, checker, and decision documentation | Runtime rewiring, shared profile schema implementation, persistence migration, Optimizer/Deployer/Flutter implementation, Eventing design, and live provider execution |

## 2. Required Inputs

The implementation must stop if any input is missing or stale:

- `contracts/architecture-inventory/v1/current-graph.json`;
- passing `scripts/check_architecture_inventory.py`;
- `docs/research/phase_08_current_function_edge_matrix.md`;
- current resolved-deployment-specification roadmap and contracts;
- paper and bachelor implementation provenance;
- current provider capability and deployment drift matrices.

The recorded `audited_source_tree_digest` must match the source tree before
decisions begin.

## 3. Scientific Baseline Invariants

The following responsibilities are mandatory:

| Responsibility ID | Scientific purpose | Current optimization slots |
|---|---|---|
| `responsibility.ingestion` | Receive and normalize device telemetry | `l1_ingestion` |
| `responsibility.processing` | Apply user/domain transformation and event checks | `l2_processing` |
| `responsibility.storage` | Persist hot, cool, and archive data under explicit retention assumptions | `l3_hot_storage`, `l3_cool_storage`, `l3_archive_storage` |
| `responsibility.twin-state` | Maintain/query operational or semantic Twin state | `l4_twin_state` |
| `responsibility.visualization` | Expose the Twin state for visualization | `l5_visualization` |

The seven optimization slots remain separately costed because the three L3
storage classes have distinct provider services, billing units, retention
inputs, and transition runtimes. This does not turn them into seven scientific
layers.

The baseline must retain the six workload/transfer relationships already
defined by the complete-path optimizer:

```text
L1 -> L2
L2 -> L3 hot
L3 hot -> L3 cool
L3 cool -> L3 archive
L3 hot -> L4
L4 -> L5
```

These relationships define functional and cost flow, not a requirement that
each transition is a remote function call.

## 4. Fixed Decisions

1. `five-layer-baseline@1` contains no general Eventing responsibility, broker,
   queue, or event-service cost.
2. Provider-native triggers that are intrinsic to an approved service may
   remain implementation details. They must not be presented as the Eventing
   profile.
3. Same-responsibility helper calls must be internalized into one deployable
   component when separate deployment adds no trust, scaling, lifecycle,
   failure-isolation, or independent-consumer boundary.
4. A retained synchronous remote edge requires an immediate-response
   requirement, typed request/response contract, timeout, bounded retry policy,
   identity, correlation, and cost ownership.
5. Storage transitions must use provider lifecycle features only when they
   preserve the modeled timing, destination semantics, cross-provider
   behavior, observability, and cost ownership. Otherwise the explicit
   source-owned mover remains.
6. Cross-provider edges require explicit source/destination adapters and
   transfer-cost ownership. Functions must not derive another component's
   resource name or endpoint.
7. Provider services may be represented by a reviewed bundle, not forced into
   one-to-one service equivalence.
8. A provider/profile candidate is admissible only if every mandatory
   capability and edge behavior is complete.
9. Unsupported all-provider combinations remain explicitly unsupported. Mixed
   profiles must not fabricate missing provider capability.
10. The existing unsupported error-handling topology remains outside the
    executable baseline unless a separate approved contract reintroduces it.
11. User logic remains behind platform-owned wrappers and approved extension
    slots. Phase 8.3 must not bind a user slot before #113 completes.
12. All cost, formula, pricing evidence, transfer, runtime, deployment
    dimension, and package references remain traceable.

## 5. Decision Artifacts

Create:

```text
contracts/architecture-inventory/v1/
  baseline-decision.schema.json
  five-layer-baseline-v1-decision.json
docs/research/five_layer_baseline_target_decision.md
docs-site/docs/architecture/five-layer-baseline.md
```

The JSON is the machine-readable target decision SSOT for Phases 8.2-8.7.
The research document explains alternatives, predecessor debt, limitations, and
threats to validity. The docs-site page explains only the approved current
baseline after it becomes implemented; until Phase 8.7 it must be clearly
marked as a target design and must not replace current-behavior documentation.

## 6. Decision Contract

Top-level required fields:

| Field | Rule |
|---|---|
| `schema_version` | Constant `five-layer-baseline-decision.v1` |
| `profile_id` | Constant `five-layer-baseline` |
| `profile_version` | Constant `1` |
| `source_inventory_digest` | Exact Phase 8.0 content digest |
| `required_responsibilities` | Exactly the five IDs in Section 3 |
| `optimization_slots` | Exactly the seven current deployment slots |
| `component_decisions` | One decision for every in-scope current component |
| `edge_decisions` | One decision for every in-scope current edge |
| `provider_admissibility` | Explicit AWS/Azure/GCP and mixed constraints |
| `functional_completeness_rules` | Machine-readable required capabilities |
| `cost_ownership_rules` | One owner for every modeled cost |
| `compatibility_rules` | Current contract/profile compatibility |
| `residual_limitations` | Explicit accepted baseline limitations |
| `content_digest` | Deterministic SHA-256 |

### 6.1 Component Decision

Each current component must be assigned exactly one action:

- `retain`: independent deployable component remains;
- `internalize`: behavior moves behind another retained component boundary;
- `replace`: a named target component/mechanism provides equivalent required
  behavior;
- `remove`: behavior is proven unused, duplicate, or unsupported and is not
  part of the baseline.

Required fields:

- current and target component IDs;
- action;
- target responsibility;
- provider applicability;
- functional behavior before/after;
- trust, scaling, lifecycle, failure-isolation, and ownership rationale;
- package/Terraform effect;
- cost/formula effect;
- migration/compatibility effect;
- implementation owner phase;
- source evidence and decision evidence.

`internalize`, `replace`, and `remove` require an explicit proof that no
observable behavior, required capability, or modeled cost disappears.

### 6.2 Edge Decision

Each current edge must be assigned exactly one target mechanism:

- `in_process_port`;
- `typed_synchronous_api`;
- `provider_native_trigger`;
- `provider_workflow`;
- `storage_lifecycle`;
- `source_owned_transition_runtime`;
- `cross_provider_adapter`;
- `remove`.

Required fields:

- current and target edge IDs;
- mechanism;
- source/destination target component IDs;
- payload/envelope and schema version;
- invocation and delivery semantics;
- timeout/retry/dead-letter/idempotency/ordering behavior;
- trust and authentication;
- correlation/observability;
- transfer route and cost owner;
- resource-binding source;
- rationale and rejected alternatives;
- implementation owner phase;
- compatibility and verification fixtures.

A target mechanism may not use a duplicated string convention to identify
another resource. Its binding source must be a declared component output,
platform binding, or profile constant.

### 6.3 Provider Admissibility

For each provider implementation and supported mixed boundary, record:

- mandatory capabilities;
- implementation component bundle;
- known extra functionality;
- missing functionality;
- deployment support status;
- pricing/formula/evidence support status;
- exact unsupported error code and reason.

`supported` is allowed only if both functional and deployable status are
complete. A service that is merely priceable or present in a catalog is not
admissible.

## 7. Decision Procedure

Apply this order to every component and edge:

1. identify the logical responsibility and externally observable behavior;
2. identify trust, lifecycle, scaling, independent deployment, and failure
   boundaries;
3. identify synchronous response, fan-out, ordering, replay, and retention
   requirements;
4. identify current provider-specific behavior and equivalence gaps;
5. identify workload, formula, pricing, transition-runtime, and transfer costs;
6. evaluate `retain`, `internalize`, `replace`, or `remove`;
7. select the least complex mechanism that preserves every mandatory behavior;
8. record rejected alternatives and evidence;
9. verify provider and mixed-profile admissibility;
10. assign the implementation to exactly one later phase.

Do not use lowest cost to decide functional completeness. Cost comparison is
performed only after the admissibility decision.

## 8. Required Baseline Scenarios

The decision must cover:

- all-AWS;
- all-Azure where current capabilities are complete;
- all-GCP only for responsibilities that are currently complete;
- each current explicitly supported mixed-provider transfer boundary;
- hot-to-cool and cool-to-archive transitions;
- L3-hot-to-L4 query flow;
- L4-to-L5 visualization flow;
- user processor path;
- optional event-check and feedback states exactly as currently executable or
  explicitly unsupported.

Unsupported scenarios remain in fixtures with stable rejection reasons. They
must not be omitted from evaluation input.

## 9. Machine Check

Extend the architecture inventory checker to:

- validate the decision schema;
- verify exact source inventory digest;
- require one component decision per in-scope component;
- require one edge decision per in-scope edge;
- reject target IDs not declared by a decision;
- reject missing implementation-owner phases;
- reject `internalize`, `replace`, or `remove` without behavior/cost proofs;
- reject supported provider candidates with missing capabilities, deployment
  support, formula, or evidence;
- reject resource bindings based on constructed names;
- reject Eventing responsibility/services/costs in the baseline;
- verify deterministic digest and decision-document diagram IDs.

## 10. Failure And Security Requirements

Stable validation categories:

- `SOURCE_INVENTORY_STALE`
- `COMPONENT_DECISION_MISSING`
- `EDGE_DECISION_MISSING`
- `TARGET_REFERENCE_UNRESOLVED`
- `FUNCTIONAL_PROOF_MISSING`
- `COST_OWNER_MISSING`
- `PROVIDER_BUNDLE_INCOMPLETE`
- `RESOURCE_BINDING_IMPLICIT`
- `EVENTING_SCOPE_LEAK`
- `DECISION_DIGEST_MISMATCH`

Decision artifacts must contain no credentials, resource instance names,
account/project IDs, endpoint values, or user payloads.

## 11. Tests And Verification

Add:

```text
3-cloud-deployer/tests/unit/architecture_inventory/
  test_five_layer_baseline_decision.py
```

Tests must cover:

- valid complete decision;
- every missing component/edge decision;
- every invalid action/mechanism;
- internalize/replace/remove without proof;
- stale source inventory digest;
- incomplete provider capability;
- formula/evidence/deployment gap;
- duplicated/constructed resource binding;
- Eventing scope leak;
- deterministic digest mutation;
- unsupported scenario visibility.

Safe verification:

```bash
python scripts/check_architecture_inventory.py
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/unit/architecture_inventory/ -v
./thesis.sh test deployment-contract
docker compose --profile docs run --rm docs mkdocs build --strict
```

`deployment-contract` is a credential-free drift gate. Do not run live apply,
destroy, or provider E2E.

## 12. Documentation And Issue Updates

- Add target/current comparison and complete decision rationale to
  `docs/research/five_layer_baseline_target_decision.md`.
- Preserve current behavior separately until later phases implement the target.
- Add the baseline page to docs navigation only with an explicit implementation
  status.
- Update the roadmap with the full issue title and artifacts.
- Update #139 with decision coverage counts, supported/unsupported scenario
  counts, verification commands, and residual limitations.

## 13. Rollout And Compatibility

No runtime rollout occurs in this phase. The decision contract is consumed by
Phases 8.2-8.7. A later phase must not silently change a decision; it must:

1. update the decision contract;
2. increment the decision content digest;
3. rerun Phase 8.0 source reconciliation;
4. record why the implementation evidence required a change;
5. update affected plans/issues before code changes.

### 13.1 Rollback

Because this phase changes decision evidence only, rollback never restores an
older graph by deleting the new record. Mark the decision version
`superseded`, preserve its source digest and review evidence, keep Phases
8.2-8.7 blocked, and restore the prior issue/roadmap status. A corrected target
requires a new immutable decision version and complete revalidation against the
same Phase 8.0 inventory or a newer verified inventory.

## 14. Definition Of Done

- [ ] The Phase 8.0 inventory digest is current and verified.
- [ ] Exactly five scientific responsibilities and seven optimization slots
      are defined without conflating them.
- [ ] All six baseline flow/cost relationships remain explicit.
- [ ] Every current component has one retain/internalize/replace/remove
      decision.
- [ ] Every current edge has one explicit target mechanism and binding source.
- [ ] No historical direct call is retained solely because it exists.
- [ ] No required behavior or cost disappears without proof.
- [ ] AWS, Azure, GCP, and mixed-provider admissibility is explicit and
      fail-closed.
- [ ] Unsupported scenarios remain visible with stable reasons.
- [ ] Eventing behavior and cost are excluded from the baseline profile.
- [ ] Compatibility with the resolved deployment specification is explicit.
- [ ] Machine checks and negative fixtures enforce full decision coverage.
- [ ] Research and current/target product documentation remain separated.
- [ ] Safe deployment-contract and strict documentation gates pass.
- [ ] No runtime behavior or cloud resource changes.
- [ ] Two reviews find no unresolved issue.
- [ ] Roadmap and #139 are updated with named evidence.
- [ ] The structured commit references #139.
