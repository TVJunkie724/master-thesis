# Implementation Plan: Pricing Intent Registry Matcher

Issue: #82
Branch: `codex/pricing-catalog-reliability`
Base branch: `master`

## Goal

Add a versioned pricing intent registry contract and deterministic matcher for
the canonical candidates introduced in #81.

## Scope

### Registry Contract

- Define stable pricing intent IDs used by the optimizer cost model.
- Define provider mapping entries with:
  - schema and mapping version,
  - intent ID,
  - provider,
  - review status,
  - stable provider identifier filters,
  - expected unit, price type, region, and tier constraints,
  - optional normalization metadata.

### Matcher

- Match canonical candidates against one provider mapping.
- Return typed outcomes:
  - `matched`
  - `missing`
  - `ambiguous`
  - `changed`
  - `failed`
- Refuse to choose silently when more than one candidate matches.
- Sort candidate evidence deterministically so row order does not affect results.
- Preserve selected/rejected candidate evidence for review and drift detection.

### Tests

- Single match.
- Missing match.
- Ambiguous match.
- Changed unit / changed provider identifiers.
- Deterministic output independent of candidate order.

## Non-Goals

- No complete curated production mapping file yet. The provider catalog evidence
  is still being introduced and will feed the full curated mappings in #32.
- No publishing or last-known-good state; that is #83.
- No Flutter review UI; that is #84.
- No LLM runtime matching.

## Acceptance Criteria

- [ ] Pricing intent IDs are explicit and centrally defined.
- [ ] Mapping entries are versioned and validated before matching.
- [ ] Matcher emits `matched`, `missing`, `ambiguous`, `changed`, and `failed`.
- [ ] Ambiguous candidates are preserved and not silently collapsed.
- [ ] Tests prove deterministic row-order-independent behavior.

## Verification

```bash
docker-compose run 2twin2clouds sh -lc \
  'cd /app && PYTHONPATH=/app pytest tests/unit/pricing/test_pricing_intent_registry.py -q'
```
