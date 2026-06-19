---
title: "Phase 3.1: Deployer API Boundary Audit"
description: "Classify Deployer API routes and remove provider-specific responsibilities from route-level planning."
tags: [deployer, api, boundaries, audit]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/api/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 3.1: Deployer API Boundary Audit

## Purpose

Determine which Deployer API routes are thin controllers and which currently own
validation, provider logic, workspace state, or file I/O.

## Scope

| In scope | Out of scope |
|---|---|
| API route classification | Provider implementation changes |
| Project/template/runtime boundary review | Live E2E |
| Route-to-service extraction candidates | Management API changes |

## Deliverables

- Endpoint inventory for project files, validation, deployment, logs,
  simulator, credentials, verify, and functions.
- Mixed-responsibility route list with extraction priority.
- Test-only versus production endpoint classification.

## Acceptance Criteria

- API routes have clear target owners.
- Provider-specific behavior is assigned below the route layer.
- Runtime file endpoints cannot read legacy template credentials.

## Verification

- Static route review.
- Existing API test inventory.
- No live deployment.

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
