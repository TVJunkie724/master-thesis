# Phase 4b: Storage Transition Runtime Ownership

**Issue:** [#61](https://github.com/TVJunkie724/master-thesis/issues/61)
**Status:** Implemented and verified
**Blocked by:** #127, #129, #130, #131

## Problem

The current baseline prices each hot-to-cool and cool-to-archive mover as part
of the destination storage slot. The deployed mover instead executes beside
the source storage and invokes a destination writer when the transition
crosses providers.

For single-cloud paths source and destination are identical, so the mismatch is
invisible. For mixed storage paths the Optimizer can price one provider's
runtime while Terraform deploys another provider's function. Provider-specific
memory, plan, scaling, permission, and free-tier assumptions can therefore
refer to the wrong resource.

## Target

Model exactly the two existing baseline transition edges as closed-world
runtime contracts:

```text
L3 hot storage
  -> source-owned hot-to-cool mover
  -> optional destination-owned cold writer
  -> L3 cool storage

L3 cool storage
  -> source-owned cool-to-archive mover
  -> optional destination-owned archive writer
  -> L3 archive storage
```

This phase does not create arbitrary graph editing, new storage paths, or a
generic workflow engine. The two edges and their ownership rules remain fixed
for `five-layer-baseline@1`.

## Contract Changes

1. Add a closed-world `transition_runtime` component slot to the canonical
   resolved-deployment registry.
2. Add a `transition_runtime_policy` registry section with exactly two ordered
   edge definitions. Every definition must contain `boundary_id`,
   `source_slot`, `target_slot`, canonical monthly invocation count and basis,
   and a provider-to-component mapping.
3. Register one source-owned runtime bundle for each transition and provider:
   - `transition.l3_hot_to_l3_cool.aws.runtime`
   - `transition.l3_hot_to_l3_cool.azure.runtime`
   - `transition.l3_hot_to_l3_cool.gcp.runtime`
   - `transition.l3_cool_to_l3_archive.aws.runtime`
   - `transition.l3_cool_to_l3_archive.azure.runtime`
   - `transition.l3_cool_to_l3_archive.gcp.runtime`
4. A runtime bundle represents the mover function and its timer/scheduler
   trigger. Its typed dimensions contain the formula-bound function runtime
   profile and fixed baseline schedule. Provider phases 5-7 own final
   Terraform-resource wiring and official pricing-source verification.
5. Derive transition provider ownership from the source slot:
   - hot-to-cool uses `l3_hot_storage.provider`;
   - cool-to-archive uses `l3_cool_storage.provider`.
6. Keep cross-cloud writer/glue ownership on the destination provider.
7. Rename mover Terraform targets so they describe the edge rather than
   incorrectly implying destination-slot ownership.
8. Preserve existing function memory, plan, scaling, duration, schedule, and
   invocation assumptions as explicit typed dimensions.
9. Remove destination-owned mover components from the three L3 cool/archive
   slot requirements. Storage slots retain storage components only; transition
   runtimes are emitted in canonical edge order after the seven baseline slots
   and before cross-cloud glue.
10. Regenerate schema fixtures and byte-identical Optimizer, Management API, and
   Deployer contract copies.

The contract remains v1 while it is unreleased and repository-internal. The
schema/registry version strings do not change; all golden digests and fixtures
must be regenerated atomically. Historical development runs become
`legacy_not_deployable` through the existing digest/compatibility boundary.

## Optimizer Changes

1. Remove mover-function and trigger cost from destination storage layer base
   totals and deployment selections.
2. Introduce an immutable `TransitionRuntimeResult` returned by every provider
   calculator. It contains edge ID, provider, function cost, trigger cost,
   total cost, invocation count/basis, formula/evidence references, and the
   exact `ComponentDeploymentSelection`.
3. Calculate source-provider mover cost for both transition edges in every
   candidate, including same-provider paths.
4. Keep destination writer/glue cost only for cross-provider paths.
5. Do not overload `TransferSegmentCharge`. Extend
   `CompletePathEvaluation` with separate transition charges and
   `transition_runtime_cost`; total candidate cost must equal layer cost plus
   transfer/glue cost plus transition-runtime cost.
6. Add the following additive result contracts:
   - `transitionRuntimeCosts`: edge-to-source-runtime cost;
   - `transitionRuntimeContext` using
     `baseline-transition-runtime.v1`;
   - `optimizationDiagnostics.winningTransitionRuntimeCost`.
7. The transition context must expose:
   - source mover provider;
   - source and destination slot/provider;
   - source runtime component and formula/evidence references;
   - invocation quantity and schedule basis;
   - function and trigger cost;
   - destination writer provider when required;
   - separate mover, writer/glue, egress, and total contributions.
8. Include the two transition runtime selections in
   `ResolvedDeploymentSpecification v1`.
9. Extend currency conversion and strategy/intent traceability so the new cost
   fields are converted and reconciled exactly once.
10. Preserve deterministic path scoring and reject missing runtime selections.

## Management API Changes

1. Validate the exact two transition runtime components and source-provider
   ownership against the selected path.
2. Persist them only inside the existing immutable resolved specification.
3. Preserve atomic run/result/specification persistence and digest continuity.
4. Reject packages whose transition ownership differs from the selected
   Optimizer path.
5. Accept the additive transition evidence fields without duplicating their
   costs into Management-owned calculations. Keep historical result
   projections readable; historical runs without transition ownership remain
   non-deployable.

## Deployer Changes

1. Validate transition cardinality, ordering, provider ownership, and
   destination-writer requirements before package staging.
2. Translate only transition dimensions classified as
   `deployable_selection`.
3. Emit edge- and provider-specific typed tfvars without applying them to a
   destination storage resource. The immediately following provider phases
   bind them to:
   - AWS source-owned Lambda/EventBridge resources in #132;
   - Azure source-owned Function/Timer resources in #133;
   - GCP source-owned Function/Cloud Scheduler resources in #120.
4. Keep destination cold/archive writers behind the existing cross-cloud glue
   contract.
5. Fail closed when a provider path requires a mover or writer that the current
   baseline cannot deploy.

## Required File Boundaries

| Area | Files |
| --- | --- |
| Canonical contract | `contracts/resolved-deployment-specification/v1/` |
| Contract generation | `scripts/sync_resolved_deployment_contract.py` |
| Optimizer scoring/evidence | `2-twin2clouds/backend/calculation_v2/` |
| Management validation | `twin2multicloud_backend/src/services/resolved_deployment_specification_service.py` and pricing/transfer validation |
| Deployer validation | `3-cloud-deployer/src/deployment_specification/` |
| Runtime resources | deferred to provider phases #132, #133, and #120 |
| Documentation | contract, Optimizer, Management, Deployer, roadmap, known limitations |

## Tests

- all 27 complete `(hot, cool, archive)` provider triples resolve both source
  runtimes correctly, thereby covering all 9 source/destination provider pairs
  for each transition;
- same-provider transitions include one mover and no destination writer;
- cross-provider transitions include one source mover and one destination
  writer;
- candidate totals equal layer costs plus both source runtimes plus optional
  writer/glue plus egress, with no duplicated mover cost in destination storage;
- the winner and route evidence preserve exact component/provider/formula
  identity;
- manifest/specification validation rejects missing, duplicate, destination-
  owned, reordered, or provider-drifted transition components;
- the translator emits only source-owned, allowlisted transition tfvars;
- provider Terraform source/validate gates remain owned by phases 5-7 because
  this phase intentionally does not complete resource wiring;
- legacy result compatibility remains explicit and non-deployable.

## Non-Goals

- no arbitrary architecture graph;
- no user-selectable mover placement;
- no new storage service or transition;
- no provider-native lifecycle-policy redesign;
- no live cloud apply or billable E2E execution;
- no Phase 8 architecture profile or eventing implementation.

## Definition of Done

- [x] Costed mover provider equals the source provider and selected transition
      component provider for both transitions.
- [x] Destination writer/glue is costed and deployed only for cross-provider edges.
- [x] Every positive source/destination combination has deterministic evidence.
- [x] All contract copies, digests, fixtures, and OpenAPI snapshots are synchronized.
- [x] Candidate totals, currency conversion, strategy trace, and resolved
      specification reconcile transition cost exactly once.
- [x] Optimizer, Management API, Deployer, contract-sync, and strict-docs safe
      gates pass.
- [x] Two review passes report no unresolved finding.
- [x] #61 is closed with commit and verification evidence.

## Verification Evidence

Verified on 2026-07-18 without live provider credentials or billable cloud
operations:

| Gate | Result |
| --- | --- |
| Optimizer safe suite | `800 passed` |
| Management API suite | `865 passed` |
| Deployer unit/API/integration suite | `1494 passed, 1 skipped` |
| Post-review focused transition tests | `37 passed` |
| Contract generation/sync/check | valid and byte-identical |
| Ruff, compile, and dependency integrity | all three Python projects passed |
| Bandit | changed Optimizer, Management, and Deployer boundaries passed |
| MkDocs strict build | passed |

Provider HCL consumption of the emitted transition tfvars remains intentionally
owned by #132, #133, and #120. The final cross-stack equality gate remains
#128.
