---
title: "Phase 3.6: Deployer Simulator Test Utility Audit"
description: "Audit simulator and test utility behavior separately from core deployment hardening."
tags: [deployer, simulator, test-utilities, audit]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/api/simulator.py
- 3-cloud-deployer/src/iot_device_simulator/
- 3-cloud-deployer/tests/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 3.6: Deployer Simulator Test Utility Audit

## Purpose

Keep simulator and diagnostic-tool bugs visible without mixing them into the
deployment-core refactor.

## Scope

| In scope | Out of scope |
|---|---|
| Simulator API and CLI utility review | Full simulator UI redesign |
| Test endpoint safety | Real device integration |
| Known broken flows and log needs | Live cloud E2E by default |

## Deliverables

- Simulator/test utility inventory by provider.
- Broken or ambiguous workflow list.
- Safe mock/test mode contract for Management API and Flutter.
- Follow-up issue list for simulator logs and diagnostics.

## Acceptance Criteria

- Simulator issues are tracked independently from deployment core.
- Test utility endpoints cannot be confused with production deployment.
- Safe local tests exist or are planned for simulator flows.

## Verification

- Static simulator route and utility review.
- Test inventory excluding live E2E.
- No real cloud resources.

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
