---
title: "Phase 4.1 Review: Cross-Service Contract Gate"
description: "Review evidence for OpenAPI snapshots and Management API downstream client contract gates."
tags: [quality, contracts, openapi, issue-102]
lastUpdated: "2026-06-26"
version: "1.1"
---

# Phase 4.1 Review: Cross-Service Contract Gate

## Result

Status: Complete.

The service layer now has reproducible OpenAPI snapshots for all three Python
services. The snapshots are generated through Dockerized service runtimes and
stored as contract evidence under `docs/contracts/openapi/`.

As of 2026-06-26, the Management API also has a hard downstream contract gate:
all Optimizer and Deployer HTTP access is centralized in typed client classes,
and route/service code is tested to prevent direct `httpx.AsyncClient`,
`settings.OPTIMIZER_URL`, or `settings.DEPLOYER_URL` usage outside that client
layer.

## Contract Artifacts

| Service | Snapshot | Entrypoint |
|---|---|---|
| Management API | `docs/contracts/openapi/management-api.openapi.json` | `twin2multicloud_backend/src.main:app` |
| Optimizer | `docs/contracts/openapi/optimizer.openapi.json` | `2-twin2clouds/rest_api:app` |
| Deployer | `docs/contracts/openapi/deployer.openapi.json` | `3-cloud-deployer/rest_api:app` |

## Verification Commands

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace master-thesis-management-api:latest python scripts/service_quality_gate/export_openapi.py --service management-api --output docs/contracts/openapi/management-api.openapi.json
docker run --rm -v "$PWD:/workspace" -w /workspace 2twin2clouds:latest python scripts/service_quality_gate/export_openapi.py --service optimizer --output docs/contracts/openapi/optimizer.openapi.json
docker run --rm -v "$PWD:/workspace" -w /workspace 3cloud-deployer:latest python scripts/service_quality_gate/export_openapi.py --service deployer --output docs/contracts/openapi/deployer.openapi.json
python -m json.tool docs/contracts/openapi/management-api.openapi.json >/tmp/management-api.openapi.validated.json
python -m json.tool docs/contracts/openapi/optimizer.openapi.json >/tmp/optimizer.openapi.validated.json
python -m json.tool docs/contracts/openapi/deployer.openapi.json >/tmp/deployer.openapi.validated.json
```

## Summary

| Service | Title | Version | Paths |
|---|---|---:|---:|
| Management API | Twin2MultiCloud Management API | 1.0.0 | 44 |
| Optimizer | twin2clouds REST API | 1.2 | 23 |
| Deployer | Digital Twin Manager API | 2.0 | 42 |

## Additional Verification

```text
python3 -m json.tool docs/contracts/openapi/management-api.openapi.json
python3 -m json.tool docs/contracts/openapi/optimizer.openapi.json
python3 -m json.tool docs/contracts/openapi/deployer.openapi.json
```

Result: all snapshots validated as JSON.

```text
rg -n "AKIA[0-9A-Z]{16}|BEGIN PRIVATE KEY|private_key_id\"\\s*:\\s*\"[^<]|client_secret\"\\s*:\\s*\"[^<]|refresh_token\"\\s*:\\s*\"[^<]|secret_access_key\"\\s*:\\s*\"[^<]" docs/contracts/openapi/*.openapi.json
```

Result: no live-secret or credential-shaped example values found after replacing
the Optimizer AWS example credentials with placeholders.

Optimizer focused regression:

```text
31 passed in 0.41s
```

Management API downstream contract regression:

```text
67 passed in 1.35s
```

Static contract/security gate:

```text
compileall: passed
bandit: passed
git diff --check: passed
raw downstream HTTP sweep: only twin2multicloud_backend/src/clients/base.py contains httpx.AsyncClient
```

## Review Findings

| Finding | Resolution |
|---|---|
| OpenAPI artifacts were not versioned in the repository. | Added deterministic snapshots under `docs/contracts/openapi/`. |
| Service app entrypoints differ between services. | Added an explicit service registry in `scripts/service_quality_gate/export_openapi.py`. |
| Management API test routes must not appear in default contracts. | Export tool sets `ENABLE_TEST_ENDPOINTS=false` for the Management API by default. |
| Optimizer OpenAPI contained credential-shaped AWS example values. | Replaced them with neutral placeholders and regenerated the snapshot. |
| Management API services could still bypass typed clients for permission/config validation. | Added `verify_permissions` and `validate_config_file` client methods, moved credential/config validation through typed clients, and added a contract gate that fails on direct downstream HTTP usage outside `src/clients/`. |
| Downstream client surface could grow silently. | Added an explicit OptimizerClient/DeployerClient public-method contract test. |

## Residual Risk

This gate proves schema availability, typed client centralization, and critical
Management API downstream method/endpoint compatibility. It still does not run
live cloud E2E tests or prove provider-specific permission completeness; those
remain opt-in verification/future hardening items.
