# Cross-Provider Cost Validation

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

Issue for this phase: GitHub issue #94

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

- active optimization profile compatibility
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
7. Verify calculation output includes `optimization_profile_id`, result schema
   version, and compatible cost intent groups.
8. Write a validation summary that lists publishable, review-required,
   non-applicable, and failed intents per provider.
9. Verify a representative validated calculation can be stored as a Management
   API cost-calculation run without losing evidence references.
10. Update developer/thesis documentation with the final evidence-backed cost
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
- validation fails when the active profile is not `cost_minimization_v1` or is
  incompatible with cost intents
- persisted Management API run detail exposes the same evidence ids as the
  optimizer result
- persisted Management API run detail exposes the same optimization profile id
  as the optimizer result

## Definition Of Done

- [x] Active cost intents have AWS/Azure/GCP evidence or explicit
  non-applicability.
- [x] Active optimization profile is compatible with cost intents and result
  schema.
- [x] Publishable pricing has zero fallback_static fields.
- [x] Cost calculations reference evidence/registry metadata and validation
  summaries expose selected evidence ids.
- [x] Cross-provider unit compatibility is validated.
- [x] Representative workload regression tests pass.
- [x] Documentation explains the final evidence-backed cost flow.
- [x] Validation summary is structured enough for a future UI to render without
  parsing logs.
- [x] A validated calculation can be persisted and read back from the existing
  Management DB run store.
- [x] Persisted run history retains optimization profile metadata.

## Implementation Summary

Implemented in issue #94:

- Added `backend.cross_provider_cost_validation` as the provider-neutral
  publish gate for cost evidence.
- Validates all active cost intents from `PricingRegistryService` against AWS,
  Azure, and GCP evidence reports.
- Fails publishable validation for missing provider reports, missing
  provider/intent records, `fallback_static`, unresolved `review_required`
  evidence, incompatible normalized units, and incompatible optimization
  profile/result-schema metadata.
- Allows explicit `not_applicable` provider evidence only when it is not marked
  review-required.
- Produces a structured summary with provider/intent status, selected evidence
  ids, selected-row identity, candidate/rejected counts, publishable/review/
  non-applicable/failed counters, and Management-run compatibility status.
- Added `evidenceReferences` to calculation-v2 optimizer results.
- Hardened the Management API run-store contract so optimizer responses without
  evidence-reference metadata are rejected before persistence.

## Verification

Focused optimizer validation and engine contract:

```bash
docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/unit/pricing/test_cross_provider_cost_validation.py tests/unit/calculation_v2/test_engine.py -q'
```

Result:

```text
17 passed
```

Broad optimizer pricing/profile/calculation suite:

```bash
docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/unit/pricing tests/unit/optimization tests/unit/calculation_v2 -q'
```

Result:

```text
218 passed
```

Management API run-store focused suite:

```bash
PYTHONPATH=. /Users/caroline/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m pytest tests/test_cost_calculation_runs.py -q
```

Result:

```text
12 passed
```

Full Management backend suite:

```bash
PYTHONPATH=. /Users/caroline/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m pytest tests -q
```

Result:

```text
303 passed
```

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
- Fixed: cross-provider validation now checks active optimization profile
  compatibility and persistence metadata.
- Fixed: publishable validation now requires calculation-result evidence
  metadata, not only provider evidence reports.
- Fixed: `not_applicable` evidence marked as review-required is not publishable.
- Fixed: Management API run persistence now rejects optimizer responses that
  omit `evidenceReferences`.

No open findings after review.
