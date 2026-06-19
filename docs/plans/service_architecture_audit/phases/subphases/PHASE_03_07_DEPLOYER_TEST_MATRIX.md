---
title: "Phase 3.7: Deployer Test Matrix"
description: "Map Deployer tests to API, provider, Terraform, workspace, logging, permission, simulator, and security risks."
tags: [deployer, tests, quality, security]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_03_DEPLOYER_AUDIT.md
- 3-cloud-deployer/tests/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 3.7: Deployer Test Matrix

## Purpose

Define safe Deployer verification coverage without accidentally including live
cloud E2E tests.

## Scope

| In scope | Out of scope |
|---|---|
| Unit/API/integration test inventory | Default live E2E execution |
| E2E exclusion policy | Cloud resource cost validation |
| Security and workspace regression gaps | Flutter widget tests |

## Deliverables

- Test-to-risk matrix for API, provider, Terraform package building, workspace,
  validation, logs, permissions, simulator, and redaction.
- Explicit default test command list excluding `tests/e2e/`.
- Opt-in E2E command registry for later user-approved runs.
- Missing high-risk test list for implementation planning.

## Acceptance Criteria

- Ordinary verification cannot deploy cloud resources.
- Every planned Deployer refactor has matching safe regression tests.
- E2E tests remain documented but quarantined from default checks.

## Verification

- Static test inventory.
- Mapping against Phase 3.1 through Phase 3.6 findings.
- No live cloud execution.

## Parent Phase

[Phase 3: Deployer Audit](../PHASE_03_DEPLOYER_AUDIT.md)
