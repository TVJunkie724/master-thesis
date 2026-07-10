---
title: "Development Guide Cleanup Baseline"
description: "Cleanup plan for stale service Development Guides before relying on them for refactor handoffs."
tags: [docs, development-guide, onboarding, quality]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md
- twin2multicloud_backend/DEVELOPMENT_GUIDE.md
- 2-twin2clouds/DEVELOPMENT_GUIDE.md
- 3-cloud-deployer/development_guide.md
- README.md
- compose.yaml
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Development Guide Cleanup Baseline

The service Development Guides are useful but stale. They should not be treated
as authoritative for commands or permissions until cleaned up.

## Findings

| Guide | Finding | Required cleanup |
|---|---|---|
| `twin2multicloud_backend/DEVELOPMENT_GUIDE.md` | References old container name `master-thesis-0twin2multicloud-1` and Windows host paths. | Replace with current `management-api` compose service and `/app` container path. |
| `2-twin2clouds/DEVELOPMENT_GUIDE.md` | Contains broad auto-run permission language and stale command guidance. | Replace with safe default verification and E2E approval rule. |
| `3-cloud-deployer/development_guide.md` | Contains duplicated tool table and contradictory shell guidance. | Replace with current safe command policy and explicit E2E exclusion. |
| All service guides | Claim permissive agent execution rules that conflict with current repository safety policy. | Remove broad permission claims and point to `ONBOARDING.md` plus this baseline. |

## Canonical Replacement Content

Each guide should contain:

- service role and compose service name,
- safe default test command,
- E2E exclusion statement,
- credential safety rules,
- implementation plan location,
- link to the shared audit rubric,
- link to the service-specific audit phase.

## Cleanup Order

1. Update Management API guide first because it is the Flutter-facing
   orchestration boundary.
2. Update Optimizer guide before pricing refactors.
3. Update Deployer guide before deployment, preflight, simulator, or logging
   refactors.

## Acceptance Criteria

- No guide references stale Windows host paths.
- No guide grants broad auto-run permission.
- Every guide distinguishes safe tests from opt-in E2E/cloud-cost tests.
- Every guide links to the shared rubric and service audit roadmap.
