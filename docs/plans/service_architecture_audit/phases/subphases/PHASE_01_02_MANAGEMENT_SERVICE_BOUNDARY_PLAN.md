---
title: "Phase 1.2: Management Service Boundary Plan"
description: "Define target service and repository ownership for Management API orchestration logic."
tags: [management-api, services, repositories, architecture]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_01_MANAGEMENT_API_AUDIT.md
- twin2multicloud_backend/src/services/
- twin2multicloud_backend/src/api/routes/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 1.2: Management Service Boundary Plan

## Purpose

Define the final ownership boundaries for Management API behavior before code is
extracted from routes.

## Scope

| In scope | Out of scope |
|---|---|
| Target service/repository map | Implementing the extraction |
| Boundary rules for downstream clients | Changing Optimizer or Deployer APIs |
| Migration order and compatibility strategy | Flutter UI wiring |

## Deliverables

- Target ownership map for twin lifecycle, cloud connections, config,
  optimizer proxy, deployer proxy, deployment operations, SSE, and test
  endpoints.
- Rule for where DB transactions start and end.
- Rule for where downstream HTTP calls are allowed.
- Compatibility plan for existing tests during extraction.

## Acceptance Criteria

- A downstream implementer can place any new Management API behavior in a
  specific route, service, repository, or client without follow-up questions.
- Routes remain thin in the target state.
- Sensitive credential materialization is isolated behind explicit services.

## Verification

- Static dependency review.
- Comparison against Phase 1.1 route classifications.
- No runtime tests required for this planning subphase.

## Parent Phase

[Phase 1: Management API Audit](../PHASE_01_MANAGEMENT_API_AUDIT.md)
