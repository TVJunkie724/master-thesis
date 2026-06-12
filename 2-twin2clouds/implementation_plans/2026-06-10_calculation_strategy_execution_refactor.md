# Calculation Strategy Execution Refactor

## Metadata

- Phase: 15
- Status: planned
- Parent roadmap: `docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`
- Depends on: Phase 12, Phase 13, Phase 14
- Parent issues: #69, #32, #99
- Scope owner: `2-twin2clouds`
- No live cloud deployment E2E in this phase

## Goal

Refactor calculation execution so the active calculation strategy and formula
set are resolved before provider/layer calculators run.

Provider calculators remain provider-specific, but they must execute inside the
validated optimization bundle instead of implicitly selecting formulas and
pricing fields.

## Target Flow

```text
calculate(request)
    -> resolve optimization profile
    -> resolve calculation strategy
    -> resolve formula set
    -> resolve workload contract
    -> validate provider pricing contracts
    -> validate pricing model/source classifications
    -> execute provider/layer calculators
    -> score candidates
    -> return result + contract metadata
```

## Implementation Steps

1. Introduce a calculation strategy execution context.
   Suggested fields:
   - `optimization_profile_id`
   - `calculation_strategy_id`
   - `formula_set_id`
   - `workload_contract_id`
   - `pricing_contract_group_id`
   - `pricing_model_classification_group_id`
   - `price_source_classification_group_id`
   - `publishable_mode`
2. Update `backend/calculation_v2/engine.py` to resolve the context before
   provider calculations.
3. Pass the context into provider/layer calculators or into a narrow adapter
   that validates provider calculator access.
4. Ensure formula helpers are invoked through named formula refs or a formula
   registry that belongs to `cost_formula_set_v1`.
5. Include strategy/contract metadata in calculation results.
6. Preserve existing public `/calculate` behavior for callers that use the
   default cost profile.
7. Reject disabled/future calculation strategies with typed errors.

## Expected Touchpoints

- `2-twin2clouds/backend/calculation_v2/engine.py`
- `2-twin2clouds/backend/calculation_v2/components/base.py`
- `2-twin2clouds/backend/calculation_v2/formulas/`
- `2-twin2clouds/backend/optimization/profiles.py`
- `2-twin2clouds/backend/pricing_contract_validation.py`
- `2-twin2clouds/tests/unit/calculation_v2/test_engine.py`
- `2-twin2clouds/tests/unit/pricing/test_calculation_strategy_execution.py`
- `2-twin2clouds/tests/unit/optimization/test_optimization_profiles.py`

## Compatibility Requirements

- Existing cost result shape remains backward-compatible unless fields are
  additive metadata.
- Management API run persistence must still accept optimizer results.
- `evidenceReferences` remains present.
- No new optimizer database is introduced.
- No frontend changes are required.

## Error Handling

Typed failures must be returned for:

- missing default optimization profile
- disabled calculation strategy
- unknown formula set
- missing workload contract
- provider calculator invoked without compatible pricing contract
- provider calculator requesting a formula ref outside the active formula set
- calculation result missing required metadata

Errors must be deterministic and secret-free.

## Security Requirements

- Execution context must not carry credentials.
- Calculation errors must include contract IDs and field paths, not raw provider
  payloads.
- Result metadata must remain safe for Management API persistence.

## Non-Goals

- No new optimization metric.
- No weighted multi-objective execution.
- No formula semantics rewrite unless needed to route through the formula set.
- No live provider E2E.
- No UI changes.

## Test Plan

Add or update tests under:

- `2-twin2clouds/tests/unit/calculation_v2/`
- `2-twin2clouds/tests/unit/optimization/`
- `2-twin2clouds/tests/unit/pricing/`

Required tests:

- default `/calculate` path still produces current cost ranking
- result metadata includes all strategy and contract IDs
- disabled strategy cannot execute
- unknown formula set fails
- provider calculator cannot use formula outside active formula set
- provider calculator cannot execute without compatible pricing contract
- Management API compatibility is preserved through existing evidence metadata
- existing provider tiering tests remain green

Recommended command:

```bash
cd 2-twin2clouds
python -m pytest \
  tests/unit/calculation_v2/test_engine.py \
  tests/unit/calculation_v2/test_aws_tiering.py \
  tests/unit/calculation_v2/test_azure_tiering.py \
  tests/unit/calculation_v2/test_gcp_tiering.py \
  tests/unit/optimization/test_optimization_profiles.py \
  tests/unit/pricing/test_calculation_strategy_execution.py \
  -q
```

Management API compatibility smoke:

```bash
cd twin2multicloud_backend
python -m pytest tests/test_cost_calculation_runs.py -q
```

## Definition Of Done

- [ ] Calculation resolves an execution context before provider calculators run.
- [ ] `cost_calculation_v2` is the only executable calculation strategy.
- [ ] Formula usage is traceable to `cost_formula_set_v1`.
- [ ] Provider calculators fail when contract context is missing or
      incompatible.
- [ ] Result metadata includes strategy and contract IDs.
- [ ] Existing cost calculation behavior remains backward-compatible.
- [ ] Roadmap phase 15 is updated to implemented when the phase is complete.

## Review Gate

Before commit:

- [ ] Run the phase-specific pytest command.
- [ ] Run the Management API compatibility smoke test.
- [ ] Run `git diff --check`.
- [ ] Review that all formula usage is traceable to the active formula set.
- [ ] Review that disabled strategies cannot execute.
- [ ] Update this plan with implementation notes and completed checkbox state.

## Review Findings Fixed In Plan

- Fixed: formulas are selected by calculation strategy, not by provider code.
- Fixed: provider calculators are constrained by provider pricing contracts.
- Fixed: result metadata becomes audit-friendly.
- Fixed: existing Management API run store remains compatible.
