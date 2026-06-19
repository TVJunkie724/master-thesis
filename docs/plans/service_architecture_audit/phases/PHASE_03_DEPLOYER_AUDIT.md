---
title: "Phase 3: Deployer Audit"
description: "Audit the Deployer for API/provider/workspace boundaries, Terraform execution, logs, preflight, permissions, simulator, and security."
tags: [deployer, terraform, audit, architecture, quality]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md
- 3-cloud-deployer/src/api/
- 3-cloud-deployer/src/core/
- 3-cloud-deployer/src/providers/
- 3-cloud-deployer/src/terraform_runner.py
- 3-cloud-deployer/src/file_manager.py
- 3-cloud-deployer/src/validator.py
- 3-cloud-deployer/tests/
- 3-cloud-deployer/implementation_plans/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 3: Deployer Audit

## Summary

Audit the Deployer as the operationally riskiest service. This phase should
separate API, provider, Terraform, workspace, validation, simulator, permission,
and logging responsibilities into implementable hardening slices.

## Scope

| In scope | Out of scope |
|---|---|
| API route and provider boundary review | Running live E2E deployments by default |
| Terraform workspace and manifest contract review | Replacing Terraform |
| Permission checker and preflight review | Final provider least-privilege policy if cloud behavior is not yet verified |
| Logging, SSE, and trace review | Full UI simulator redesign |
| File/project/template boundary review | Deleting valid local credentials or upload templates |

## Audit Findings To Address

| Finding | Evidence |
|---|---|
| Deployer has the largest blast radius and code volume. | 163 Python source files under `src`; 36k+ source lines. |
| Several API/provider modules are very large. | `api/validation.py`, `api/functions.py`, `providers/terraform/package_builder.py`, and `providers/terraform/deployer_strategy.py` exceed 1000 lines. |
| Error/log behavior is inconsistent. | 321 broad `except Exception` matches and 338 `print()` matches in `src/`. |
| E2E and generated state must be isolated from default checks. | `tests/e2e/` contains many live cloud scenarios and generated `.build` state. |
| Development Guide contains contradictory command guidance. | It both forbids and rationalizes complex shell patterns and references stale agent tooling. |

## Subphases

| Subphase | Deliverable |
|---|---|
| 3.1 API boundary audit | Classify every API route by project files, validation, deployment, logs, simulator, credentials, verify, and functions. |
| 3.2 Provider boundary audit | Review AWS/Azure/GCP provider responsibilities, naming, cleanup, layer ownership, and shared helper duplication. |
| 3.3 Terraform/workspace audit | Verify manifest contract, ephemeral workspace behavior, tfvars generation, outputs, and file/template boundaries. |
| 3.4 Logging/error/trace audit | Define structured deployment events, redaction, correlation IDs, SSE semantics, and failure taxonomy. |
| 3.5 Permissions/preflight audit | Review AWS/Azure/GCP permission checkers, pricing-access credentials, admin bootstrap assumptions, and least-privilege gaps. |
| 3.6 Simulator/test utility audit | Scope simulator bugs and log-trace issues separately from deployment core. |
| 3.7 Test matrix | Map safe unit/API/integration tests and explicitly exclude live cloud E2E from default verification. |

## Acceptance Criteria

- Deployment API routes do not own provider-specific business logic.
- Provider implementations expose clear contracts for deploy, destroy, package,
  validate, preflight, cleanup, and outputs.
- Runtime project files cannot fall back to legacy templates or local secrets.
- Logs and API errors are sanitized and structured enough for Management API and
  Flutter to consume.
- E2E cloud tests remain opt-in and are never required for ordinary code-quality
  verification.

## Verification Gates

- Static route/provider/dependency review.
- Unit/API/integration test inventory excluding `tests/e2e/`.
- Security review for workspace files, credential paths, logs, and outputs.
- Terraform command boundary review.
- Permission checker and preflight test plan with fake/no-live credentials.

## Roadmap Anchor

[Service Architecture Audit Roadmap](../ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md)
