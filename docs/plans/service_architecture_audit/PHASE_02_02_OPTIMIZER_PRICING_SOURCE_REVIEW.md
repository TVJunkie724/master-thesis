---
title: "Phase 2.2 Review: Optimizer Pricing Source Inventory"
description: "Review of the pricing source inventory that classifies Optimizer pricing values by source, refreshability, evidence, and failure behavior."
tags: [optimizer, pricing, sources, evidence, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/subphases/PHASE_02_02_OPTIMIZER_PRICING_SOURCE_AUDIT.md
- 2-twin2clouds/backend/calculation_v2/strategy_contracts.py
- 2-twin2clouds/backend/calculation_v2/pricing_source_inventory.py
- 2-twin2clouds/backend/fetch_data/
- 2-twin2clouds/tests/unit/calculation_v2/test_pricing_source_inventory.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 2.2 Review: Optimizer Pricing Source Inventory

## Review Result

Phase 2.2 is complete. The Optimizer now has a flattened pricing source
inventory in `2-twin2clouds/backend/calculation_v2/pricing_source_inventory.py`.
It consumes the Phase-2.1 strategy contract and classifies every declared
pricing field by primary source, refreshability, failure behavior, evidence
requirement, emergency fallback source, units, normalizer, and JSON key path.

## Source Classification Model

| Source type | Meaning | Refreshability | Failure behavior |
|---|---|---|---|
| `dynamic_provider_api` | Value is expected from AWS, Azure, or GCP pricing APIs. | `refreshable` | Reject the field, or require review when the legacy code still has an emergency fallback. |
| `static_official_table` | Value is an official static pricing/free-tier/configuration table not available through the current provider API path. | `static_non_fetchable` | Require review before publishing refreshed pricing. |
| `reviewed_decision` | Value is selected and approved by a human reviewer in a future Management API review flow. | `reviewed_persisted` | Use the reviewed decision. |
| `derived_calculation` | Value is a workload model parameter rather than a provider price. | `derived_at_runtime` | Derive from the usage model. |
| `unsupported` | Value cannot currently be represented safely. | `unsupported` | Mark unsupported. |

## Fallback Policy

Fallback is explicitly modeled as an emergency source, not as the target state.
For currently known legacy fallback fields, the inventory exposes
`emergency_fallback_source_type=static_official_table` and
`emergency_fallback_allowed=false`.

This means:

- A fallback value can be shown for diagnostics.
- A fallback value must not be silently treated as a successful provider fetch.
- Fetcher and API hardening phases must surface these cases as review-required
  or unpublishable until approved.

## Provider Matrix

| Provider | Dynamic API examples | Static official examples | Derived examples | Review-required examples |
|---|---|---|---|---|
| AWS | IoT Core messages/rules, Lambda request/duration, DynamoDB read/write/storage, S3 storage/retrieval, TwinMaker queries, transfer egress | Lambda free tier, DynamoDB free storage, Grafana seat assumptions | None in current contract | IoT device-month fallback, S3 request fallback, Grafana static values |
| Azure | Functions request/duration, Blob storage, Event Grid, Digital Twins operation/message/query-unit meters, transfer tiers | Functions free tier, Grafana workspace/user assumptions | Cosmos DB RU-per-read and RU-per-write workload weights; Digital Twins billable quantities | IoT Hub tier table fallback |
| GCP | Pub/Sub GiB pricing, Cloud Functions request/duration, Firestore read/write/storage, Cloud Storage tiers, Compute Engine self-hosted VM/storage, transfer egress | Pub/Sub device-month zero value, Cloud Functions free tier | None in current contract | Self-hosted VM-hour fallback, GiB/GB normalization review |

## Tests Added

`2-twin2clouds/tests/unit/calculation_v2/test_pricing_source_inventory.py`
verifies:

- Every strategy-contract field has exactly one source record.
- Dynamic provider fields are refreshable and fail closed or require review.
- Static official fields are non-fetchable and review-required.
- Derived usage-model fields are not treated as provider prices.
- Current emergency fallbacks are visible but not publishable successes.
- Inventory records serialize into stable API/UI payloads.

Latest focused test evidence:

```text
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests/unit/calculation_v2/test_strategy_contracts.py tests/unit/calculation_v2/test_pricing_source_inventory.py -q

17 passed in 0.02s
```

Latest calculation/pricing evidence:

```text
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests/unit/calculation_v2 tests/unit/pricing -q

97 passed in 0.28s
```

Latest full-suite evidence with non-sensitive test config mounts:

```text
tmpdir=$(mktemp -d /tmp/optimizer-test-config.XXXXXX)
printf '{"aws":{}}\n' > "$tmpdir/config_credentials.json"
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -v "$tmpdir/config_credentials.json":/config/config_credentials.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests -q

210 passed in 50.78s
```

## Findings Handed To Later Subphases

| Finding | Owner phase |
|---|---|
| Fetchers still return plain pricing dictionaries and do not emit selected/rejected candidate evidence. | Phase 2.3 |
| `_get_or_warn()` still writes fallback values into the same shape as fetched values. Source inventory now exposes the desired policy, but runtime enforcement belongs to fetcher reliability. | Phase 2.3 |
| API responses do not yet expose source records, candidate evidence, review-required status, or unpublishable fallback states. | Phase 2.5 |
| Formula code does not yet consume source policies or reject mismatched unit/tier inputs. | Phase 2.4 |
| Flutter Pricing Review UI must later display source status, evidence, and review-required records from the Management API. | Frontend UI Delta roadmap |

## Acceptance Review

| Criterion | Result |
|---|---|
| No required pricing field can be silently populated by an undocumented fallback. | Passed at policy layer; runtime enforcement scheduled for Phase 2.3 |
| Static values are explicitly sourced and marked non-fetchable. | Passed |
| Dynamic values record enough metadata for later user/developer review. | Passed through key path, aliases, units, source type, normalizer, evidence, and failure behavior |
| Provider-by-provider source matrix exists. | Passed |
| No live cloud access is required for verification. | Passed |

## Residual Risk

The inventory is now the pricing source policy, but existing fetchers still need
to produce evidence-rich result objects and stop collapsing dynamic, static, and
fallback values into indistinguishable JSON. That is the core work of Phase 2.3.
