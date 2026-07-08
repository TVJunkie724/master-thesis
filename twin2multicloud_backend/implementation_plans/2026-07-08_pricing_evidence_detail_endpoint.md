# Pricing Evidence Detail Endpoint

## Metadata

- Branch: `codex/pricing-evidence-detail-endpoint`
- Base: `master`
- GitHub issue: #100
- Status: complete

## Goal

Expose persisted optimizer intent-to-result trace evidence through the
Management API so Flutter can show collapsed pricing/evidence diagnostics
without parsing logs or calling the Optimizer directly.

## Scope

In scope:

- Add a read-only Management API endpoint for one persisted optimizer run:
  `GET /twins/{twin_id}/optimizer-runs/{run_id}/pricing-evidence`.
- Reuse existing `CostCalculationRun` ownership checks.
- Return stored `intentTrace` data, transfer trace data, selected path,
  result-item evidence references, and bounded result metadata.
- Handle older runs without `intentTrace` gracefully.
- Redact secret-looking values before returning evidence details.
- Add route/service tests for happy path, missing trace, redaction, and
  ownership scoping.

Out of scope:

- No new Optimizer calculation behavior.
- No Flutter UI changes in this slice.
- No pricing candidate review write workflow.
- No real cloud E2E.
- No database migration.

## API Contract

```text
GET /twins/{twin_id}/optimizer-runs/{run_id}/pricing-evidence
```

Response:

```json
{
  "run_id": "uuid",
  "twin_id": "uuid",
  "trace_schema_version": "intent-result-trace.v1",
  "trace_available": true,
  "profile": {},
  "workload": {},
  "selected_path": [],
  "records": [],
  "transfer_trace": [],
  "summary": {},
  "result_metadata": {},
  "result_items": [],
  "warnings": []
}
```

Rules:

- `result_items` reuses the existing typed result-item response shape.
- `records` and `transfer_trace` are intentionally schema-flexible dictionaries
  because the Optimizer owns the trace record schema version.
- Missing trace returns `trace_available=false`, empty trace arrays, and a
  warning instead of a 500.
- Unknown run/twin/user boundaries return 404 through the existing scoped
  `get_run` behavior.
- The endpoint never returns credential values, tokens, private keys, or raw
  downstream error bodies.

## Implementation Steps

1. Add `PricingEvidenceDetailResponse` schema.
2. Add service method on `CostCalculationRunService` that:
   - loads the scoped run,
   - extracts `intentTrace` from `result_summary_json`,
   - builds bounded metadata from known result fields,
   - redacts secret-looking payload values,
   - returns trace arrays and warnings.
3. Add route endpoint under `optimizer_runs.py`.
4. Add tests to `tests/test_cost_calculation_runs.py`:
   - detail endpoint returns trace and result item evidence,
   - missing trace is graceful,
   - secret-looking values are redacted,
   - foreign twin/run access remains 404.
5. Run targeted backend tests and full Management API test suite in Docker.
6. Review implementation against this plan, fix findings, update status, commit.

## Definition Of Done

- [x] Endpoint exists and is documented through FastAPI route metadata.
- [x] Endpoint is user/twin scoped.
- [x] Response is typed at the Management API boundary.
- [x] Missing trace is non-crashing and explicit.
- [x] Secret-looking values are redacted recursively.
- [x] Tests cover happy path, missing trace, redaction, and scoping.
- [x] `pytest tests/test_cost_calculation_runs.py -q` passes.
- [x] Full Management API tests pass.

## Verification Evidence

- Targeted Docker test:
  `docker compose run --rm --no-deps -e PYTHONPATH=/app management-api python -m pytest tests/test_cost_calculation_runs.py -q`
  - Result: `16 passed, 1 warning`
- Full Management API Docker suite:
  `docker compose run --rm --no-deps -e PYTHONPATH=/app management-api python -m pytest tests/ -q`
  - Result: `516 passed, 1 warning`
- `git diff --check` passed.
