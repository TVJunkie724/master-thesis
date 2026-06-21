---
title: "Phase 2.4 Review: Optimizer Calculation Correctness"
description: "Review of formula and unit hardening for tier-aware Azure IoT Hub and Azure Digital Twins calculation."
tags: [optimizer, calculation, formulas, tiering, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
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
shape and Azure Digital Twins per-1K pricing/query-unit tier shape instead of
silently relying on old unit fields or undercounting per-1K values.

## Implemented Formula Hardening

| Area | Previous behavior | New behavior |
|---|---|---|
| Azure IoT Hub | Calculator expected `pricePerUnit`, `messagesPerUnit`, and `additionalMessagePrice`; canonical fetched JSON only contains `pricing_tiers`, so the IoT Hub cost could collapse to zero. | Calculator detects `pricing_tiers`, applies free tier, computes required units per tier threshold, enforces tier limits, and selects the cheapest valid tier. |
| Azure Digital Twins operations | `operationPrice` was treated as price per million operations. | `operationPrice` defaults to per-1K normalization, matching the fetcher meter shape. Explicit unit hints are supported. |
| Azure Digital Twins messages | `messagePrice` was treated as price per message. | `messagePrice` defaults to per-1K normalization. |
| Azure Digital Twins queries | `queryPrice` was applied directly per query and `queryUnitTiers` was ignored. | Query cost uses query units. The default query-unit weight comes from the lowest configured `queryUnitTiers` tier, with an explicit override for future workload modeling. |
| Strategy contract | Azure Digital Twins source units suggested action/message/query-unit values directly. | Contract now declares `usd/1k_*` source units and the per-1K normalizer for operation, message, and query prices. |

## Tests Added

`2-twin2clouds/tests/unit/calculation_v2/test_azure_tiered_calculations.py`
verifies:

- Azure IoT Hub free-tier pricing.
- Azure IoT Hub unit scaling within a tier.
- Azure IoT Hub selection of the next tier when lower-tier capacity is exceeded.
- Azure IoT Hub rejection when no tier can cover the requested volume.
- Azure Digital Twins per-1K normalization for operations, messages, and query units.
- Azure Digital Twins explicit query-unit weight override.

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
| Action-based | Azure Digital Twins per-1K normalization and query-unit weighting added. |
| Storage-based | Existing provider storage calculators remain covered; deeper retrieval/minimum-duration modeling remains a later pricing-model refinement. |
| User/time-based | Existing Grafana and self-hosted VM calculators remain covered. |
| Transfer | Existing transfer helper remains covered by current engine tests; tier-specific transfer enforcement remains a later provider-model refinement. |

## Findings Handed To Later Subphases

| Finding | Owner phase |
|---|---|
| Calculation output still does not expose the selected pricing evidence records in the public response. | Phase 2.5 |
| Storage minimum-duration fees, request-unit variants, and transfer tiers need deeper provider-model verification when broad live/provider fixture evidence is available. | Phase 2.6 and future pricing model issue |
| The Azure Digital Twins default query-unit weight uses the lowest tier until the UI/API can provide query complexity intent explicitly. | Frontend UI Delta roadmap and future workload model issue |
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
