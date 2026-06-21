---
title: "Phase 3.1 Review: Deployer API Boundary"
description: "Review evidence and implementation outcome for the Deployer API boundary hardening slice."
tags: [deployer, api, boundary, review, security]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 3.1 Review: Deployer API Boundary

## Result

Status: Complete.

The Deployer API boundary was reviewed and hardened for the highest-risk
route-level defect in this slice: generic project-file endpoints could expose
runtime credential files if a caller knew the path. The canonical target state is
now explicit:

- API routes remain HTTP adapters.
- Project file browsing may show non-sensitive project artifacts and credential
  examples.
- Runtime credential files are never listed or returned through generic file
  browser APIs.
- Provider execution remains below `src.providers` and is reviewed in Phase 3.2.

## Endpoint Inventory

| Area | Route modules | Boundary owner | Phase decision |
|---|---|---|---|
| Project CRUD and config files | `src/api/projects.py` | Project file service / validator | Hardened credential file access in this slice. |
| Deployment and destroy | `src/api/deployment.py` | `src.providers.deployer` facade | Already covered by route-boundary tests; deeper provider review moves to 3.2. |
| Validation and ZIP extraction | `src/api/validation.py` | Validation services and accessors | Mixed responsibility; inventory moves to later validation hardening after provider/workspace review. |
| Credentials and permission checks | `src/api/credentials.py`, `src/api/*credentials_checker.py`, `src/api/verify.py` | Credential checker services | Moves to 3.5 because provider preflight and least-privilege checks are coupled. |
| Logs and status | `src/api/logs.py`, `src/api/status.py` | Log/status services | Moves to 3.4 because error shape, sanitization, and trace semantics must be reviewed together. |
| Functions | `src/api/functions.py` | Function packaging/update services | Moves to 3.2/3.3 because provider package and Terraform workspace boundaries are involved. |
| Simulator | `src/api/simulator.py` | Simulator package builder | Moves to 3.6. |

## Implemented Boundary

### Protected Project Files

The generic file browser now treats the following files as protected runtime
credential files:

- `config_credentials.json`
- `config_credentials_aws.json`
- `config_credentials_azure.json`
- `config_credentials_google.json`
- `config_credentials_gcp.json`

Files ending in `.example` remain visible and readable, including
`config_credentials.json.example`.

### HTTP Contract

Direct reads of protected files now return `403 Forbidden` instead of file
content. This gives the Management API and Flutter a stable, user-safe response:
the file exists as a runtime secret, but the generic project file API is not the
right boundary for reading it.

### JSON Example Parsing

`*.json.example` files are parsed as JSON when possible. This keeps examples
usable for UI help panels and documentation without exposing runtime secrets.

## Files Changed

| File | Change |
|---|---|
| `3-cloud-deployer/src/file_manager.py` | Added central sensitive-file classification, hid runtime credentials from file trees, blocked direct reads, parsed JSON examples. |
| `3-cloud-deployer/src/api/projects.py` | Mapped protected file reads to `403`; removed stale debug print. |
| `3-cloud-deployer/src/api/error_models.py` | Added documented `403` error response. |
| `3-cloud-deployer/tests/unit/test_file_manager_crud.py` | Added unit tests for tree filtering and protected/readable credential file behavior. |
| `3-cloud-deployer/tests/api/test_project_file_routes.py` | Added API regression tests for hidden runtime credentials and readable examples. |

## Verification

Targeted Docker verification:

```bash
docker run --rm \
  -v /Users/caroline/.codex/worktrees/01ff/master-thesis/3-cloud-deployer:/app \
  -w /app \
  -e PYTHONPATH=/app \
  3cloud-deployer:latest \
  python -m pytest \
    tests/unit/test_file_manager_crud.py::TestProjectFileBrowserSecurity \
    tests/api/test_project_file_routes.py \
    -q
```

Result:

```text
6 passed
```

## Review Findings

No open findings remain for Phase 3.1.

Residual work is intentionally assigned to later subphases:

- Provider extraction and package-builder boundaries: Phase 3.2.
- Terraform workspace and manifest boundaries: Phase 3.3.
- Logs, error trace, and sanitization consistency: Phase 3.4.
- Permission checker and provider preflight hardening: Phase 3.5.
- Simulator utility cleanup: Phase 3.6.
