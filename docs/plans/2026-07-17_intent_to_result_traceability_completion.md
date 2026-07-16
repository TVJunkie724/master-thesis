---
title: "Intent-To-Result Traceability Completion"
description: "Completion contract for honest, bounded pricing calculation traceability across Optimizer, Management API, and Flutter."
tags: [pricing, optimizer, traceability, management-api, flutter, thesis]
lastUpdated: "2026-07-17"
version: "1.0"
---

# Intent-To-Result Traceability Completion

**Issue:** [#100 Expose intent-to-result pricing traceability](https://github.com/TVJunkie724/master-thesis/issues/100)
**Base branch:** `master`
**Feature branch:** `codex/pricing-traceability`
**Status:** Approved for implementation
**Live-cloud E2E:** Explicitly deferred

## Objective

Make every persisted cost calculation inspectable from workload and strategy to
pricing contracts, source classification, evidence references, formula binding,
selection state, and result contribution. The trace must remain bounded, read-only,
secret-free, and honest about the precision of its contribution values.

## Current Findings

The repository already emits two additive structures:

- `intentTrace` is a compact envelope for profile, workload, selected path, transfer
  segments, selected intent records, and summary counters.
- `resultTrace` contains the richer provider pricing contracts, model/source
  classifications, evidence references, normalization, formulas, and verification
  gates for all provider fields.

They are not currently given explicit separate roles. Management API persists both
inside the result JSON but exposes only `intentTrace`; Flutter parses only
`intentTrace`. `resultTrace.cost_contribution` can repeat an entire layer total across
multiple field records, which must not be presented as an additive field amount.

## Final Ownership And Data Flow

```text
Pricing registry + calculation strategy + runtime result
                         |
                         v
Optimizer calculation
  |-- intentTrace   compact path/summary envelope
  `-- resultTrace   field-level audit records
                         |
                         v
Management API run persistence (immutable result snapshot)
                         |
                         v
GET /twins/{twin_id}/optimizer-runs/{run_id}/pricing-evidence
  |-- compact trace
  `-- field trace records + versions + compatibility warning
                         |
                         v
Flutter calculation result
  |-- concise status and counts by default
  `-- collapsed, read-only audit details on demand
```

The Optimizer owns trace construction. Management owns user-scoped persistence and
redacted read access. Flutter owns presentation only.

## Trace Roles

### Compact Intent Trace

`intentTrace` remains `intent-result-trace.v1` for compatibility. It answers:

- which profile and workload were used;
- which provider path was selected;
- which transfers contributed;
- whether selected records are publishable or require review.

### Field Audit Trace

`resultTrace` remains additive and versioned as `intent-to-result-trace.v1`. It answers:

- which provider pricing contract and classifications govern a field;
- which evidence references and normalized units apply;
- which formula and workload inputs are bound;
- whether the provider/layer was selected, alternative, or unsupported;
- what result scope the displayed amount represents;
- which verification gates passed or failed.

The two structures must not duplicate authority: compact path state comes from
`intentTrace`; field contract detail comes from `resultTrace`.

## Honest Contribution Contract

Every field audit record adds:

| Field | Meaning |
|---|---|
| `selection_status` | `selected`, `alternative`, `unsupported`, or `not_applicable` |
| `selected_for_path` | true only when this provider owns the selected result layer |
| `alternative_record_ids` | same semantic field on providers not selected for that layer |
| `rejected_evidence_ids` | actual rejected fetch/review evidence only; empty when unavailable |
| `cost_contribution` | bounded result amount already emitted for compatibility |
| `cost_contribution_scope` | `component_total`, `layer_total_shared`, `transfer_total_shared`, or `none` |
| `cost_contribution_is_additive` | false unless the amount is proven to be an exclusive formula contribution |
| `result_component_key` | concrete result component when one can be resolved |
| `runtime_selected_evidence_available` | whether calculation input carries exact selected-row evidence |
| `evidence_reference_kind` | distinguishes registry references from runtime selected-row evidence |

Current calculators generally expose service/component or layer totals, not exclusive
per-pricing-field amounts. Therefore repeated field records must explicitly use shared,
non-additive scope. The UI and docs must never invite summing them.

## Compatibility

- New Optimizer results continue to expose both existing top-level keys additively.
- Historical runs with only `intentTrace` return compact trace plus an explicit warning
  and an empty field trace list.
- Historical `resultTrace` records remain readable because new fields are additive.
- Flutter accepts absent field trace data and never blocks calculation rendering.
- No database migration is required because the immutable result JSON already stores
  the Optimizer payload.

## Implementation Slices

### Slice 1: Optimizer Trace Semantics

1. Derive selected provider/layer state from the canonical calculation result.
2. Mark unsupported rows from canonical `LayerResult.supported` metadata.
3. Add honest contribution scope and additivity metadata.
4. Populate deterministic cross-provider alternative record IDs by semantic field.
5. Include rejected evidence IDs only when the calculation input references an actual
   fetch/review evidence report; never relabel provider alternatives as rejected rows.
6. Distinguish registry evidence references from unavailable runtime row evidence.
7. Keep all strings bounded and apply the existing secret sanitizer.

### Slice 2: Management API Read Contract

1. Extend the evidence response with `field_trace_schema_version`,
   `field_trace_available`, and `field_trace_records`.
2. Preserve compact trace fields and historical-run behavior.
3. Apply recursive redaction to both structures and all metadata.
4. Keep user/twin scoping and immutable persistence unchanged.
5. Add route/service tests for current, historical, malformed-safe, and secret-bearing
   payloads.

### Slice 3: Flutter Read-Only Diagnostics

1. Parse field trace version and records as immutable typed read models.
2. Keep the existing summary compact.
3. Add a nested collapsed detail grouped by selected path/provider/layer.
4. Show intent, service, source type, formula, normalized unit, evidence reference,
   verification, and contribution scope without raw provider rows.
5. Label shared amounts as non-additive and show alternatives without preselecting them.
6. Cover empty/historical, selected, alternative, unsupported, review-required,
   constrained-width, and dark/light presentation states.

### Slice 4: Documentation And Handoff

1. Document trace ownership, schemas, data flow, and precision boundary.
2. Update Optimizer, Management API, Flutter, contracts, roadmap, and thesis evidence.
3. Update both older Phase 16 plans to point to this completion contract.
4. Close #100 only after all non-E2E gates pass.

## Verification Gates

### Optimizer

- deterministic 48-record contract for the current 3-provider registry;
- selected/alternative/unsupported status across every provider-layer row;
- deterministic alternative IDs;
- component/shared contribution scopes cannot claim false additivity;
- all seven verification gates remain visible;
- trace remains below the existing bound and secret/path redaction passes;
- currency conversion updates amounts but not source-currency evidence.

### Management API

- current run exposes compact and field traces;
- historical compact-only run remains readable with one explicit warning;
- owner/twin scoping remains enforced;
- recursive redaction covers both trace structures;
- full run persistence remains unchanged and transactional.

### Flutter

- analyzer and complete test suite pass;
- typed parser handles additive fields and missing historical field trace;
- summary remains compact before expansion;
- selected, alternative, unsupported, and review states are distinguishable;
- shared amounts are labelled non-additive;
- no overflow at constrained desktop/web width and no direct service call from widgets.

### Repository

- touched Python passes Ruff and Bandit;
- full Optimizer and Management API non-E2E suites pass;
- full Flutter analyzer/test gate passes;
- strict MkDocs build passes;
- `git diff --check` passes;
- no provider credential or billable cloud operation runs.

## Definition Of Done

- [ ] Trace roles and ownership are explicit and non-conflicting.
- [ ] Field records connect strategy, contracts, classifications, evidence, formulas,
  workload, verification, selection, and result scope.
- [ ] No field trace implies false additive precision.
- [ ] Management API exposes both trace levels for persisted runs.
- [ ] Flutter offers compact-by-default, read-only drill-down.
- [ ] Historical runs remain readable.
- [ ] Documentation and roadmap reflect the implemented state.
- [ ] All non-E2E verification gates pass.
