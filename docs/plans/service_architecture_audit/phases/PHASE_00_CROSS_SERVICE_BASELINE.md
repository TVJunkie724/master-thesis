---
title: "Phase 0: Cross-Service Baseline"
description: "Define the shared audit rubric, tooling baseline, stale guide cleanup plan, and verification gates for all Python services."
tags: [architecture, audit, tooling, docs, quality]
lastUpdated: "2026-06-21"
version: "1.2"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md
- ONBOARDING.md sections "Tests" and "Credentials"
- twin2multicloud_backend/DEVELOPMENT_GUIDE.md
- 2-twin2clouds/DEVELOPMENT_GUIDE.md
- 3-cloud-deployer/development_guide.md
- requirements.txt files in all three service projects
- docs/plans/service_architecture_audit/BASELINE_AUDIT_RUBRIC.md
- docs/plans/service_architecture_audit/BASELINE_TEST_AND_TOOLING_POLICY.md
- docs/plans/service_architecture_audit/BASELINE_DEVELOPMENT_GUIDE_CLEANUP.md
- docs/plans/service_architecture_audit/BASELINE_BACKLOG_MAPPING.md
EXTRACTED: 2026-06-21 | VERSION: 1.2
-->

# Phase 0: Cross-Service Baseline

Status: Complete.

## Summary

Create a shared baseline before service-specific work starts. This avoids three
separate audits using three different quality bars.

## Scope

| In scope | Out of scope |
|---|---|
| Shared audit rubric for all Python services | Refactoring business logic |
| Current container/test command normalization | Running live cloud E2E tests |
| Static analysis/security tooling plan | Installing new tooling without implementation approval |
| Development Guide cleanup plan | Rewriting the documentation site |
| Cross-service error/log/security criteria | Implementing a central observability backend |

## Audit Findings To Address

| Finding | Impact |
|---|---|
| Development Guides contain stale container names, Windows paths, and broad auto-run permission language. | Handoffs become misleading and can encourage unsafe commands. |
| The Python services expose only `requirements.txt`; no shared `pyproject.toml`, Ruff, mypy, pytest, or Bandit policy was found. | Quality checks are not reproducible or comparable across services. |
| Default verification boundaries around E2E/cloud-cost tests are not consistently encoded in every service guide. | Future agents may accidentally run costly or destructive tests. |
| Error/logging/security criteria exist implicitly in code and chats, not as a shared gate. | Each refactor can drift into a different standard. |

## Subphases

| Subphase | Status | Deliverable |
|---|---|---|
| 0.1 Audit rubric | Complete | [BASELINE_AUDIT_RUBRIC.md](../BASELINE_AUDIT_RUBRIC.md) |
| 0.2 Tooling baseline | Complete | [BASELINE_TEST_AND_TOOLING_POLICY.md](../BASELINE_TEST_AND_TOOLING_POLICY.md) |
| 0.3 Guide cleanup plan | Complete | [BASELINE_DEVELOPMENT_GUIDE_CLEANUP.md](../BASELINE_DEVELOPMENT_GUIDE_CLEANUP.md) |
| 0.4 Test boundary policy | Complete | [BASELINE_TEST_AND_TOOLING_POLICY.md](../BASELINE_TEST_AND_TOOLING_POLICY.md) |
| 0.5 Backlog mapping | Complete | [BASELINE_BACKLOG_MAPPING.md](../BASELINE_BACKLOG_MAPPING.md) |

## Review Artifact

[Phase 0 Review: Cross-Service Baseline](../PHASE_00_REVIEW_2026-06-21.md)

## Acceptance Criteria

- Every service-specific audit phase references the same rubric.
- The allowed verification commands are explicit for each service and exclude
  live cloud E2E by default.
- Stale Development Guide sections are identified before any code refactor
  relies on them.
- Security checks include secret redaction, credential file handling, and
  dependency scanning expectations.
- The baseline is narrow enough for thesis scope and does not require adopting
  heavyweight enterprise infrastructure.

## Verification Gates

- Static review of all three Development Guides.
- Static review for existing Python tooling configuration.
- Static review of default test paths to ensure E2E tests are not included.
- Roadmap review against the shared quality criteria.

## Roadmap Anchor

[Service Architecture Audit Roadmap](../ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md)
