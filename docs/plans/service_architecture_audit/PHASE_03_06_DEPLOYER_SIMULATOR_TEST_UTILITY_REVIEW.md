---
title: "Phase 3.6 Review: Deployer Simulator Test Utility"
description: "Review evidence and implementation outcome for simulator and diagnostic utility boundaries."
tags: [deployer, simulator, test-utilities, diagnostics, review]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 3.6 Review: Deployer Simulator Test Utility

## Result

Status: Complete.

Simulator behavior is now tracked independently from deployment-core hardening.
Two concrete boundary defects were fixed without running live device or cloud
tests:

- GCP simulator aliases are normalized consistently for stream and download.
- WebSocket simulator payload lookup prefers the canonical shared
  `iot_device_simulator/payloads.json` path and only then supports the legacy
  provider-local path.

## Simulator Inventory

| Provider | Source directory | Download support | Stream support after 3.6 |
|---|---|---|---|
| AWS | `src/iot_device_simulator/aws` | yes | yes |
| Azure | `src/iot_device_simulator/azure` | yes | yes |
| GCP | `src/iot_device_simulator/google` | yes through `gcp`/`google` alias | yes through `gcp`/`google` alias |

## Safe Test Utility Contract

| Utility surface | Contract |
|---|---|
| Simulator download | Returns standalone ZIP and marks response with `X-Twin2MultiCloud-Utility: simulator`. |
| Simulator stream | Validates project, provider, config, and payload files before starting subprocess. |
| Payload lookup | Uses shared payload file first; provider-local payloads remain legacy fallback. |
| Provider aliases | Public `gcp` and legacy/internal `google` both resolve to `google` simulator folder. |
| Verification | Unit/integration tests only; no real device/cloud integration by default. |

## Broken Or Ambiguous Workflows

| Workflow | Status |
|---|---|
| GCP WebSocket stream provider support | Fixed in this slice. |
| Payload path mismatch between upload/download/stream | Fixed in this slice. |
| Rich simulator logs and dashboard diagnostics | Still planned after core app flows are stable. |
| Real device integration | Out of scope for this roadmap and must remain opt-in. |

## Files Changed

| File | Change |
|---|---|
| `3-cloud-deployer/src/api/simulator.py` | Added provider normalization, shared/legacy payload resolution, GCP stream support, and utility response header. |
| `3-cloud-deployer/tests/unit/test_simulator_api_boundaries.py` | Added no-live tests for provider aliases and payload path resolution. |

## Verification

Targeted Docker verification:

```bash
docker run --rm \
  -v /Users/caroline/.codex/worktrees/01ff/master-thesis/3-cloud-deployer:/app \
  -w /app \
  -e PYTHONPATH=/app \
  3cloud-deployer:latest \
  python -m pytest \
    tests/unit/test_simulator_api_boundaries.py \
    tests/test_gcp_simulator.py \
    tests/integration/azure/test_azure_simulator.py \
    -q
```

Result:

```text
25 passed
```

## Review Findings

No open findings remain for Phase 3.6.

Residual simulator work remains intentionally separate from deployment core:

- Simulator logs and diagnostics UX.
- Twin overview simulator test status.
- Real cloud/device verification after broader refactors are stable.
