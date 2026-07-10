---
title: "Phase 2.5 Review: Optimizer API Contract"
description: "Review of Optimizer API contract hardening for pricing source inventory, review state, and Management API handoff."
tags: [optimizer, api, contracts, pricing, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/subphases/PHASE_02_05_OPTIMIZER_API_CONTRACT_AUDIT.md
- 2-twin2clouds/api/pricing.py
- 2-twin2clouds/backend/calculation_v2/pricing_source_inventory.py
- 2-twin2clouds/tests/integration/test_pricing_source_inventory_api.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 2.5 Review: Optimizer API Contract

## Review Result

Phase 2.5 is complete for the Pricing Review handoff contract. The Optimizer now
exposes `GET /pricing/source_inventory` with a typed response model. Management
API and Flutter can use this endpoint to display pricing source governance,
review-required fields, unsupported fields, emergency fallback state, units, and
normalizers without guessing the internal JSON shape.

Legacy refresh endpoints remain backward compatible and still return provider
pricing dictionaries.

## Endpoint Matrix

| Endpoint | Status | Contract notes |
|---|---|---|
| `PUT /calculate` | Existing | Keeps legacy response shape. Calculation evidence exposure remains a later response-versioning task. |
| `POST /fetch_pricing/{provider}` | Existing | Keeps legacy provider pricing dict for compatibility. Source/evidence state is not mixed into this endpoint. |
| `POST /stream/fetch_pricing/{provider}` | Existing | Keeps SSE log stream. Review-state event enrichment remains future UI work. |
| `GET /pricing/export/{provider}` | Existing | Keeps snapshot export. |
| `GET /pricing/source_inventory` | Added | Typed source inventory contract with schema version, objective, optional provider filter, summary, and source records. |
| `GET /pricing_age/{provider}` | Existing | Keeps age/status response. |

## New Contract

`PricingSourceInventoryResponse` contains:

- `schema_version`: currently `pricing-source-inventory.v1`,
- `objective`: currently `cost`,
- `provider`: optional provider filter,
- `summary`: total, ready, review-required, unsupported, and failed counts,
- `records`: one typed record per pricing source field.

Each record contains:

- field identity: record id, intent id, provider, layer, service key, field id,
- source location: key path and aliases,
- units: canonical unit, source unit, quantity basis, normalizer,
- governance: primary source type, refreshability, failure behavior, evidence,
  review state,
- emergency fallback visibility.

## Review-State Mapping

| Failure behavior | API review state |
|---|---|
| `reject_field` | `ready` |
| `require_review` | `review_required` |
| `use_reviewed_decision` | `ready` |
| `derive_from_usage_model` | `ready` |
| `mark_unsupported` | `unsupported` |

## Tests Added

`2-twin2clouds/tests/integration/test_pricing_source_inventory_api.py`
verifies:

- Response schema version, objective, summary, and records.
- Provider filtering.
- Unknown provider validation.
- OpenAPI declaration for the new endpoint.

Latest focused evidence:

```text
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests/integration/test_pricing_source_inventory_api.py -q

4 passed in 0.36s
```

Latest full-suite evidence with non-sensitive test config mounts:

```text
tmpdir=$(mktemp -d /tmp/optimizer-test-config.XXXXXX)
printf '{"aws":{}}\n' > "$tmpdir/config_credentials.json"
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -v "$tmpdir/config_credentials.json":/config/config_credentials.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests -q

226 passed in 50.71s
```

## Findings Handed To Later Work

| Finding | Owner phase |
|---|---|
| `PUT /calculate` still returns legacy calculation output without selected pricing evidence. A versioned calculation response should be added when the Management API and Flutter screens are ready to consume it. | Frontend UI Delta roadmap and future Optimizer calculation response issue |
| Refresh endpoints still write legacy pricing JSON. The source inventory now lets UI/API report review-required state separately without breaking existing clients. | Pricing Review UI/API integration |
| SSE refresh streams do not yet emit structured candidate/evidence events. | Future Pricing Review streaming issue |

## Acceptance Review

| Criterion | Result |
|---|---|
| Management API can proxy Optimizer pricing source responses without guessing payload shape. | Passed for `/pricing/source_inventory` |
| User-safe errors avoid credential or provider-internal leakage. | Passed for new endpoint; it exposes only invalid provider and generic internal errors |
| Pricing refresh states distinguish success, review-required, failed, and unsupported states. | Passed through source inventory review state; legacy refresh endpoints remain compatible |
| No live cloud deployment tests are required. | Passed |

## Residual Risk

The source inventory endpoint is the safe contract for Pricing Review readiness.
It does not yet replace the legacy pricing refresh dict endpoints or provide a
versioned calculation-evidence response. Those changes require Management API
and Flutter consumer work to avoid breaking the current application flow.
