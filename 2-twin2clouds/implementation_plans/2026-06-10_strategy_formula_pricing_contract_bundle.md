# Strategy Formula Pricing Contract Bundle

## Metadata

- Phase: 13
- Status: implemented
- Parent roadmap: `docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`
- Depends on: Phase 12 pricing model/source classification
- Parent issues: #69, #32, #97
- Scope owner: `2-twin2clouds`
- No live cloud deployment E2E in this phase

## Goal

Create a versioned optimization bundle that binds the executable cost profile to
one calculation strategy, one formula set, one workload contract, one pricing
model classification group, one price source classification group, and one
provider pricing contract group.

This makes the optimizer profile the compatibility boundary and prevents metric
providers, formulas, contracts, and scoring logic from drifting apart.

## Target Bundle

```text
cost_minimization_v1
    -> metric_provider: cost
    -> calculation_strategy: cost_calculation_v2
    -> formula_set: cost_formula_set_v1
    -> workload_contract: digital_twin_workload_v1
    -> pricing_model_classification_group: cost_pricing_models_v1
    -> price_source_classification_group: cost_price_sources_v1
    -> pricing_contract_group: cost_provider_pricing_contracts_v1
    -> scoring_strategy: min_total_cost_v1
```

## Implementation Steps

1. Add registry files under `2-twin2clouds/pricing_registry/`.
   - `optimization_bundles.yaml`
   - `calculation_strategies.yaml`
   - `formula_sets.yaml`
   - `workload_contracts.yaml`
   - `provider_pricing_contracts.yaml`
2. Extend `PricingRegistryService` with typed accessors:
   - `list_optimization_bundles()`
   - `get_optimization_bundle(id)`
   - `get_calculation_strategy(id)`
   - `get_formula_set(id)`
   - `get_workload_contract(id)`
   - `get_provider_pricing_contract(provider, layer, service)`
3. Update `backend/optimization/profiles.py` so
   `cost_minimization_v1` resolves the bundle instead of carrying only broad
   profile metadata.
4. Keep existing `/calculate` behavior compatible. Requests that do not specify
   a profile continue to use `cost_minimization_v1`.
5. Future strategies may be declared disabled, but must not execute.
6. Do not move calculation logic yet; this phase establishes contracts only.

## Implementation Notes

- Added five versioned registry SSOT files:
  - `optimization_bundles.yaml`
  - `calculation_strategies.yaml`
  - `formula_sets.yaml`
  - `workload_contracts.yaml`
  - `provider_pricing_contracts.yaml`
- Added one executable bundle, `cost_minimization_v1`, bound to
  `cost_calculation_v2`, `cost_formula_set_v1`,
  `digital_twin_workload_v1`, and 48 provider pricing contracts.
- Extended the pricing registry loader so contracts are validated together with
  Phase 12 pricing model and source classifications.
- Extended `PricingRegistryService` with typed read accessors and defensive
  copies.
- Extended read-only pricing registry API status and list endpoints for
  optimization bundles and provider pricing contracts.
- Updated `OptimizationProfileRegistry` so enabled profiles must resolve a
  ready, enabled optimization bundle and result metadata contains bundle
  contract metadata.

## Expected Touchpoints

- `2-twin2clouds/pricing_registry/optimization_bundles.yaml`
- `2-twin2clouds/pricing_registry/calculation_strategies.yaml`
- `2-twin2clouds/pricing_registry/formula_sets.yaml`
- `2-twin2clouds/pricing_registry/workload_contracts.yaml`
- `2-twin2clouds/pricing_registry/provider_pricing_contracts.yaml`
- `2-twin2clouds/backend/pricing_registry_service.py`
- `2-twin2clouds/backend/optimization/profiles.py`
- `2-twin2clouds/tests/unit/optimization/test_optimization_profiles.py`
- `2-twin2clouds/tests/unit/pricing/test_strategy_formula_pricing_contract_bundle.py`

## Data Ownership And Compatibility

- Bundle and contract files are source-controlled registry SSOT.
- No generated evidence artifacts become editable SSOT.
- No optimizer database or Management API database migration is required.
- Existing requests without an explicit optimization profile continue to use
  `cost_minimization_v1`.
- Result metadata may be additive but must not remove existing fields.

## Security Requirements

