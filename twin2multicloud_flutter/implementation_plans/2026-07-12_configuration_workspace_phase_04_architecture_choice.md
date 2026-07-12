# Configuration Workspace Phase 4: Architecture Choice

## Objective

Turn the former mixed optimizer screen into three focused tasks: pricing
readiness, calculation, and recommendation review. Preserve the optimizer result
and trace contracts as the architecture decision record.

## Behavior

- Pricing readiness renders provider health only and points to the Dashboard
  Pricing Review location without adding refresh controls.
- Calculate alternatives renders a compact workload summary and the existing
  explicit Calculate command. It never repeats the 26-field form.
- Compare and select renders the optimizer recommendation, provider/layer cost
  evidence, warnings, and calculation trace. Continuing accepts the persisted
  optimizer result as the selected architecture.
- Recalculation preserves existing invalidation confirmation and downstream
  recovery behavior.
- Missing/stale pricing fails closed according to the existing contract.

## Contract Boundary

- `CalcResult` remains the selected architecture record.
- No client-side optimization or alternative mutation is introduced.
- If future backend contracts expose selectable non-optimal alternatives, they
  extend the task through a typed selection command rather than replacing the
  journey.

## Verification

- Each task renders only its owned information.
- Calculate stays disabled for incomplete inputs or failed pricing readiness.
- Successful calculation enables recommendation review and Cloud Access.
- Recalculation with changed provider path invalidates deployment preparation.
- Saved results restore directly into recommendation review.
- Full Flutter tests and analyzer pass.

