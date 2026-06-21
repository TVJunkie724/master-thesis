---
title: "Service Audit Rubric"
description: "Shared enterprise-grade audit rubric for Management API, Optimizer, and Deployer refactoring phases."
tags: [architecture, audit, rubric, quality]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md
- docs/plans/service_architecture_audit/phases/PHASE_00_CROSS_SERVICE_BASELINE.md
- integration_vision.md
- ONBOARDING.md
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Service Audit Rubric

This rubric is the shared quality bar for every service audit and refactor
phase. A phase is not complete until the applicable criteria below are reviewed
and either satisfied or recorded as accepted residual risk.

## Criteria

| Area | Pass condition | Finding examples |
|---|---|---|
| Responsibility boundaries | Controllers/routes stay thin; orchestration, domain logic, persistence, provider logic, and downstream clients have explicit owners. | Route calls DB, builds files, calls downstream service, and formats response in one handler. |
| Typed contracts | Public API payloads use explicit schemas; raw dictionaries are confined to documented unstructured payloads. | Endpoint returns provider-specific maps without schema, version, or documented exception. |
| Error handling | Failures use typed categories and user-safe messages; internal diagnostics are kept out of responses. | Broad catch returns raw exception text or downstream body. |
| Logging | Logs are structured enough to correlate operation, service, provider, layer, and phase. | `print()` statements, missing operation IDs, or inconsistent log event shape. |
| Secret safety | Credentials, tokens, private keys, local secret paths, and decrypted payloads never appear in logs, responses, or committed artifacts. | Downstream error includes request body or credential fragment. |
| Runtime config | Dev, test, local-cloud, and production-like settings are explicit and not inferred from local files. | Service reads root credential file implicitly during normal app startup. |
| Persistence | DB writes have clear transaction boundaries, migration expectations, and retention rules. | Model changes rely only on startup `create_all` without upgrade guidance. |
| Test coverage | Tests match risk level and cover success, validation, downstream failure, security, and regression paths. | Refactor has only happy-path tests or depends on live cloud E2E. |
| Tooling | Static analysis, security scans, and test commands are documented and reproducible inside the project runtime. | Service has no agreed lint/security command or ignores generated/E2E paths inconsistently. |
| Documentation | Development guides and roadmap docs describe current architecture only. | Guide references stale container names, Windows paths, or unsafe broad auto-run language. |

## Severity Model

| Severity | Meaning | Required action |
|---|---|---|
| Critical | Secret exposure, data loss, live cloud cost risk, destructive behavior, or broken primary workflow. | Fix before continuing to the next phase. |
| High | Architecture boundary violation, inconsistent contract, missing migration, unsafe error/log behavior, or missing high-risk tests. | Fix in the current phase or create a blocking follow-up issue. |
| Medium | Maintainability or observability problem with workaround and limited blast radius. | Fix when scoped; otherwise track explicitly. |
| Low | Documentation, naming, or polish issue that does not affect correctness or safety. | Fix opportunistically or track. |

## Review Checklist

- Boundary ownership is explicit.
- Public contracts are typed or documented as intentionally unstructured.
- Errors and logs are sanitized.
- E2E tests that can create cloud resources are excluded from default checks.
- Test gaps are mapped to risk.
- Development documentation matches current compose service names and commands.
- Residual risks have issue references or a documented reason for deferral.

## Use In Later Phases

Every Phase 1-4 review must cite this rubric and record findings using the
severity model above.
