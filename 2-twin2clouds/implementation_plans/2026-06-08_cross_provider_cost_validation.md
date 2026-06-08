# Cross-Provider Cost Validation

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

Depends on:

- `2026-06-08_azure_tiering_calculation_review.md`
- `2026-06-08_aws_tiering_calculation_review.md`
- `2026-06-08_gcp_credentials_pricing_evidence.md`
- `twin2multicloud_backend/implementation_plans/2026-06-08_cost_calculation_run_store.md`

## Goal

Validate the final cost-only optimizer path across AWS, Azure, and GCP with
zero publishable fallbacks and inspectable evidence for every cost field.

## Problem

Even if each provider works in isolation, cross-provider optimization can still
be wrong if provider-neutral intents do not line up:

- different units
- different tier boundaries
- different billing modes
- free tier assumptions
- service equivalence mismatches
- region/transfer assumptions

This phase verifies the whole cost path as a coherent provider comparison.
The validated result must be persistable as a Management API
`CostCalculationRun` with result items and evidence references.

## Scope

This phase is cost-only and validation-focused.

It must not:

- add new optimization metrics
- redesign the Flutter UI
- perform real cloud deployments
- accept `fallback_static` in publishable pricing
- create a separate optimizer database

## Validation Targets

Every active cost intent must be checked for:

- AWS evidence
- Azure evidence
- GCP evidence
- normalized unit
- calculation formula
- tier behavior
- selected row or official evidence
- rejected alternatives
- zero fallback in publishable state
- Management API run/result-item persistence compatibility

Validation output must be machine-readable and developer-readable. It should be
usable later by Flutter or documentation pages, but this phase does not build
the UI.

## Implementation Steps

1. Build a provider-neutral cost-intent coverage report.
2. Fail validation when any active provider/intent lacks evidence.
3. Fail validation when normalized units are incompatible.
4. Fail publish when any provider has `fallback_static`.
5. Add regression fixtures for representative workloads.
6. Verify calculation output includes evidence references.
7. Write a validation summary that lists publishable, review-required,
   non-applicable, and failed intents per provider.
8. Verify a representative validated calculation can be stored as a Management
   API cost-calculation run without losing evidence references.
9. Update developer/thesis documentation with the final evidence-backed cost
   flow.

## Test Strategy

Required tests:

- all active intents have provider coverage
- incompatible normalized units fail validation
- missing provider evidence fails validation
- fallback_static fails publish validation
- cost-only optimizer output is deterministic for representative workloads
- calculation results can be traced back to evidence ids
- validation summary exposes the selected evidence id per provider/intent
- persisted Management API run detail exposes the same evidence ids as the
  optimizer result

## Definition Of Done

- [ ] Active cost intents have AWS/Azure/GCP evidence or explicit
  non-applicability.
- [ ] Publishable pricing has zero fallback_static fields.
- [ ] Cost calculations reference evidence ids.
- [ ] Cross-provider unit compatibility is validated.
- [ ] Representative workload regression tests pass.
- [ ] Documentation explains the final evidence-backed cost flow.
- [ ] Validation summary is structured enough for a future UI to render without
  parsing logs.
- [ ] A validated calculation can be persisted and read back from the existing
  Management DB run store.

## Self Review

### Architect Review

- This is correctly late in the roadmap after provider evidence and tiering.
- Validation is cost-only and does not expand thesis scope prematurely.
- Evidence references make optimizer outputs auditable.

### Builder Review

- Validation targets and failure modes are concrete.
- Tests enforce cross-provider behavior rather than individual fetcher behavior.

### Review Findings

- Fixed: phase requires explicit non-applicability instead of silently ignoring
  provider gaps.
- Fixed: calculation output must reference evidence ids.
- Fixed: validation output is structured for future UI/dev inspection without
  making UI work part of this phase.
- Fixed: cross-provider validation now verifies compatibility with the
  Management API run store and rejects a separate optimizer DB.

No open findings after review.
