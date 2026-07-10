---
title: "Phase 2.6 Review: Optimizer Test Matrix"
description: "Optimizer test matrix mapping pricing source, fetcher, calculation, API, validation, and credential risks to verification gates."
tags: [optimizer, tests, pricing, quality, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/subphases/PHASE_02_06_OPTIMIZER_TEST_MATRIX.md
- docs/plans/service_architecture_audit/PHASE_02_01_OPTIMIZER_STRATEGY_CONTRACT_REVIEW.md
- docs/plans/service_architecture_audit/PHASE_02_02_OPTIMIZER_PRICING_SOURCE_REVIEW.md
- docs/plans/service_architecture_audit/PHASE_02_03_OPTIMIZER_FETCHER_RELIABILITY_REVIEW.md
- docs/plans/service_architecture_audit/PHASE_02_04_OPTIMIZER_CALCULATION_CORRECTNESS_REVIEW.md
- docs/plans/service_architecture_audit/PHASE_02_05_OPTIMIZER_API_CONTRACT_REVIEW.md
- 2-twin2clouds/tests/
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 2.6 Review: Optimizer Test Matrix

## Review Result

Phase 2.6 is complete. The Optimizer has 28 `test_*.py` modules covering unit
and integration risks across pricing sources, provider fetchers, calculation
formulas, API contracts, validation, credentials, streaming, file status, and
region handling.

## Test Inventory

| Test area | Modules | Purpose |
|---|---:|---|
| Calculation v2 | 8 | Formula primitives, engine structure, pricing keys, strategy contracts, source inventory, Azure tiering |
| Pricing fetchers | 7 | Provider fetchers, orchestration, schema, validation, ambiguity evidence |
| Integration API | 8 | REST endpoints, pricing source inventory, calculation edge cases, file handling, regions, errors |
| Credentials and validation | 2 | Credential checker and optimizer validation |
| Streaming/status/core | 3 | Pricing stream, file age utility, backend core logic |

## Risk Matrix

| Risk area | Primary tests | Coverage statement |
|---|---|---|
| Strategy/objective drift | `test_strategy_contracts.py` | Only cost is enabled; future objectives are disabled; formula bindings reference declared intents. |
| Source classification | `test_pricing_source_inventory.py` | Dynamic, static official, derived, review-required, and emergency fallback states are represented. |
| Provider candidate ambiguity | `test_price_fetcher_aws.py`, `test_price_fetcher_azure.py`, `test_price_fetcher_gcp.py` | Distinct paid candidate matches become ambiguous/review-required instead of automatic success. |
| Azure tier/unit correctness | `test_azure_tiered_calculations.py` | IoT Hub tier table and Digital Twins per-1K/query-unit calculations are covered. |
| Formula and engine stability | `test_core_formulas.py`, `test_engine.py`, `test_engine_consistency.py`, `test_pricing_keys.py` | Calculation structure, positive costs, and pricing-key compatibility are covered. |
| Pricing orchestration/schema | `test_calculate_pricing_refactored.py`, `test_pricing_orchestration.py`, `test_pricing_schema.py`, `test_pricing_validation.py` | Fetch orchestration and pricing schema validation remain covered. |
| API contract | `test_pricing_source_inventory_api.py`, `test_rest_api_endpoints.py`, `test_rest_api_calculation_edge_cases.py` | New source inventory endpoint and existing REST contracts are covered. |
| Error handling | `test_error_handling.py`, `test_rest_api_file_handling_edge_cases.py` | User-safe endpoint error behavior and file edge cases are covered. |
| Credentials | `test_credentials_checker.py` | Credential checker behavior is covered without paid resource creation. |
| Streaming | `test_pricing_streaming.py` | Pricing SSE behavior and event formatting are covered. |
| Regions/file age | `test_rest_api_regions.py`, `test_utils_file_age.py` | Region endpoints and freshness helpers are covered. |

## Source-Type Coverage

| Source type | Coverage |
|---|---|
| Dynamic provider API | Source inventory tests plus provider fetcher tests for selected and ambiguous candidate cases. |
| Static official table | Source inventory tests cover static non-fetchable fields and review-required state. |
| Reviewed decision | Contract model and source inventory response support the state; runtime UI/editor creation is future work. |
| Derived calculation | Source inventory tests cover Cosmos DB RU-per-read/write as derived usage-model values. |
| Unsupported | API and inventory model expose unsupported state; no current cost field is classified unsupported. |

## Required Verification Gates

Use these gates for future Optimizer work:

| Change type | Required gate |
|---|---|
| Any Optimizer source change | Full Dockerized suite with config and non-sensitive dummy credentials. |
| Strategy/source contract change | `test_strategy_contracts.py` and `test_pricing_source_inventory.py` plus full suite. |
| Provider fetcher matching change | Provider-specific fetcher tests plus `tests/unit/pricing` and full suite. |
| Formula/calculation change | `tests/unit/calculation_v2` plus full suite. |
| API route or response contract change | Affected integration tests, OpenAPI assertion for schema-visible endpoints, plus full suite. |
| Credential/error/logging change | Credential/error tests plus full suite. |

Full-suite command:

```text
tmpdir=$(mktemp -d /tmp/optimizer-test-config.XXXXXX)
printf '{"aws":{}}\n' > "$tmpdir/config_credentials.json"
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -v "$tmpdir/config_credentials.json":/config/config_credentials.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests -q
```

Latest full-suite evidence:

```text
226 passed in 50.71s
```

## Missing Tests Registered For Later Work

| Gap | Owner |
|---|---|
| Versioned calculation response with selected pricing evidence. | Future Optimizer calculation response issue |
| Runtime reviewed-decision persistence and edit flow. | Management API / Pricing Review UI roadmap |
| Broad harvested provider fixtures for current AWS/Azure/GCP catalog drift. | Future pricing provider fixture issue |
| Storage minimum-duration fees, transfer tiers, and deeper provider-specific pricing formulas. | Future pricing model hardening issue |
| End-to-end UI review workflow. | Frontend UI Delta roadmap |

## Acceptance Review

| Criterion | Result |
|---|---|
| Every pricing source type has at least one regression or contract test. | Passed |
| Every formula correction has unit tests. | Passed |
| API failure paths are covered with user-safe errors. | Passed for existing error tests and new source inventory provider validation |
| No paid cloud resource tests are required. | Passed |

## Residual Risk

The Optimizer is now thesis-ready for the implemented pricing contract,
source-governance, fetcher-evidence, Azure tiering, and source-inventory API
scope. Remaining risk is explicitly future work around provider fixture breadth,
reviewed-decision persistence, UI consumption, and deeper provider-specific
billing semantics.
