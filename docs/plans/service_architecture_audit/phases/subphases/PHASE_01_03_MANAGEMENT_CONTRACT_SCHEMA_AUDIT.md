---
title: "Phase 1.3: Management Contract And Schema Audit"
description: "Audit Management API request/response schemas, OpenAPI contracts, and raw payload exceptions."
tags: [management-api, openapi, schemas, contracts]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_01_MANAGEMENT_API_AUDIT.md
- twin2multicloud_backend/src/schemas/
- twin2multicloud_backend/src/api/routes/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 1.3: Management Contract And Schema Audit

## Purpose

Ensure that Flutter-facing and service-facing Management API contracts are typed,
stable, and safe to consume.

## Scope

| In scope | Out of scope |
|---|---|
| Request/response model coverage | Changing product semantics |
| Schema-version policy | Regenerating Flutter clients |
| Raw-map exception register | Optimizer/Deployer internals |

## Deliverables

- Endpoint-to-schema matrix for user-facing routes.
- List of untyped or partially typed responses.
- Schema-version recommendation for read models.
- Explicit register for allowed raw payloads such as redacted Terraform outputs.

## Acceptance Criteria

- Every Flutter-facing endpoint either has a response model or an explicit
  reason why the payload remains unstructured.
- Contract changes needed by Flutter are identified before Flutter work starts.
- Secret-like fields are excluded from response schemas or redacted by contract.

## Verification

- Static schema and router review.
- OpenAPI review when the Management API is running.
- No live cloud calls.

## Parent Phase

[Phase 1: Management API Audit](../PHASE_01_MANAGEMENT_API_AUDIT.md)
