# Intent To Result Traceability

## Metadata

- Phase: 16
- Status: planned
- Parent roadmap: `docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`
- Depends on: Phase 12, Phase 13, Phase 14, Phase 15
- Parent issues: #69, #32, #100
- Scope owner: `2-twin2clouds`
- No live cloud deployment E2E in this phase

## Goal

Expose an inspectable, secret-free trace from business intent to final cost
contribution. The trace must explain why each result value exists.

This phase supports developer diagnostics, audit review, pricing drift analysis,
and thesis explanation.

## Target Trace Flow

```text
Business intent
    -> workload input
    -> optimization profile
    -> calculation strategy
    -> formula set
    -> provider pricing contract
    -> pricing model classification
    -> price source classification
    -> selected evidence
    -> rejected alternatives
    -> normalization
    -> formula application
    -> result field
    -> cost contribution
```

## Trace Record Shape

Each trace item should include:

- `trace_id`
- `provider`
- `layer`
- `service`
- `intent_id`
- `workload_contract_id`
- `workload_inputs`
- `optimization_profile_id`
- `calculation_strategy_id`
- `formula_set_id`
- `formula_ref`
- `provider_pricing_contract_id`
- `pricing_model_classification_id`
- `price_source_classification_ids`
- `selected_evidence_id`
- `selected_evidence_summary`
- `rejected_alternative_ids`
- `normalization_steps`
- `result_field`
- `cost_contribution`
- `currency`
- `output_metric_unit`
- `publishability_status`
- `verification_gate`
- `verification_status`
- `verification_error_code`
- `verification_error_message`
- `source_build_path`
- `source_type`

## Implementation Steps

1. Add trace data structures in `backend/calculation_v2/` or a small
   `backend/traceability.py` module.
2. Extend calculation execution to emit trace items alongside result metadata.
3. Keep trace output secret-free and bounded.
4. Include selected evidence IDs and summaries, not raw credential-bearing
   provider payloads.
5. Include rejected alternative references where evidence reports already
   contain them.
6. Add read-only API output only if it follows the existing optimizer API
   response patterns without introducing write paths.
7. Update Management API run validation only if result trace metadata becomes
   part of persisted run summaries.

## Expected Touchpoints

- `2-twin2clouds/backend/calculation_v2/engine.py`
- `2-twin2clouds/backend/calculation_v2/components/`
- `2-twin2clouds/backend/pricing_evidence.py`
- `2-twin2clouds/backend/pricing_contract_validation.py`
- `2-twin2clouds/api/calculation.py`
- `2-twin2clouds/tests/unit/pricing/test_intent_to_result_traceability.py`
- `2-twin2clouds/tests/unit/calculation_v2/test_engine.py`
- `twin2multicloud_backend/tests/test_cost_calculation_runs.py`

## Data Ownership And Compatibility

- Trace output is calculation metadata, not registry SSOT.
- Trace may be persisted by the Management API only as part of calculation run
  summaries or result metadata.
- Trace output must be additive and must not break existing result consumers.
- Trace IDs should be deterministic for tests and thesis evidence.

## Security And Privacy

Trace output must never include:

- credentials
- credential file paths
- raw request headers
- raw provider auth errors containing secrets
- local absolute paths to credential files
- unbounded raw provider payloads

Trace output may include:

- sanitized SKU/meter/product identifiers
- sanitized request scope
- source URLs
- evidence IDs
- normalized units
- reviewed source metadata

## Non-Goals

- No editable trace UI.
- No pricing registry editor.
- No live deployment E2E.
- No automatic repair of failed traces.
- No full billing reconciliation.

## Test Plan

Add tests under:

- `2-twin2clouds/tests/unit/calculation_v2/`
- `2-twin2clouds/tests/unit/pricing/`

Required tests:

- AWS IoT Core result includes trace from intent to formula contribution
- Azure IoT Hub result includes pricing model and source classifications
- GCP Pub/Sub result includes workload inputs and formula ref
- AWS Managed Grafana trace includes selected evidence/source info
- Azure Managed Grafana trace includes selected evidence/source info
- one storage service trace includes normalization steps
- trace redacts credential-like values
- trace IDs are deterministic for snapshot comparison
- trace includes verification gate status for every contributing field
- failed verification gates are visible in non-publishable diagnostic traces
- trace remains bounded and does not dump raw provider payloads
- Management API run persistence remains compatible if trace is included

Recommended command:

```bash
cd 2-twin2clouds
python -m pytest \
  tests/unit/calculation_v2/test_engine.py \
  tests/unit/pricing/test_intent_to_result_traceability.py \
  -q
```

Optional Management API compatibility smoke:

```bash
cd twin2multicloud_backend
python -m pytest tests/test_cost_calculation_runs.py -q
```

## Definition Of Done

- [ ] Calculation results expose inspectable trace metadata.
- [ ] Trace connects intent, workload, classification, evidence, formula, and
      final contribution.
- [ ] Trace distinguishes provider API, official/static, curated, derived,
      not-applicable, unsupported, and fallback diagnostic source states.
- [ ] Trace includes field-level verification gate status.
- [ ] Trace is secret-free and bounded.
- [ ] Snapshot-style tests prove trace stability.
- [ ] Roadmap phase 16 is updated to implemented when the phase is complete.

## Review Gate

Before commit:

- [ ] Run the phase-specific pytest command.
- [ ] Run the optional Management API compatibility smoke if persistence is
      touched.
- [ ] Run `git diff --check`.
- [ ] Review trace output for secrets, local credential paths, and unbounded raw
      provider payloads.
- [ ] Review snapshot stability for representative AWS, Azure, and GCP traces.
- [ ] Update this plan with implementation notes and completed checkbox state.

## Review Findings Fixed In Plan

- Fixed: result values become explainable instead of opaque totals.
- Fixed: non-fetchable official/static sources are visible in trace output.
- Fixed: trace supports thesis evidence without requiring live E2E.
- Fixed: no secrets or raw credential material are exposed.
