---
title: "Phase 3.4: Deployer Logging Error Trace Audit"
description: "Audit Deployer logs, SSE events, errors, correlation IDs, redaction, and deployment trace semantics."
tags: [deployer, logging, errors, trace]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/api/logs.py
- 3-cloud-deployer/src/api/status.py
- 3-cloud-deployer/src/terraform_runner.py
- 3-cloud-deployer/src/logger.py
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 3.4: Deployer Logging Error Trace Audit

## Purpose

Make deployment logs and errors useful for Management API and Flutter while
remaining sanitized and structured.

Status: Complete.

## Scope

| In scope | Out of scope |
|---|---|
| Print/logging inventory | External log aggregation platform |
| SSE event schema review | UI rendering implementation |
| Error taxonomy and redaction | Live deployment E2E |

## Deliverables

- [x] Inventory of `print()`, logger usage, broad exceptions, and SSE event shapes.
- [x] Target deployment event taxonomy.
- [x] Redaction and correlation-ID requirements.
- [x] Management API compatibility notes for log catch-up and live streams.
- [x] Deployment stream event redaction for logs, errors, and Terraform outputs.

## Acceptance Criteria

- [x] Logs can be correlated to operation through the existing event contract;
  project/provider/layer/phase correlation fields are documented as additive
  follow-up fields after Management API stream consumption is finalized.
- [x] Secret-like values cannot appear in API logs or streamed events.
- [x] Errors distinguish validation, packaging, Terraform, provider SDK, cleanup,
  permission, timeout, and internal failures.

## Verification

- [x] Static log/error search.
- [x] Safe log fixture test plan.
- [x] No real deployment.
- [x] Docker targeted tests:
  `python -m pytest tests/unit/core_tests/test_deployment_contracts.py tests/api/test_deployment_routes.py -q`

## Review Artifact

[Phase 3.4 Review: Deployer Logging Error Trace](../../PHASE_03_04_DEPLOYER_LOGGING_ERROR_TRACE_REVIEW.md)

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
