---
title: "Phase 3.6: Deployer Simulator Test Utility Audit"
description: "Audit simulator and test utility behavior separately from core deployment hardening."
tags: [deployer, simulator, test-utilities, audit]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/api/simulator.py
- 3-cloud-deployer/src/iot_device_simulator/
- 3-cloud-deployer/tests/
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 3.6: Deployer Simulator Test Utility Audit

## Purpose

Keep simulator and diagnostic-tool bugs visible without mixing them into the
deployment-core refactor.

Status: Complete.

## Scope

| In scope | Out of scope |
|---|---|
| Simulator API and CLI utility review | Full simulator UI redesign |
| Test endpoint safety | Real device integration |
| Known broken flows and log needs | Live cloud E2E by default |

## Deliverables

- [x] Simulator/test utility inventory by provider.
- [x] Broken or ambiguous workflow list.
- [x] Safe mock/test mode contract for Management API and Flutter.
- [x] Follow-up issue list for simulator logs and diagnostics.
- [x] GCP provider alias and shared payload path fixes.

## Acceptance Criteria

- [x] Simulator issues are tracked independently from deployment core.
- [x] Test utility endpoints cannot be confused with production deployment.
- [x] Safe local tests exist or are planned for simulator flows.

## Verification

- [x] Static simulator route and utility review.
- [x] Test inventory excluding live E2E.
- [x] No real cloud resources.
- [x] Docker targeted tests:
  `python -m pytest tests/unit/test_simulator_api_boundaries.py tests/test_gcp_simulator.py tests/integration/azure/test_azure_simulator.py -q`

## Review Artifact

[Phase 3.6 Review: Deployer Simulator Test Utility](../../PHASE_03_06_DEPLOYER_SIMULATOR_TEST_UTILITY_REVIEW.md)

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
