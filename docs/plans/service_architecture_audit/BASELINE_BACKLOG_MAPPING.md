---
title: "Service Audit Backlog Mapping"
description: "Backlog mapping for service audit phases and GitHub issue readiness."
tags: [backlog, github, audit, roadmap]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md
- gh issue list --repo TVJunkie724/master-thesis --state open --search "service architecture audit"
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Service Audit Backlog Mapping

GitHub is reachable from the current environment, but the service audit phases
do not yet have dedicated issues. Existing issue search for service architecture
audit work did not return a matching service-audit issue.

## Required Issues

| Phase | Proposed issue title | Labels |
|---|---|---|
| Phase 0 | Define cross-service architecture audit baseline | `type:task`, `area:backend`, `area:optimizer`, `area:deployer`, `priority:p1` |
| Phase 1 | Audit and refactor Management API architecture boundaries | `type:task`, `area:backend`, `priority:p1` |
| Phase 2 | Audit and harden Optimizer pricing and calculation architecture | `type:task`, `area:optimizer`, `priority:p1` |
| Phase 3 | Audit and harden Deployer API, provider, workspace, logging, and preflight boundaries | `type:task`, `area:deployer`, `priority:p1` |
| Phase 4 | Run cross-service quality gate for thesis-ready backend services | `type:task`, `area:backend`, `area:optimizer`, `area:deployer`, `priority:p1` |

## Issue Creation Rule

Create or update GitHub issues before starting Phase 1 implementation work.
Phase 0 can complete with this mapping because it is the local baseline that
defines which issues are needed.

## Existing Related Issues

| Issue | Relationship |
|---|---|
| `#6` Implement CloudConnection credential SSOT and compose split | Related to credential/security criteria, but not a replacement for service audit phases. |
| `#73` Split Flutter twin overview into dashboard detail actions and logs | Related UI work, not a service audit issue. |

## Acceptance Criteria

- Every service audit phase has an issue before code refactoring starts.
- Commits for later implementation phases reference the relevant issue.
- Issues include acceptance criteria and verification commands from the phase
  documents.
