---
title: "Phase 4.6 Review: Residual Risk Register"
description: "Accepted and deferred service-layer risks after the cross-service quality gate."
tags: [quality, risks, roadmap, github, issue-105]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 4.6 Review: Residual Risk Register

## Result

Status: Complete.

The service layer is thesis-ready for safe local development and further
Flutter/application work, with explicit residual risks. It is not being claimed
as live-cloud-production-final because live E2E, provider least-privilege proof,
and UI diagnostic consumption remain intentionally deferred.

Primary GitHub anchor: [#105 Run cross-service quality gate for thesis-ready backend services](https://github.com/TVJunkie724/master-thesis/issues/105)

## Completed Gate Evidence

| Gate | Evidence |
|---|---|
| 4.1 Contract gate | OpenAPI snapshots: Management API 44 paths, Optimizer 23 paths, Deployer 42 paths. |
| 4.2 Test gate | Management API `454 passed`; Optimizer `375 passed, 1 warning`; Deployer `1059 passed, 1 skipped, 1 warning`. |
| 4.3 Security gate | Management API and Optimizer all-severity Bandit clean; Deployer high-severity clean with Low/Medium provider-runtime residuals tracked separately. |
| 4.4 Observability gate | Management SSE persistence failure is logged; deployment stream boundaries reviewed. |
| 4.5 Documentation gate | Root README and ONBOARDING aligned with current safe gates. |

## Residual Risk Register

| Risk | Impact | Mitigation / owner | Issue |
|---|---|---|---|
| Live cloud E2E has not been run in Phase 4. | Safe gates prove service behavior without cost, but not real provider execution. | Run only after explicit approval and stable refactors. | [#107](https://github.com/TVJunkie724/master-thesis/issues/107) |
| Provider least-privilege policies still need final live verification. | Credentials may still require broader permissions than desired. | Finalize versioned permission sets and validate against real providers. | [#79](https://github.com/TVJunkie724/master-thesis/issues/79) |
| Flutter has not consumed the new/cleaned service contracts yet. | UI may still use legacy dynamic maps or miss new diagnostics. | Continue Flutter UI delta/refactor work. | [#72](https://github.com/TVJunkie724/master-thesis/issues/72), [#73](https://github.com/TVJunkie724/master-thesis/issues/73) |
| Pricing review evidence is not yet fully displayed end-to-end. | Users cannot yet inspect all pricing intent/result/candidate evidence in the UI. | Implement Pricing Review traceability flow. | [#100](https://github.com/TVJunkie724/master-thesis/issues/100), [#69](https://github.com/TVJunkie724/master-thesis/issues/69) |
| Deployer still has Low/Medium Bandit findings. | Some subprocess/urllib/template-function boundaries need behavior-aware review. | Treat as targeted hardening, not blanket suppression. | [#106](https://github.com/TVJunkie724/master-thesis/issues/106), [#14](https://github.com/TVJunkie724/master-thesis/issues/14) |
| Management API still uses script-based SQLite migrations rather than Alembic. | Upgrade history is less explicit than enterprise production systems. | Accept for thesis scope; revisit if DB lifecycle grows. | [#102](https://github.com/TVJunkie724/master-thesis/issues/102) |
| Local credential fixture files still exist for compatibility. | Confusion between final Credentials SSOT and local test fixtures remains possible. | Continue credential SSOT and bootstrap work; root docs now call fixtures compatibility-only. | [#6](https://github.com/TVJunkie724/master-thesis/issues/6), [#8](https://github.com/TVJunkie724/master-thesis/issues/8), [#9](https://github.com/TVJunkie724/master-thesis/issues/9), [#10](https://github.com/TVJunkie724/master-thesis/issues/10) |
| Service-specific historical docs still contain legacy references. | Future agents may read stale per-service docs instead of root/roadmap guidance. | Finish docs-site cleanup after app refactors stabilize. | [#1](https://github.com/TVJunkie724/master-thesis/issues/1), [#4](https://github.com/TVJunkie724/master-thesis/issues/4), [#5](https://github.com/TVJunkie724/master-thesis/issues/5) |
| Unified cross-service correlation fields are not on every stream event. | UI diagnostics still require some service-specific handling. | Add additive stream fields with Management API and Flutter consumers together. | [#20](https://github.com/TVJunkie724/master-thesis/issues/20), [#73](https://github.com/TVJunkie724/master-thesis/issues/73) |
| Optimizer full tests can mutate mounted pricing fixtures. | Test runs can dirty the worktree unless generated files are restored. | Move pricing writes to temp fixtures in future Optimizer hardening. | [#103](https://github.com/TVJunkie724/master-thesis/issues/103), [#69](https://github.com/TVJunkie724/master-thesis/issues/69) |

## Live E2E Quarantine

Live E2E remains opt-in only:

- Deployer `tests/e2e/` provider deployments,
- Terraform apply/destroy against AWS, Azure, or GCP,
- tests requiring admin or generated least-privilege cloud credentials,
- Flutter desktop flows that trigger real deployment actions.

Trigger conditions:

- user explicitly approves live E2E,
- credentials and budget are confirmed,
- cleanup plan is defined before execution,
- output logs are captured as thesis evidence.

## Final Assessment

The service architecture audit is complete for local, safe, thesis-ready backend
service work. Remaining work is properly separated into live-cloud validation,
Flutter/UI consumption, pricing-review UX, credential hardening, and docs-site
cleanup.
