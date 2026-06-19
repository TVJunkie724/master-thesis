---
title: "Phase 1.6: Management Test Matrix"
description: "Map Management API tests to route, service, schema, migration, security, and downstream-proxy risks."
tags: [management-api, tests, quality, audit]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_01_MANAGEMENT_API_AUDIT.md
- twin2multicloud_backend/tests/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 1.6: Management Test Matrix

## Purpose

Ensure Management API refactors are backed by a test matrix that matches risk.

## Scope

| In scope | Out of scope |
|---|---|
| Existing test inventory | Live cloud E2E |
| Missing regression tests | Flutter widget tests |
| Security and contract test gaps | Rewriting tests before implementation plan |

## Deliverables

- Test-to-risk matrix for routes, services, schemas, DB, auth, SSE, downstream
  proxies, and redaction.
- List of high-priority missing tests before route extraction.
- Safe Docker command plan for Management API tests.

## Acceptance Criteria

- Every planned Management API refactor slice has a pre/post test strategy.
- Security-sensitive flows have explicit negative tests.
- Downstream service failures are represented without live cloud dependency.

## Verification

- Static test inventory.
- Mapping against Phase 1.1 through Phase 1.5 findings.
- No live cloud E2E tests.

## Parent Phase

[Phase 1: Management API Audit](../PHASE_01_MANAGEMENT_API_AUDIT.md)
