---
title: "Phase 2.4 Review: Optimizer Calculation Correctness"
description: "Review of formula and unit hardening for tier-aware Azure IoT Hub and Azure Digital Twins calculation."
tags: [optimizer, calculation, formulas, tiering, issue-102]
lastUpdated: "2026-07-17"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/subphases/PHASE_02_04_OPTIMIZER_CALCULATION_CORRECTNESS_AUDIT.md
- 2-twin2clouds/backend/calculation_v2/components/azure/iot_hub.py
- 2-twin2clouds/backend/calculation_v2/components/azure/digital_twins.py
- 2-twin2clouds/backend/calculation_v2/strategy_contracts.py
- 2-twin2clouds/tests/unit/calculation_v2/test_azure_tiered_calculations.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 2.4 Review: Optimizer Calculation Correctness

## Review Result

Phase 2.4 is complete for the known high-risk Azure tiering and unit gaps. The
calculation layer now consumes the canonical Azure IoT Hub `pricing_tiers`
shape. Azure Digital Twins was subsequently corrected in Phase 17: provider
prices are normalized to individual billing units at the fetch boundary, while
the engine derives billable operation, routed-message, and query-unit
quantities from the workload contract.

## Implemented Formula Hardening

| Area | Previous behavior | New behavior |
|---|---|---|
| Azure IoT Hub | Calculator expected `pricePerUnit`, `messagesPerUnit`, and `additionalMessagePrice`; canonical fetched JSON only contains `pricing_tiers`, so the IoT Hub cost could collapse to zero. | Calculator detects `pricing_tiers`, applies free tier, computes required units per tier threshold, enforces tier limits, and selects the cheapest valid tier. |
| Azure Digital Twins operations | Legacy raw aliases had ambiguous units. | Registry evidence normalizes the official 1K meter to `pricePerOperation`; query-response operation quantities use one-KB increments. |
| Azure Digital Twins messages | Legacy raw aliases had ambiguous units. | Registry evidence normalizes the official 1K meter to `pricePerMessage`; the five-layer baseline derives routed-message quantity as zero because it deploys no ADT Event Route. |
| Azure Digital Twins queries | Queries were previously assigned a fabricated pricing tier. | Query-unit consumption is `logical queries * average query units per query`; `queryUnitTiers` no longer exists. |
| Strategy contract | One combined ADT intent obscured different billing quantities. | Independent operation, routed-message, and query-unit intents consume already normalized per-unit evidence. |

## Tests Added

`2-twin2clouds/tests/unit/calculation_v2/test_azure_tiered_calculations.py`
verifies:

- Azure IoT Hub free-tier pricing.
- Azure IoT Hub unit scaling within a tier.
- Azure IoT Hub selection of the next tier when lower-tier capacity is exceeded.
- Azure IoT Hub rejection when no tier can cover the requested volume.
- Azure Digital Twins billable one-KB operation boundaries.
- Azure Digital Twins explicit query-unit and query-response assumptions.
- Azure Digital Twins topology-derived zero routed-message quantity.

Latest focused evidence:

```text
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests/unit/calculation_v2/test_azure_tiered_calculations.py tests/unit/calculation_v2/test_strategy_contracts.py -q

17 passed in 0.03s
```

Latest calculation/pricing evidence:

```text
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests/unit/calculation_v2 tests/unit/pricing -q

109 passed in 0.28s
```

Latest full-suite evidence with non-sensitive test config mounts:

```text
tmpdir=$(mktemp -d /tmp/optimizer-test-config.XXXXXX)
printf '{"aws":{}}\n' > "$tmpdir/config_credentials.json"
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -v "$tmpdir/config_credentials.json":/config/config_credentials.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests -q

222 passed in 50.69s
```

## Formula Inventory Status

| Formula family | Status |
|---|---|
| Message-based | Hardened for Azure IoT Hub tier table and existing AWS/GCP ingestion models remain covered by tests. |
| Execution-based | Existing request/GB-second calculators remain covered. |
| Action-based | Azure Digital Twins uses normalized unit prices and explicit billable quantities; IoT Hub retains its capacity-tier model. |
| Storage-based | Existing provider storage calculators remain covered; deeper retrieval/minimum-duration modeling remains a later pricing-model refinement. |
| User/time-based | Existing Grafana and self-hosted VM calculators remain covered. |
| Transfer | Existing transfer helper remains covered by current engine tests; tier-specific transfer enforcement remains a later provider-model refinement. |

## Findings Handed To Later Subphases

| Finding | Owner phase |
|---|---|
| Calculation output still does not expose the selected pricing evidence records in the public response. | Phase 2.5 |
| Storage minimum-duration fees, request-unit variants, and transfer tiers need deeper provider-model verification when broad live/provider fixture evidence is available. | Phase 2.6 and future pricing model issue |
| Azure Digital Twins query-unit and query-response assumptions are estimates until production telemetry can provide measured values; defaults and provenance are visible in both traces. | Phase 17 operational boundary |
| Runtime calculation does not yet reject every source-policy mismatch before producing totals. The key known unit/tier gaps are fixed; a full enforcement envelope belongs to API/result contract hardening. | Phase 2.5 |

## Acceptance Review

| Criterion | Result |
|---|---|
| Each corrected formula declares expected input units. | Passed through Strategy Contract updates and tests |
| Provider tiering differences are modeled, rejected, or documented. | Passed for Azure IoT Hub and Azure Digital Twins; remaining provider-model refinements are registered |
| Calculation output can explain which pricing evidence was used. | Partially passed at internal evidence layer; public response exposure belongs to Phase 2.5 |
| No paid cloud tests are required. | Passed |

## Residual Risk

This phase fixes the highest-risk known calculation bugs without pretending that
all provider pricing models are now final. The next phase must expose source
policy, evidence, review-required state, and calculation metadata through typed
API contracts so the Management API and Flutter UI can display them safely.
