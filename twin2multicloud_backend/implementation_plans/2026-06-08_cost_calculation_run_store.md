# Cost Calculation Run Store

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

Related epic: GitHub issue #69

Issue for this phase: TBD

## Goal

Persist optimizer calculation results as typed, Twin-scoped application data in
the existing Management API database.

The optimizer remains a calculation service. The Management API owns users,
twins, configuration state, calculation history, audit metadata, and deployment
handoff state.

## Problem

The current Management API stores the latest optimizer state in
`optimizer_configurations`:

- `params`
- `result_json`
- separate cheapest-path columns
- pricing snapshot JSON fields

This is useful as a compatibility bridge, but it is not a clean history model.
It cannot naturally answer:

- which calculation runs existed for a twin?
- which pricing/evidence version was used?
- which cost items contributed to the result?
- which run was selected for deployment?
- did the same input produce different costs after pricing drift?
- which evidence ids support each provider/layer/component cost?

## Decision

Use the existing Management API database. Do not add a separate optimizer
database.

Reason:

```text
Cost calculation runs belong to:
  - User ownership
  - DigitalTwin ownership
  - optimizer config/version
  - later deployment handoff
  - Management API authorization
```

A separate optimizer database would duplicate Twin/User context and create
synchronization problems. The optimizer should stay stateless from an
application-data perspective.

## Target Architecture

```text
Flutter Step 2
    |
    v
Management API
    |
    +--> loads Twin/User/config context
    +--> calls Optimizer /calculate
    +--> validates response contract
    +--> stores CostCalculationRun
    +--> stores CostCalculationResultItems
    +--> exposes latest/history endpoints
    |
    v
Existing Management DB
```

```text
Optimizer Service
    |
    +--> accepts typed calculation input
    +--> returns typed optimization result
    +--> does not persist Twin/User run history
    +--> does not own an app database
```

## Data Ownership

```text
pricing_registry/*.yaml
  = cost intents, mappings, normalization, service models

generated pricing evidence
  = observed provider rows, selected/rejected alternatives, fetch metadata

Management DB
  = calculation runs, result items, selected run, audit/status metadata

optimizer_configurations
  = current Step-2 compatibility state during migration
```

## Proposed Database Model

### `cost_calculation_runs`

Required fields:

```text
id
twin_id
user_id
optimizer_config_id
status
params_json
result_summary_json
cheapest_path_json
total_monthly_cost
currency
optimization_profile_id
optimization_profile_version
scoring_strategy_id
calculation_model_version
pricing_registry_version
pricing_evidence_version
pricing_run_reference
created_at
completed_at
selected_for_deployment_at
error_code
error_message
```

### `cost_calculation_result_items`

Required fields:

```text
id
run_id
layer
component
provider
service_intent_id
cost_amount
currency
unit
quantity
unit_price
evidence_id
service_model_id
calculation_notes_json
review_status
created_at
```

The exact SQLAlchemy field names may be adjusted to existing naming patterns,
but the information must be represented explicitly rather than buried only in
one large `result_json` blob.

## API Target

The Management API should expose calculation history through typed endpoints.

Proposed endpoints:

```text
POST /twins/{twin_id}/optimizer-runs
  Runs calculation through the optimizer and persists the result.

GET /twins/{twin_id}/optimizer-runs
  Lists calculation runs for the twin.

GET /twins/{twin_id}/optimizer-runs/{run_id}
  Returns one run with result items and evidence references.

POST /twins/{twin_id}/optimizer-runs/{run_id}/select-for-deployment
  Marks one successful run as the deployment handoff source.

GET /twins/{twin_id}/optimizer-config
  May continue returning latest current-state data for compatibility.
```

Endpoint names may be adjusted to match current route conventions, but the
contract must make run history first-class.

## Migration Strategy

This phase must be backward-compatible.

Required migration behavior:

1. Add explicit tables through an idempotent migration.
2. Keep `optimizer_configurations.result_json` readable.
3. Keep existing Flutter Step-2 behavior working.
4. When a new run is created, update the compatibility current-state fields
   from the canonical run in the same transaction.
5. Deployer handoff may continue reading the cheapest path compatibility fields
   until a later phase moves it to `calculation_run_id`.

No destructive migration of existing `result_json` data is part of this phase.

## Scope

This phase is Management API persistence and API contract work.

It must not:

