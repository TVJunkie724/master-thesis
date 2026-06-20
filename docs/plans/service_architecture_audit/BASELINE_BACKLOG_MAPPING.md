---
title: "Service Audit Backlog Mapping"
description: "Backlog mapping for service audit phases and GitHub issue readiness."
tags: [backlog, github, audit, roadmap]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md
- gh issue list --repo TVJunkie724/master-thesis --state open --search "service architecture audit"
- GitHub issues #101, #102, #103, #104, #105
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Service Audit Backlog Mapping

GitHub issues now exist for every service audit phase.

## Required Issues

| Phase | Issue | Labels |
|---|---|---|
| Phase 0 | [#101 Define cross-service architecture audit baseline](https://github.com/TVJunkie724/master-thesis/issues/101) | `type:task`, `area:backend`, `area:optimizer`, `area:deployer`, `priority:p1` |
| Phase 1 | [#102 Audit and refactor Management API architecture boundaries](https://github.com/TVJunkie724/master-thesis/issues/102) | `type:task`, `area:backend`, `priority:p1` |
| Phase 2 | [#103 Audit and harden Optimizer pricing and calculation architecture](https://github.com/TVJunkie724/master-thesis/issues/103) | `type:task`, `area:optimizer`, `priority:p1` |
| Phase 3 | [#104 Audit and harden Deployer API, provider, workspace, logging, and preflight boundaries](https://github.com/TVJunkie724/master-thesis/issues/104) | `type:task`, `area:deployer`, `priority:p1` |
| Phase 4 | [#105 Run cross-service quality gate for thesis-ready backend services](https://github.com/TVJunkie724/master-thesis/issues/105) | `type:task`, `area:backend`, `area:optimizer`, `area:deployer`, `priority:p1` |

## Issue Creation Rule

Reference the relevant issue in every later implementation commit.

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
