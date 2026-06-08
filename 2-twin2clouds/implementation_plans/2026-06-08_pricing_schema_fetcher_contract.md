# Pricing Schema and Fetcher Contract Hardening

## Issue

GitHub: #32

## Goal

Make the optimizer pricing output auditable and testable while preserving the
existing calculation payload shape. Provider fetchers must produce a complete
versioned pricing contract for AWS, Azure, and GCP, with explicit quality
metadata for fetched, derived, curated, fallback, and unsupported values.

Fallback is not the target state. It is an emergency escape hatch so the system
does not crash while drift is being investigated. Any fallback value must be
visible as review-required and must not be treated as publishable fresh pricing.

## Scope

- Add a single source of truth for the provider pricing schema.
- Move schema validation out of hardcoded `pricing_utils` duplication.
- Enrich generated provider pricing files with reserved metadata fields:
  - `__schema__`
  - `__quality__`
- Mark static/default fallback values as `review_required`, not as successful
  provider evidence.
- Keep calculation compatibility by stripping reserved metadata when building
  combined pricing for calculations.
- Update `json/pricing.json` so the template documents the full AWS/Azure/GCP
  expanded service model.
- Add broad tests that generate all provider payloads from mocked fetchers and
  validate them against the schema.

## Non-Goals

- No live cloud E2E.
- No final provider-specific least-privilege validation.
- No complete replacement of provider keyword fetchers in this slice.
- No runtime LLM matching.

## Final State

- `backend.pricing_schema` owns:
  - schema version
  - expected provider services and fields
  - validation
  - reserved metadata stripping
  - quality metadata generation
- `backend.pricing_utils.validate_pricing_schema` delegates to the schema module.
- Fetcher outputs remain backward-compatible for calculation code.
- Consumers can inspect quality metadata to see fetched, derived, curated,
  fallback, and unsupported fields.
- Fallback fields are explicit blockers for publishing fresh pricing and feed
  the review-state contract instead of silently passing as normal data.
- Missing schema fields fail deterministic tests before they reach deployment or
  thesis demos.

## Verification

- `PYTHONPATH=/app pytest tests/unit/pricing/test_pricing_contract.py -q`
- `PYTHONPATH=/app pytest tests/unit/pricing tests/unit/test_pricing_streaming.py -q`
