---
title: "Phase 2.1 Review: Optimizer Strategy Contract"
description: "Review of the optimizer strategy contract that binds objective, pricing intents, formulas, units, sources, and evidence requirements."
tags: [optimizer, pricing, contracts, audit, issue-102]
lastUpdated: "2026-07-17"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/subphases/PHASE_02_01_OPTIMIZER_STRATEGY_CONTRACT_AUDIT.md
- 2-twin2clouds/backend/calculation_v2/strategy_contracts.py
- 2-twin2clouds/backend/calculation_v2/components/
- 2-twin2clouds/json/fetched_data/
- 2-twin2clouds/tests/unit/calculation_v2/test_strategy_contracts.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 2.1 Review: Optimizer Strategy Contract

## Review Result

Phase 2.1 is complete. The Optimizer now has a code-level strategy contract in
`2-twin2clouds/backend/calculation_v2/strategy_contracts.py`. It declares the
currently enabled objective, provider/layer pricing intents, pricing source
fields, source units, canonical units, normalizers, formula bindings, usage
inputs, and result fields.

Cost optimization is the only enabled strategy. Latency, emissions, and
resilience are present as disabled future objectives with explicit extension
notes and no runtime formula bindings.

## Implemented Contract Boundary

| Boundary | Implementation |
|---|---|
| Objective selection | `OptimizationObjective` and `ObjectiveStatus` distinguish enabled runtime objectives from planned objectives. |
| Pricing source shape | `PricingFieldContract` defines key path, aliases, source type, evidence requirement, source unit, canonical unit, and quantity basis. |
| Pricing intent | `PricingIntentContract` binds one provider/layer component to the pricing fields it requires. |
| Formula ownership | `FormulaBindingContract` binds pricing intents to the calculator entrypoint, formula type, result component, required usage inputs, and normalizer. |
| Runtime registry | `strategy_contracts()`, `enabled_strategy_contracts()`, and `get_strategy_contract()` expose the registry without importing fetchers or calculators. |
| Self-hosted GCP options | GCP L4/L5 self-hosted intents are declared but marked not enabled for the default cheapest path, matching current runtime behavior. |

## Provider And Layer Coverage

The cost strategy covers:

- L0 transfer egress for AWS, Azure, and GCP.
- L1 ingestion for AWS IoT Core, Azure IoT Hub, and GCP Pub/Sub.
- L2 functions/orchestration/event routing for AWS, Azure, and GCP where the
  current calculators support them.
- L3 hot/cool/archive storage for AWS, Azure, and GCP.
- L4 twin management for AWS and Azure as default candidates, with GCP
  self-hosted declared as an explicit opt-in candidate.
- L5 visualization for AWS and Azure as default candidates, with GCP
  self-hosted declared as an explicit opt-in candidate.

## Drift Checks Added

`2-twin2clouds/tests/unit/calculation_v2/test_strategy_contracts.py` verifies:

- Only `cost` is runtime-enabled.
- Disabled future objectives have no formula bindings.
- The cost contract validates without duplicate intents or broken formula
  references.
- Every declared pricing field resolves against the bundled dynamic provider
  pricing JSONs through its primary path or an alias.
- Dynamic provider API fields require evidence.
- Known unit/shape hotspots declare normalizers:
  Azure IoT Hub tiers, GCP Pub/Sub GiB/GB volume handling, and GCP Firestore
  per-100k operation prices. Azure Digital Twins registry evidence is normalized
  to per-operation, per-message, and per-query-unit values before it reaches
  the strategy contract.

Latest focused test evidence:

```text
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests/unit/calculation_v2/test_strategy_contracts.py -q

11 passed in 0.01s
```

Latest full-suite evidence with non-sensitive test config mounts:

```text
tmpdir=$(mktemp -d /tmp/optimizer-test-config.XXXXXX)
printf '{"aws":{}}\n' > "$tmpdir/config_credentials.json"
docker run --rm -v /Users/caroline/.codex/worktrees/01ff/master-thesis/2-twin2clouds:/app -v /Users/caroline/.codex/worktrees/01ff/master-thesis/config.json:/config/config.json:ro -v "$tmpdir/config_credentials.json":/config/config_credentials.json:ro -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests -q

204 passed in 50.78s
```

## Findings Handed To Later Subphases

| Finding | Owner phase |
|---|---|
| Azure IoT Hub currently stores `pricing_tiers`, while the calculator still reads unit-oriented fields with zero defaults. The contract now marks this as `azure_iot_hub_tier_table`; the calculation hardening phase must implement the normalizer/formula bridge. | Phase 2.4 |
| Azure Digital Twins originally modeled query units as a fabricated tier table. Phase 17 removes that table, models query units as workload consumption, and splits operation, routed-message, and query-unit pricing into independent evidence-backed intents. | Phase 17 |
| GCP Pub/Sub is volume-based while AWS/Azure ingestion is message- or unit-tier based. The contract records the different quantity basis so fetchers and calculators cannot pretend that all L1 prices are per message. | Phase 2.3 and Phase 2.4 |
| Fallback/static reviewed decisions are supported by the contract model, but current source classification remains provider-API-oriented until the pricing source audit formalizes dynamic vs static vs reviewed decision state. | Phase 2.2 |
| The contract is not yet enforced inside the fetcher pipeline or API responses. That enforcement belongs to fetcher reliability and API contract phases. | Phase 2.3 and Phase 2.5 |

## Acceptance Review

| Criterion | Result |
|---|---|
| Cost optimization remains the only enabled objective unless explicitly implemented later. | Passed |
| Future objectives can be added without changing current cost semantics. | Passed through disabled objective declarations and registry tests |
| Pricing intent and calculation formula cannot drift silently. | Passed at registry level; runtime enforcement is scheduled in later Phase-2 slices |
| Unit/tier mismatches are visible before formula use. | Passed for known hotspots through explicit normalizer declarations |
| Contract is testable without live cloud access. | Passed |

## Residual Risk

The contract now defines the intended strategy boundary, but it is not yet the
runtime enforcement layer for fetcher row selection, fallback rejection, or
formula input normalization. Those are the next Optimizer subphases and are not
optional for thesis-ready pricing correctness.
