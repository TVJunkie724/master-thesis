---
title: "Phase 3.4: Deployer Logging Error Trace Audit"
description: "Audit Deployer logs, SSE events, errors, correlation IDs, redaction, and deployment trace semantics."
tags: [deployer, logging, errors, trace]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/api/logs.py
- 3-cloud-deployer/src/api/status.py
- 3-cloud-deployer/src/terraform_runner.py
- 3-cloud-deployer/src/logger.py
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 3.4: Deployer Logging Error Trace Audit

## Purpose

Make deployment logs and errors useful for Management API and Flutter while
remaining sanitized and structured.

## Scope

| In scope | Out of scope |
|---|---|
| Print/logging inventory | External log aggregation platform |
| SSE event schema review | UI rendering implementation |
| Error taxonomy and redaction | Live deployment E2E |

## Deliverables

- Inventory of `print()`, logger usage, broad exceptions, and SSE event shapes.
- Target deployment event taxonomy.
- Redaction and correlation-ID requirements.
- Management API compatibility notes for log catch-up and live streams.

## Acceptance Criteria

- Logs can be correlated to project, operation, provider, layer, and phase.
- Secret-like values cannot appear in API logs or streamed events.
- Errors distinguish validation, packaging, Terraform, provider SDK, cleanup,
  permission, timeout, and internal failures.

## Verification

- Static log/error search.
- Safe log fixture test plan.
- No real deployment.

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
