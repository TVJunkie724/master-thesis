---
title: "Service Architecture Audit Roadmap"
description: "Project-wide roadmap for auditing and hardening Management API, Optimizer, and Deployer against shared enterprise-grade code-quality criteria."
tags: [architecture, audit, backend, optimizer, deployer, quality]
lastUpdated: "2026-06-21"
version: "1.6"
---

<!-- SOURCES:
- integration_vision.md sections "System Architecture" and "The Management Platform"
- ONBOARDING.md sections "Source Of Truth", "Project Map", "Tests", "Credentials"
- docs/codebase_investigation_findings.md
- docs/design_patterns_inventory.md
- twin2multicloud_backend/DEVELOPMENT_GUIDE.md
- 2-twin2clouds/DEVELOPMENT_GUIDE.md
- 3-cloud-deployer/development_guide.md
- twin2multicloud_backend/src/
- 2-twin2clouds/backend/, 2-twin2clouds/api/
- 3-cloud-deployer/src/
EXTRACTED: 2026-06-21 | VERSION: 1.6
-->

# Service Architecture Audit Roadmap

This roadmap captures the next project-wide audit track after the frontend
architecture refactoring foundation. It applies the same quality criteria to the
three Python service projects:

- `twin2multicloud_backend` as the Management API / Orchestrator boundary,
- `2-twin2clouds` as the Optimizer / Brain,
- `3-cloud-deployer` as the Deployer / Muscle.

The goal is not to rewrite all services. The goal is to identify the highest
impact architecture debts, create implementation-ready phases, and harden each
service without losing thesis scope.

## Shared Quality Criteria

| Criterion | Target state |
|---|---|
| Responsibility boundaries | Routes/controllers are thin; orchestration, domain logic, provider logic, and persistence are separated. |
| Typed contracts | API request/response models and internal read models are explicit and versioned where needed. |
| Error handling | Failures use consistent typed errors, user-safe messages, and service-safe diagnostics. |
| Logging | Structured logs are consistent, sanitized, and correlated across service boundaries. |
| Security | Secrets are never logged, rendered, persisted in plaintext, or returned through generic error messages. |
| Runtime config | Dev/test/local-cloud/production settings are explicit and documented. |
| Tests | Unit, integration, contract, and security checks are mapped to risk; E2E cloud tests remain opt-in. |
| Tooling | Static analysis, formatting, dependency, and security checks are reproducible in Docker. |
| Documentation | Development guides reflect the current compose stack and no longer preserve stale automation claims. |

## Current Audit Snapshot

The snapshot below is static and planning-oriented. It does not claim to be a
final code review finding list; it is the evidence used to plan the phases.

| Service | Audit signals |
|---|---|
| Management API | 48 Python source files; `src/api/routes/twins.py` has 1601 lines; `config.py`, `deployer.py`, `optimizer.py`, and `test_endpoints.py` also carry large orchestration surfaces; 31 broad `except Exception` matches; 13 `print()` matches; Development Guide references stale container naming. |
| Optimizer | 91 Python files; pricing orchestration/fetching and calculation layers carry the main complexity; 49 broad `except Exception` matches; 12 `print()` matches; no central `pyproject.toml`, Ruff, mypy, pytest, or Bandit config found in the project root. |
| Deployer | 163 Python source files under `src`; 36k+ source lines; many API and provider files exceed 800-1300 lines; 321 broad `except Exception` matches; 338 `print()` matches; E2E tests and generated `.build` state require strict exclusion from default verification. |
| Cross-service | Only per-project `requirements.txt` files were found for Python tooling; Development Guides contain outdated or contradictory command/permission guidance; service contracts and error shapes are not governed from one shared quality gate. |

## Phase Index

| Phase | Status | Document | Primary outcome |
|---|---|---|---|
| 0 | Complete | [PHASE_00_CROSS_SERVICE_BASELINE.md](phases/PHASE_00_CROSS_SERVICE_BASELINE.md) | Shared audit rubric, tooling baseline, stale guide cleanup plan, and cross-service quality gates. |
| 1 | Complete | [PHASE_01_MANAGEMENT_API_AUDIT.md](phases/PHASE_01_MANAGEMENT_API_AUDIT.md) | Management API route/service/persistence boundary audit and refactor plan. |
| 2 | Complete | [PHASE_02_OPTIMIZER_AUDIT.md](phases/PHASE_02_OPTIMIZER_AUDIT.md) | Optimizer pricing/calculation/API boundary audit and strategy-contract hardening plan. |
| 3 | Planned | [PHASE_03_DEPLOYER_AUDIT.md](phases/PHASE_03_DEPLOYER_AUDIT.md) | Deployer API/provider/workspace/logging/security audit and refactor plan. |
| 4 | Planned | [PHASE_04_SERVICE_QUALITY_GATE.md](phases/PHASE_04_SERVICE_QUALITY_GATE.md) | Consolidated verification gate across Management API, Optimizer, and Deployer. |

## Subphase Split Decision

Concept review found that Phases 1, 2, and 3 are correct as service-level
containers, but too broad to implement as single slices. They are therefore
split into dedicated subphase documents. Phase 0 and Phase 4 remain single
cross-service phases because their deliverables are governance and gate reports
rather than service refactors.

| Parent phase | Split required | Reason |
|---|---|---|
| Phase 0: Cross-Service Baseline | No | Small, cross-cutting setup phase; internal steps are sufficient. |
| Phase 1: Management API Audit | Yes | Route, service, contract, error, migration, and test work are independent risk areas. |
| Phase 2: Optimizer Audit | Yes | Strategy contracts, pricing sources, fetchers, formulas, API contracts, and tests must be reviewed independently. |
| Phase 3: Deployer Audit | Yes | API, provider, Terraform/workspace, logs, permissions, simulator, and tests have different owners and risks. |
| Phase 4: Service Quality Gate | No | Final consolidated gate; implementation work happens in prior phases. |

## Execution Order

1. Start with Phase 0 so every subproject uses the same audit language and
   verification gates.
2. Audit Management API next because it is the Flutter-facing orchestration
   boundary and determines contract shape for the rest of the platform.
3. Audit Optimizer before deeper Pricing Review UI work, because cost
   calculation, pricing evidence, and strategy contracts drive what the UI can
   safely display.
4. Audit Deployer before simulator/log-trace and real deployment hardening,
   because provider execution, workspace handling, logs, and permissions carry
   the highest operational risk.
5. Finish with the cross-service quality gate before calling the service layer
   production-ready or thesis-ready.

## Out Of Scope For This Roadmap

- Running live cloud E2E tests by default.
- Replacing Terraform with another IaC tool.
- Rewriting all service modules purely for aesthetics.
- Introducing a full enterprise platform stack beyond thesis scope.
- Changing the Flutter UI directly; Flutter has its own architecture roadmap.

## Readiness

This roadmap is ready for phase-by-phase implementation planning. Each phase
must be reviewed before implementation, then implemented, verified, and
committed independently.