- Bundle and contract files must not contain credentials, account IDs, or local
  credential paths.
- Validation errors must avoid raw provider payloads and secrets.
- Future disabled profiles must be metadata-only and must not expose fake scores.

## Provider Pricing Contract Shape

Each provider pricing contract must declare:

- `id`
- `provider`
- `layer`
- `service`
- `pricing_model_classification_id`
- `allowed_price_source_types_by_field`
- `required_evidence_fields`
- `curated_model_constants`
- `normalization_rules`
- `allowed_formula_refs`
- `calculation_component`
- `consumed_workload_fields`
- `output_metric_unit`

## Validation Rules

The loader must fail on:

- unknown calculation strategy IDs
- unknown formula set IDs
- unknown workload contract IDs
- missing pricing model classification IDs
- missing price source classification IDs
- provider pricing contracts referencing unknown formula refs
- provider pricing contracts consuming unknown workload fields
- provider pricing contracts allowing unknown source types
- duplicate IDs
- executable future profiles without implemented metric/calculation/scoring
  contracts

## Non-Goals

- No formula behavior changes.
- No provider evidence matching changes.
- No Management API schema changes.
- No editable UI.
- No live provider E2E.

## Test Plan

Add tests under:

- `2-twin2clouds/tests/unit/optimization/`
- `2-twin2clouds/tests/unit/pricing/`

Required tests:

- default `cost_minimization_v1` resolves the complete bundle
- disabled future profile cannot execute
- unknown formula ref fails validation
- unknown workload field fails validation
- missing pricing model classification fails validation
- missing price source classification fails validation
- disallowed source type fails validation
- duplicate provider pricing contract ID fails validation
- bundle metadata is returned in optimization profile output

Recommended command:

```bash
cd 2-twin2clouds
python -m pytest \
  tests/unit/optimization/test_optimization_profiles.py \
  tests/unit/pricing/test_strategy_formula_pricing_contract_bundle.py \
  -q
```

## Definition Of Done

- [x] Versioned bundle and contract registry files exist.
- [x] `PricingRegistryService` exposes typed read access.
- [x] `cost_minimization_v1` resolves exactly one executable bundle.
- [x] Future profiles remain disabled/non-executable.
- [x] Provider contracts may only reference formulas from the active formula set.
- [x] Provider contracts may only consume workload fields from the active
      workload contract.
- [x] Tests cover positive and negative contract validation.
- [x] Roadmap phase 13 is updated to implemented when the phase is complete.

## Review Gate

Before commit:

- [x] Run the phase-specific pytest command.
- [x] Run `git diff --check`.
- [x] Review that every executable bundle resolves all referenced contracts.
- [x] Review that future profiles are disabled and non-executable.
- [x] Update this plan with implementation notes and completed checkbox state.

## Verification

```bash
cd 2-twin2clouds
/tmp/t2mc-phase12-py311/bin/python -m pytest \
  tests/unit/optimization/test_optimization_profiles.py \
  tests/unit/pricing/test_strategy_formula_pricing_contract_bundle.py \
  tests/unit/pricing/test_pricing_registry_api.py \
  -q
```

Result: 39 passed, 1 warning.

```bash
cd 2-twin2clouds
/tmp/t2mc-phase12-py311/bin/python -m pytest \
  tests/unit/pricing/test_pricing_registry_foundation.py \
  tests/unit/pricing/test_pricing_model_source_classification.py \
  tests/unit/pricing/test_cross_provider_cost_validation.py \
  tests/unit/optimization/test_optimization_profiles.py \
  -q
```

Result: 49 passed.

```bash
cd 2-twin2clouds
/tmp/t2mc-phase12-py311/bin/python -m pytest \
  tests/unit/pricing \
  tests/unit/optimization \
  --ignore=tests/unit/pricing/test_pricing_schema.py \
  -q
```

Result: 175 passed, 1 warning. The ignored `test_pricing_schema.py` expects
the historical Docker path `/app/json/pricing.json` and fails during local
collection outside the container.

```bash
git diff --check
```

Result: clean.

## Review Findings Fixed In Plan

- Fixed: formula ownership is explicitly under `CalculationStrategy`.
- Fixed: provider contracts reference formula IDs but do not own formulas.
- Fixed: optimization profile is the compatibility boundary.
- Fixed: future metrics cannot emit fake values.
