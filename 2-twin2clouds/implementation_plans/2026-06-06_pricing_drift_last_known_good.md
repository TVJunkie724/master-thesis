# Pricing Drift Detection and Last-Known-Good Publishing

## Issue

GitHub: #83

## Goal

Introduce a deterministic pricing publication contract so provider catalog refreshes
can complete without automatically replacing reviewed calculation pricing. Fresh
provider evidence may be published only when all intent matches are safe. Drift,
missing mappings, ambiguous matches, and failed refreshes must produce structured
review-required state and preserve the last-known-good calculation snapshot.

## Final State

- Pricing refresh has two separate outputs:
  - fresh provider evidence and match results
  - a publication decision for calculation consumers
- Publication decisions are provider-scoped, schema-versioned, and stable enough
  for Management API and Flutter to expose in the next slice.
- `matched` intent results may publish a fresh calculation snapshot.
- `ambiguous`, `missing`, `changed`, `failed`, and `fallback_static` require
  review before publishing.
- When review is required, calculations use last-known-good pricing if available.
- If no last-known-good pricing exists, the decision is explicit that calculation
  pricing is unavailable for that provider.

## Non-Goals

- No live cloud E2E.
- No review UI.
- No full curated provider mapping registry; that remains #32.
- No rewrite of the existing provider price fetchers in this slice.

## Implementation Steps

1. Add a small `pricing_publication_state` backend module.
2. Define typed publication states, calculation source values, and a
   schema-versioned decision payload.
3. Summarize matcher outcomes by status and by intent.
4. Select fresh pricing only when all match results are publishable.
5. Select last-known-good pricing when drift/review is required.
6. Add unit tests for successful publish, drift, missing mapping, ambiguous
   candidates, failed refresh, fallback-static, stale last-known-good metadata,
   and no last-known-good availability.

## Verification

- `PYTHONPATH=/app pytest tests/unit/pricing/test_pricing_publication_state.py -q`
- `PYTHONPATH=/app pytest tests/unit/pricing -q`
