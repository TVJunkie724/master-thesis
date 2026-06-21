---
title: "Phase 3.7: Deployer Test Matrix"
description: "Map Deployer tests to API, provider, Terraform, workspace, logging, permission, simulator, and security risks."
tags: [deployer, tests, quality, security]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/tests/
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 3.7: Deployer Test Matrix

## Purpose

Define safe Deployer verification coverage without accidentally including live
cloud E2E tests.

Status: Complete.

## Scope

| In scope | Out of scope |
|---|---|
| Unit/API/integration test inventory | Default live E2E execution |
| E2E exclusion policy | Cloud resource cost validation |
| Security and workspace regression gaps | Flutter widget tests |

## Deliverables

- [x] Test-to-risk matrix for API, provider, Terraform package building, workspace,
  validation, logs, permissions, simulator, and redaction.
- [x] Explicit default test command list excluding `tests/e2e/`.
- [x] Opt-in E2E command registry for later user-approved runs.
- [x] Missing high-risk test list for implementation planning.

## Acceptance Criteria

- [x] Ordinary verification cannot deploy cloud resources.
- [x] Every planned Deployer refactor has matching safe regression tests.
- [x] E2E tests remain documented but quarantined from default checks.

## Verification

- [x] Static test inventory.
- [x] Mapping against Phase 3.1 through Phase 3.6 findings.
- [x] No live cloud execution.

## Review Artifact

[Phase 3.7 Review: Deployer Test Matrix](../../PHASE_03_07_DEPLOYER_TEST_MATRIX_REVIEW.md)

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
