---
title: "Phase 3.5 Review: Deployer Permissions Preflight"
description: "Review evidence and implementation outcome for credential preflight fail-closed behavior."
tags: [deployer, permissions, preflight, security, review]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 3.5 Review: Deployer Permissions Preflight

## Result

Status: Complete.

Deployment credential preflight now fails closed before Terraform starts. A
provider checker must return `status == "valid"` for every configured provider.
`partial`, `invalid`, `check_failed`, `sdk_missing`, `error`, and unknown
statuses block deployment with a sanitized, actionable error.

## Permission Checker Matrix

| Provider | Checker | Credential source | Live behavior | No-live test boundary |
|---|---|---|---|---|
| AWS | `api.credentials_checker.check_aws_credentials` | `config_credentials.json["aws"]` | STS/IAM permission inspection | Patched checker result in unit tests. |
| Azure | `api.azure_credentials_checker.check_azure_credentials` | `config_credentials.json["azure"]` | Entra/RBAC role inspection | Patched checker result in unit tests. |
| GCP | `api.gcp_credentials_checker.check_gcp_credentials` | `config_credentials.json["gcp"]` | Service account/project/API inspection | Patched checker result in unit tests. |

## Preflight Status Contract

| Checker status | Deployment behavior |
|---|---|
| `valid` | Continue deployment. |
| `partial` | Block deployment; required permission state is incomplete. |
| `invalid` | Block deployment; credentials or permissions are unusable. |
| `check_failed` | Block deployment; permission state is unknown. |
| `sdk_missing` | Block deployment; required checker dependency is unavailable. |
| `error` | Block deployment; checker failed. |
| any unknown status | Block deployment; fail closed. |

GCP provider names are normalized before preflight, so both `google` and `gcp`
trigger GCP credential validation.

## Credential-Purpose Mapping

| Purpose | Credential class | Persistence decision |
|---|---|---|
| Deployment execution | Twin-scoped deployment credentials | Stored through the Credentials SSOT, not generic project file APIs. |
| Pricing fetch | Minimal pricing/read credentials | Planned as profile-scoped credentials separate from deployment credentials. |
| Bootstrap/admin setup | Temporary admin credentials | Not persisted by this deployer phase; bootstrap flow remains a separate credential architecture topic. |

## Least-Privilege Gap Register

| Gap | Status |
|---|---|
| Final AWS least-privilege policy for every Terraform and SDK action | Open for live verification after refactors. |
| Final Azure custom role action list, including publishing credentials and diagnostic cleanup | Open for live verification after refactors. |
| Final GCP service account roles and API enablement requirements | Open for live verification after refactors. |
| Pricing-fetch credentials separate from deployment credentials | Planned in Pricing/UI credential roadmap. |

## Implemented Boundary

- `_validate_credentials()` now normalizes `google` to `gcp`.
- `_validate_credentials()` raises on every non-`valid` checker status.
- Checker messages are sanitized before entering exceptions.
- Missing checker SDK imports fail closed instead of silently skipping preflight.

## Files Changed

| File | Change |
|---|---|
| `3-cloud-deployer/src/providers/terraform/deployer_strategy.py` | Added fail-closed preflight evaluation, GCP alias normalization, sanitized messages, and SDK-missing blocking. |
| `3-cloud-deployer/tests/unit/terraform/test_preflight_validation.py` | Added no-live tests for valid, partial, sdk-missing, GCP alias, and redacted checker messages. |

## Verification

Targeted Docker verification:

```bash
docker run --rm \
  -v /Users/caroline/.codex/worktrees/01ff/master-thesis/3-cloud-deployer:/app \
  -w /app \
  -e PYTHONPATH=/app \
  3cloud-deployer:latest \
  python -m pytest \
    tests/unit/terraform/test_preflight_validation.py \
    tests/unit/core_tests/test_deployment_contracts.py \
    -q
```

Result:

```text
14 passed
```

## Review Findings

No open findings remain for Phase 3.5.

Residual work remains intentionally open for future live verification:

- Provider-specific least-privilege policy finalization.
- Bootstrap generation of minimal deployment and pricing credentials.
- UI exposure of credential purpose/account and pricing-fetch credential choice.
