---
title: "Phase 3.2 Review: Deployer Provider Boundary"
description: "Review evidence and implementation outcome for provider responsibility and cleanup boundary hardening."
tags: [deployer, providers, cleanup, boundary, review]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 3.2 Review: Deployer Provider Boundary

## Result

Status: Complete.

Provider deploy and destroy execution is still intentionally owned by the
canonical Terraform strategy, but SDK fallback cleanup no longer leaks
provider-specific function signatures into orchestration code. The new cleanup
registry is the single dispatch boundary for AWS, Azure, and GCP cleanup.

## Provider Responsibility Matrix

| Responsibility | Canonical owner | Phase 3.2 outcome |
|---|---|---|
| Provider registration | `src.core.registry.ProviderRegistry` | Existing contract retained. |
| Provider SDK clients | `src.providers.{aws,azure,gcp}.provider` | Existing provider classes retained. |
| Terraform deploy/destroy | `src.providers.terraform.deployer_strategy.TerraformDeployerStrategy` | Existing canonical deployment path retained. |
| SDK fallback cleanup dispatch | `src.providers.cleanup_registry` | New central boundary implemented. |
| Provider cleanup implementation | `src.providers.{aws,azure,gcp}.cleanup` | Provider-specific behavior retained behind registry. |
| Retry, timeout, and parallel cleanup policy | `TerraformDeployerStrategy` | Retained with no behavior change. |
| API deployment routes | `src.api.deployment` | Remain thin adapters to `src.providers.deployer`. |

## Implemented Boundary

### Cleanup Registry Contract

`CleanupRequest` now captures the provider-agnostic cleanup intent:

- provider identifier,
- full credential bundle,
- twin prefix,
- optional identity-user cleanup flag,
- optional platform user email,
- dry-run flag.

`cleanup_provider_resources()` normalizes provider aliases and maps the contract
to the provider-specific function signatures:

- AWS: `cleanup_identity_user`
- Azure: `cleanup_entra_user`
- GCP: no identity-user cleanup argument

### Orchestration Import Boundary

The following orchestration modules now depend on the cleanup registry instead
of importing provider cleanup modules directly:

- `3-cloud-deployer/src/providers/deployer.py`
- `3-cloud-deployer/src/providers/terraform/deployer_strategy.py`

This keeps provider-specific cleanup signatures out of orchestration code and
gives future permission/preflight hardening one stable extension point.

## Provider Differences Kept Explicit

| Difference | Decision |
|---|---|
| AWS and Azure support optional platform identity-user cleanup. | Keep as explicit `cleanup_identity_user` contract field. |
| GCP cleanup does not accept platform identity-user cleanup. | Registry ignores identity-user fields for GCP. |
| `google` appears in some public/API contexts. | Registry normalizes `google` to `gcp`. |
| Terraform strategy runs cleanup in parallel with retry/timeout. | Keep policy in Terraform strategy; registry only dispatches provider cleanup. |

## Files Changed

| File | Change |
|---|---|
| `3-cloud-deployer/src/providers/cleanup_registry.py` | Added cleanup request contract, provider normalization, supported-provider list, and dispatch boundary. |
| `3-cloud-deployer/src/providers/deployer.py` | Replaced direct provider cleanup imports with registry calls. |
| `3-cloud-deployer/src/providers/terraform/deployer_strategy.py` | Replaced duplicated cleanup dispatcher with registry calls while preserving retry/parallel policy. |
| `3-cloud-deployer/tests/unit/providers/test_cleanup_registry.py` | Added unit tests for dispatch mapping, alias normalization, and unsupported providers. |
| `3-cloud-deployer/tests/unit/core_tests/test_architecture_boundaries.py` | Added regression test preventing direct provider cleanup imports in orchestration. |

## Verification

Targeted Docker verification:

```bash
docker run --rm \
  -v /Users/caroline/.codex/worktrees/01ff/master-thesis/3-cloud-deployer:/app \
  -w /app \
  -e PYTHONPATH=/app \
  3cloud-deployer:latest \
  python -m pytest \
    tests/unit/providers/test_cleanup_registry.py \
    tests/unit/core_tests/test_architecture_boundaries.py \
    tests/unit/core_tests/test_deployment_contracts.py \
    tests/api/test_deployment_routes.py \
    -q
```

Result:

```text
21 passed
```

## Review Findings

No open findings remain for Phase 3.2.

Residual work is intentionally assigned to later subphases:

- Terraform workspace isolation and generated state boundaries: Phase 3.3.
- Sanitized logging/error trace behavior during deploy/destroy: Phase 3.4.
- Permission checker and preflight least-privilege behavior: Phase 3.5.
