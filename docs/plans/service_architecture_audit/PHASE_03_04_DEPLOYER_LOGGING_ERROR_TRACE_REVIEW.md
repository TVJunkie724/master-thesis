---
title: "Phase 3.4 Review: Deployer Logging Error Trace"
description: "Review evidence and implementation outcome for deployment stream redaction and trace semantics."
tags: [deployer, logging, errors, trace, redaction, review]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 3.4 Review: Deployer Logging Error Trace

## Result

Status: Complete.

Deployment stream events now sanitize secret-like log messages, error messages,
and Terraform complete-event outputs at the typed event-contract boundary.
Failure events also expose a user-safe `error_category`. This protects
Management API and Flutter consumers without requiring each route to remember
redaction or classification rules.

## Deployment Event Taxonomy

| Event | Required fields | Purpose |
|---|---|---|
| `log` | `event`, `operation`, `message` | User-visible progress line for deploy/destroy execution. |
| `complete` | `event`, `operation`, `success`, optional `outputs` | Terminal success event with sanitized Terraform outputs. |
| `error` | `event`, `operation`, `success`, `error`, `error_category` | Terminal failure event with sanitized user-safe error text and category. |

The current event contract preserves the existing SSE wire shape. Correlation
fields for project/provider/layer/phase are documented as the next trace-depth
extension, but were not added to avoid breaking existing consumers in this
slice.

## Error Categories

| Category | Trigger examples |
|---|---|
| `validation` | invalid config, schema, validation failures |
| `packaging` | package, bundle, ZIP build failures |
| `terraform` | Terraform plan/apply/destroy failures |
| `provider_sdk` | AWS/Azure/GCP SDK or provider-specific runtime failures |
| `cleanup` | SDK fallback cleanup failures |
| `permission` | permission, forbidden, unauthorized, denied, credential failures |
| `timeout` | timeout and timed-out failures |
| `internal` | default category for unexpected failures |

## Redaction Rules

| Surface | Rule |
|---|---|
| Log messages | Any message containing secret markers such as `secret`, `token`, `password`, `api_key`, or `connection_string` is replaced with a generic redacted message. |
| Error messages | Same sanitizer as log messages. |
| Terraform complete outputs | Output names classified as `redacted` by `terraform_output_policy.py` return `[REDACTED]`. |
| Safe outputs | Endpoint/name/URL/instruction outputs remain visible. |
| Internal-only outputs | Values remain unchanged in this slice; Phase 4 decides whether API response profiles split user-facing versus internal outputs. |

## Implemented Boundary

`src.api.models.deployment.DeploymentStreamEvent` now owns sanitization:

- `DeploymentStreamEvent.log()` sanitizes log messages.
- `DeploymentStreamEvent.failure()` sanitizes error messages.
- `DeploymentStreamEvent.failure()` classifies errors into `error_category`.
- `DeploymentStreamEvent.complete()` sanitizes Terraform outputs.

The deployment routes still stream the same event shapes, but sensitive values
cannot pass through the typed event constructors.

## Management API Compatibility Notes

- Existing SSE event names and JSON keys are preserved.
- Flutter/Management API clients can keep parsing `log`, `complete`, and
  `error` events without migration.
- Consumers should treat `[REDACTED]` as an intentional value, not as a missing
  field.
- Future correlation fields should be additive and optional for clients.

## Files Changed

| File | Change |
|---|---|
| `3-cloud-deployer/src/api/deployment_trace.py` | Added deployment message sanitizer, Terraform output sanitizer, and error classifier. |
| `3-cloud-deployer/src/api/models/deployment.py` | Applied sanitization in typed stream-event constructors. |
| `3-cloud-deployer/tests/unit/core_tests/test_deployment_contracts.py` | Added stream contract redaction tests. |
| `3-cloud-deployer/tests/api/test_deployment_routes.py` | Added API-level stream redaction regression test. |

## Verification

Targeted Docker verification:

```bash
docker run --rm \
  -v /Users/caroline/.codex/worktrees/01ff/master-thesis/3-cloud-deployer:/app \
  -w /app \
  -e PYTHONPATH=/app \
  3cloud-deployer:latest \
  python -m pytest \
    tests/unit/core_tests/test_deployment_contracts.py \
    tests/api/test_deployment_routes.py \
    -q
```

Result:

```text
18 passed
```

## Review Findings

No open findings remain for Phase 3.4.

Residual work is intentionally assigned to later phases:

- Correlation IDs and richer phase/layer metadata should be additive after
  Management API stream consumption is finalized.
- Full user-facing versus internal Terraform output profiles belong in the final
  cross-service quality gate.
