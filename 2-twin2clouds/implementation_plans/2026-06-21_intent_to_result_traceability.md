# Intent-To-Result Traceability

## Metadata

- GitHub issue: #100
- Service: `2-twin2clouds`
- Status: Complete
- Date: 2026-06-21

## Goal

Expose bounded, secret-free trace metadata alongside Optimizer calculation
results so developers, the Management API, Flutter diagnostics, and thesis
evidence can inspect how a final cost result was produced.

The trace must connect:

- optimization profile,
- workload/derived input,
- pricing intent and contract field,
- source policy/classification,
- evidence reference,
- formula binding,
- selected provider/layer contribution,
- verification gate status.

## Scope

In scope:

- Add typed trace construction in the calculation layer.
- Return trace metadata additively from `/calculate`.
- Preserve existing legacy response fields and consumers.
- Add unit/integration tests for stable trace shape.
- Keep trace read-only and secret-free.

Out of scope:

- Flutter UI rendering.
- Management API persistence changes.
- Pricing registry editor or reviewed-decision write flow.
- Live cloud E2E.
- Full billing reconciliation.
- Runtime LLM/AI matching.

## Target Response Shape

`calculate_cheapest_costs()` returns the existing result plus:

```json
{
  "trace_schema_version": "intent-result-trace.v1",
  "intentTrace": {
    "schema_version": "intent-result-trace.v1",
    "profile": {},
    "workload": {},
    "selected_path": [],
    "records": [],
    "summary": {}
  }
}
```

Each trace record represents one selected pricing intent field used or governed
by the selected provider/layer path:

```json
{
  "trace_id": "trace:aws.l1.iot_core.message_tiers",
  "intent_id": "aws.l1.iot_core",
  "provider": "aws",
  "layer": "L1_INGESTION",
  "service_key": "iotCore",
  "field_id": "message_tiers",
  "source": {
    "primary_source_type": "dynamic_provider_api",
    "refreshability": "refreshable",
    "failure_behavior": "reject_field",
    "evidence": "required"
  },
  "pricing": {
    "key_path": ["aws", "iotCore", "pricing_tiers"],
    "aliases": [],
    "canonical_unit": "usd/message",
    "source_unit": "tier_table",
    "quantity_basis": "billable_messages",
    "normalizer": "aws_iot_core_tier_table"
  },
  "formula": {
    "binding_id": "...",
    "formula_type": "CM",
    "calculation_entrypoint": "...",
    "result_component": "...",
    "required_usage_inputs": []
  },
  "contribution": {
    "selected": true,
    "path_key": "L1_AWS",
    "cost": 1.23,
    "component_keys": []
  },
  "verification": {
    "status": "ready",
    "review_required": false,
    "publishable": true,
    "evidence_reference_id": "pricing_registry:2026.06.08/aws.l1.iot_core.message_tiers"
  }
}
```

## Implementation Steps

1. Add `backend/calculation_v2/traceability.py`.
   - Build records from `cost_strategy_contract()` and
     `pricing_source_inventory_by_id()`.
   - Map selected calculation path back to provider/layer keys.
   - Bind records to formula bindings by intent id.
   - Include a bounded workload summary from derived params.
   - Do not include raw credentials, raw provider API rows, or full pricing
     payloads.

2. Integrate trace construction in `calculate_cheapest_costs()`.
   - Add `trace_schema_version`.
   - Add `intentTrace`.
   - Preserve existing keys unchanged.

3. Add tests.
   - Unit test stable trace schema and record fields.
   - Unit test selected records correspond to selected path.
   - Unit test trace is bounded and does not contain raw pricing keys that look
     like credentials/secrets.
   - Integration test `/calculate` includes additive trace metadata.

4. Review and fix.
   - Run targeted trace tests.
   - Run full Optimizer suite in Docker.
   - Run `git diff --check`.
   - Review response shape against this plan and #100 acceptance criteria.

## Acceptance Criteria

- [x] `/calculate` exposes additive `intentTrace` metadata without removing legacy
  fields.
- [x] Trace records connect intent, source policy, formula binding, selected
  contribution, evidence reference, and verification state.
- [x] Trace contains bounded workload values, not raw pricing payloads or secrets.
- [x] Snapshot-style tests prove stable shape.
- [x] Full Optimizer test suite passes.
- [x] Roadmap and issue #100 can be updated with evidence.

## Implementation Evidence

Completed on 2026-06-21.

Implemented:

- `backend/calculation_v2/traceability.py` builds bounded
  `intent-result-trace.v1` metadata.
- `calculate_cheapest_costs()` returns additive `trace_schema_version` and
  `intentTrace` fields.
- Trace records cover the selected calculation path and connect source policy,
  pricing units, formula binding, contribution, and registry evidence
  references.
- Transfer costs are represented as segment-level `transfer_trace` entries with
  source-provider transfer intent references.
- `/calculate` exposes the trace through the existing response envelope without
  removing legacy result fields.

Verification:

- Targeted trace/API/engine gate: `17 passed, 1 warning`.
- Full Optimizer suite: `379 passed, 1 warning`.

## Verification

```bash
docker run --rm \
  -v "$PWD/2-twin2clouds:/app" \
  -v "$PWD/config.json:/config/config.json:ro" \
  -w /app \
  -e PYTHONPATH=/app \
  2twin2clouds:latest \
  python -m pytest \
    tests/unit/calculation_v2/test_intent_to_result_traceability.py \
    tests/unit/calculation_v2/test_engine.py \
    tests/integration/test_rest_api_calculation_edge_cases.py \
    -q
```

```bash
tmpdir=$(mktemp -d /tmp/optimizer-test-config.XXXXXX)
printf '{"aws":{}}\n' > "$tmpdir/config_credentials.json"
docker run --rm \
  -v "$PWD/2-twin2clouds:/app" \
  -v "$PWD/config.json:/config/config.json:ro" \
  -v "$tmpdir/config_credentials.json":/config/config_credentials.json:ro \
  -w /app \
  -e PYTHONPATH=/app \
  2twin2clouds:latest \
  python -m pytest tests -q
```
