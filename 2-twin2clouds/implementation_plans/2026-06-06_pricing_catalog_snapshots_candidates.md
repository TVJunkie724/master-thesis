# Implementation Plan: Pricing Catalog Snapshots and Candidates

Issue: #81
Branch: `codex/pricing-catalog-reliability`
Base branch: `master`

## Goal

Introduce a provider-neutral catalog snapshot and candidate extraction contract.
Provider pricing data must become inspectable before future matching/publishing
logic decides which price is allowed into optimizer calculations.

## Scope

### Candidate Contract

- Add a canonical candidate schema for AWS, Azure, and GCP catalog rows.
- Preserve provider identifiers where available:
  - AWS SKU, product family, service code, usage type, operation, rate code.
  - Azure meter/product/SKU IDs and meter/product/SKU names.
  - GCP service ID, SKU ID, SKU description, category, usage units.
- Include region, unit, price mode/type, tier/quantity range, currency, raw
  price, fetch timestamp, and sanitized raw payload reference.

### Snapshot Contract

- Add a snapshot object containing provider, schema version, source API,
  request scope, fetched timestamp, candidate count, and candidates.
- Keep snapshots secrets-free by only accepting provider catalog rows, never
  credential payloads.
- Provide a writer helper for future refresh integration, but do not wire it
  into publishing yet.

### Tests

- Add deterministic unit tests with mocked AWS, Azure, and GCP catalog payloads.
- Prove ambiguous-looking rows are preserved as separate candidates rather than
  collapsed by string matching.

## Non-Goals

- No mapping registry.
- No drift detection.
- No calculation snapshot publishing changes.
- No Flutter review UI.
- No live cloud calls.

## Acceptance Criteria

- [ ] AWS, Azure, and GCP raw catalog rows can be converted to canonical
  candidates.
- [ ] Stable provider identifiers and raw evidence are preserved.
- [ ] Snapshot helper returns metadata plus candidates without touching pricing
  calculation files.
- [ ] Tests cover provider-specific extraction and ambiguous rows.

## Verification

```bash
docker-compose run 2twin2clouds sh -lc \
  'cd /app && PYTHONPATH=/app pytest tests/unit/pricing/test_pricing_catalog_candidates.py -q'
```
