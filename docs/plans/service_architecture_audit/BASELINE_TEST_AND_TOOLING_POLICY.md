---
title: "Service Test And Tooling Policy"
description: "Baseline policy for safe Python service verification, tooling, and E2E exclusion."
tags: [tests, tooling, security, docker]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md
- docs/plans/service_architecture_audit/phases/PHASE_00_CROSS_SERVICE_BASELINE.md
- ONBOARDING.md section "Tests"
- README.md section "Daily Usage"
- compose.yaml
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Service Test And Tooling Policy

This policy defines safe default verification for the three Python services.
It intentionally excludes live cloud E2E tests unless the user explicitly
approves them.

## Default Test Boundary

| Project | Safe default scope | Explicitly excluded by default |
|---|---|---|
| `twin2multicloud_backend` | Unit and integration tests under `twin2multicloud_backend/tests/` that use local DB/test clients. | Tests that trigger real deployment or cloud resources. |
| `2-twin2clouds` | Unit and integration tests under `2-twin2clouds/tests/` that do not create cloud resources. | Provider calls that incur cost or require live resource creation. |
| `3-cloud-deployer` | Unit/API/integration tests excluding `3-cloud-deployer/tests/e2e/`. | All E2E scenarios, Terraform apply/destroy against cloud, generated `.build` state under E2E. |

## Safe Commands

These commands are the target documented verification commands. They may need
container availability or dependency installation before execution.

```bash
docker compose ps
docker compose run --rm management-api sh -lc 'cd /app && PYTHONPATH=/app python -m pytest tests/ -q'
docker compose run --rm 2twin2clouds sh -lc 'cd /app && PYTHONPATH=/app python -m pytest tests/ -q'
docker compose run --rm 3cloud-deployer sh -lc 'cd /app && PYTHONPATH=/app python -m pytest tests/ --ignore=tests/e2e -q'
```

## Static And Security Tooling Target

| Tooling area | Target |
|---|---|
| Formatting/linting | Adopt a per-service or root `pyproject.toml` policy before enforcing format changes. |
| Type checking | Introduce mypy or pyright incrementally only after service boundaries stabilize. |
| Security scanning | Use Bandit for Python source while excluding tests, generated E2E state, and provider function bundles where appropriate. |
| Dependency scanning | Add a documented dependency audit command once the Python dependency manager strategy is stable. |
| Contract checks | Use OpenAPI/schema snapshots or explicit response-model tests for Flutter-facing and cross-service endpoints. |

## E2E Approval Rule

E2E tests that can create, mutate, or delete cloud resources require explicit
user approval for the exact provider/scenario. A phase can prepare E2E command
documentation, but cannot execute those commands as default verification.

## Failure Policy

- If a safe unit/integration test fails because of the current phase, fix it in
  the same phase before commit.
- If a safe test fails because of a pre-existing unrelated issue, record it in
  the phase review and do not hide it.
- If a command cannot run because Docker or dependencies are unavailable, record
  the blocker and provide the exact command that should be run when available.
