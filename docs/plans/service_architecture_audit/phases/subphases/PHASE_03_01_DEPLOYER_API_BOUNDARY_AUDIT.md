---
title: "Phase 3.1: Deployer API Boundary Audit"
description: "Classify Deployer API routes and remove provider-specific responsibilities from route-level planning."
tags: [deployer, api, boundaries, audit]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/src/api/
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 3.1: Deployer API Boundary Audit

## Purpose

Determine which Deployer API routes are thin controllers and which currently own
validation, provider logic, workspace state, or file I/O.

Status: Complete.

## Scope

| In scope | Out of scope |
|---|---|
| API route classification | Provider implementation changes |
| Project/template/runtime boundary review | Live E2E |
| Route-to-service extraction candidates | Management API changes |

## Deliverables

- [x] Endpoint inventory for project files, validation, deployment, logs,
  simulator, credentials, verify, and functions.
- [x] Mixed-responsibility route list with extraction priority.
- [x] Test-only versus production endpoint classification.
- [x] Runtime credential file access hardening for generic project file routes.

## Acceptance Criteria

- [x] API routes have clear target owners.
- [x] Provider-specific behavior is assigned below the route layer.
- [x] Runtime file endpoints cannot read legacy template credentials.

## Verification

- [x] Static route review.
- [x] Existing API test inventory.
- [x] No live deployment.
- [x] Docker targeted tests:
  `python -m pytest tests/unit/test_file_manager_crud.py::TestProjectFileBrowserSecurity tests/api/test_project_file_routes.py -q`

## Review Artifact

[Phase 3.1 Review: Deployer API Boundary](../../PHASE_03_01_DEPLOYER_API_BOUNDARY_REVIEW.md)

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
