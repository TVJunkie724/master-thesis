# Phase 7: Wizard Step 2 Optimizer Cleanup

**Status:** planned
**Primary owner:** Flutter Wizard
**Depends on:** Phase 4 and Phase 6

## Goal

Remove pricing maintenance from Wizard Step 2. Step 2 should focus on workload
parameters and cost calculation.

## Target Layout

```text
Wizard Step 2: Optimizer
|-- Pricing Readiness Summary
|   |-- AWS stale
|   |-- Azure fresh
|   |-- GCP review required
|   `-- Pricing data is managed from the Dashboard.
|
|-- Workload / Calculation Form
|-- Calculate
|-- Cost Results
```

## Required Removals

- Remove provider refresh cards from Step 2.
- Remove pricing refresh SSE log window from Step 2.
- Remove direct refresh confirmation dialog from Step 2.
- Keep only compact read-only readiness.

## Widget Tree

```text
Step2Optimizer [MODIFY]
|-- PricingReadinessSummary [NEW]
|-- CalcForm [EXISTING]
|-- CalculationActions [EXISTING]
`-- OptimizerResults [EXISTING]
```

## Behavior

- Step 2 calls Management API for pricing readiness only.
- If pricing state is `review_required` or `missing`, calculation is blocked
  unless backend explicitly permits last-known-good/stale calculation.
- The UI text says: `Pricing data is managed from the Dashboard.`
- No button/link to Pricing Review is shown in Step 2.

## Verification

- Widget tests prove refresh buttons/logs are gone.
- Widget tests cover fresh/stale/review-required/missing readiness.
- Calculation blocking/warning is tested against typed readiness state.

## Definition Of Done

- [ ] Step 2 has no pricing refresh controls.
- [ ] Step 2 has compact readiness summary only.
- [ ] Step 2 does not navigate to Pricing Review.
- [ ] Calculation gating follows backend readiness.
- [ ] Tests updated and old refresh expectations removed.