- create a separate optimizer database
- rewrite provider pricing fetchers
- rewrite cost calculation formulas
- introduce non-cost optimization metrics
- build Flutter history UI
- run real cloud deployment E2E tests
- make DB records the SSOT for pricing mappings or intents

## Implementation Steps

1. Add SQLAlchemy models for calculation runs and result items.
2. Add Pydantic schemas for run create/list/detail/select responses.
3. Add an idempotent DB migration.
4. Add a service layer that:
   - validates twin ownership through existing helpers
   - calls the optimizer client
   - validates optimizer response shape
   - validates that the optimizer response includes an executable
     `optimization_profile_id`
   - stores the run and result items transactionally
   - updates `optimizer_configurations` compatibility fields
5. Add route endpoints for create/list/detail/select.
6. Add structured error handling for optimizer validation errors, optimizer
   unavailability, persistence errors, and unauthorized twin access.
7. Add tests for model persistence, API ownership, transaction behavior,
   compatibility-field updates, and history listing.
8. Update the pricing/optimization roadmap with the final issue number.

## Error Handling

Required error behavior:

- Optimizer unavailable: return a structured 503 and store a failed run only if
  a run record was intentionally created before the call.
- Optimizer contract invalid: return structured 502/500 boundary error and do
  not mark the run successful.
- Missing or disabled optimization profile in optimizer response: return a
  structured contract error and do not mark the run successful.
- DB persistence failure: rollback both run records and compatibility updates.
- Unauthorized twin: return existing Management API auth/ownership error.
- Invalid run selection: return 409 or 422 when the run is failed, belongs to a
  different twin, or is not selectable.

Error messages must not include secrets or raw credential material.

## Test Strategy

No real cloud deployment E2E is required.

Required tests:

- migration creates `cost_calculation_runs`
- migration creates `cost_calculation_result_items`
- creating a run persists params, summary, cheapest path, and result items
- creating a run persists `optimization_profile_id`,
  `optimization_profile_version`, `scoring_strategy_id`, and
  `calculation_model_version`
- creating a run updates `optimizer_configurations` compatibility fields
- list endpoint returns only runs owned by the current user/twin
- detail endpoint returns evidence references when present
- failed optimizer call does not create a successful run
- invalid optimizer response is handled with a structured error
- missing, disabled, or unknown optimization profile metadata is rejected
- select-for-deployment rejects failed runs
- select-for-deployment records the selected run and preserves compatibility
  cheapest-path fields
- rollback test proves partial run/result writes do not survive DB failure

## Definition Of Done

- [ ] Existing Management DB is extended; no optimizer-owned app DB exists.
- [ ] Cost calculation runs are first-class typed records.
- [ ] Cost result items are queryable separately from the raw result JSON.
- [ ] Cost calculation runs persist the active optimization profile, scoring
  strategy, and calculation model metadata.
- [ ] Result items can store pricing/evidence references.
- [ ] Current `optimizer_configurations` behavior remains compatible.
- [ ] API endpoints support create/list/detail/select lifecycle.
- [ ] Deployer compatibility remains intact.
- [ ] Tests cover persistence, ownership, rollback, and structured errors.
- [ ] Documentation explains data ownership and migration path.

## Self Review

### Architect Review

- The plan keeps application state in the Management API, where User/Twin
  ownership already lives.
- The optimizer remains stateless and avoids a second app database.
- The compatibility bridge prevents a disruptive Flutter/deployer rewrite.
- The result-item model is future-ready for evidence ids without making pricing
  mappings DB-owned.
- The run model preserves the selected optimization profile so future audits can
  explain which metric/model/strategy bundle produced a result.

### Builder Review

- Tables, endpoints, service responsibilities, and error cases are explicit.
- The migration strategy is backward-compatible.
- Test expectations are concrete and do not require real cloud deployments.

### Review Findings

- Fixed: DB ownership is explicitly the existing Management DB, not a new
  optimizer DB.
- Fixed: pricing mappings/intents remain file-owned and are not moved into DB.
- Fixed: current `optimizer_configurations.result_json` is treated as a
  compatibility bridge, not immediately deleted.
- Fixed: deployment handoff migration is deferred to avoid broad side effects.
- Fixed: structured error handling and rollback tests are mandatory.
- Fixed: run history now persists `optimization_profile_id` and related strategy
  metadata instead of only a loose scoring strategy string.

No open findings after review.
