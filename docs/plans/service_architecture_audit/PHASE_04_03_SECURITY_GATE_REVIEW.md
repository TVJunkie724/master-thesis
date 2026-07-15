---
title: "Phase 4.3 Review: Cross-Service Security Gate"
description: "Bandit, secret-shape, and redaction-oriented security evidence for the service layer."
tags: [quality, security, bandit, secrets, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

# Phase 4.3 Review: Cross-Service Security Gate

## Result

Status: Complete.

The cross-service security gate is established with a strict high-severity
policy: high-severity Bandit findings must be zero before a service slice can be
called thesis-ready. Low and medium findings remain visible as residual risk for
later targeted hardening instead of being hidden through blanket skips.

## Fixes Applied

| Finding | Resolution |
|---|---|
| Deployer used MD5 for content-based package versioning. | Replaced MD5 with SHA-256 in `src/providers/terraform/package_builder.py`. |
| Optimizer Docker image did not include Bandit. | Added `bandit` to `2-twin2clouds/requirements.txt` and rebuilt the image. |
| Optimizer OpenAPI example exposed credential-shaped AWS values. | Removed the secret example value and regenerated the OpenAPI snapshot. |

## Bandit Gate

High-severity commands:

```bash
docker run --rm -v "$PWD/twin2multicloud_backend:/app" -w /app -e PYTHONPATH=/app master-thesis-management-api:latest python -m bandit -r src -lll -q
docker run --rm -v "$PWD/2-twin2clouds:/app" -v "$PWD/config.json:/config/config.json:ro" -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m bandit -r api backend rest_api.py -lll -q
docker run --rm -v "$PWD/3-cloud-deployer:/app" -w /app -e PYTHONPATH=/app 3cloud-deployer:latest python -m bandit -r src rest_api.py app.py -lll -q
```

Result: all three commands passed.

All-severity inventory:

| Service | High | Medium | Low | Notes |
|---|---:|---:|---:|---|
| Management API | 0 | 0 | 0 | Full `/app/src` Bandit scan is clean; line-specific `# nosec B105` comments document false-positive count/regex literals. |
| Optimizer | 0 | 0 | 0 | Clean after removing credential-shaped example value. |
| Deployer | 0 | 0 | 0 | Clean after [#106](https://github.com/TVJunkie724/master-thesis/issues/106): HTTPS-only runtime boundaries, allowlisted Terraform/simulator commands, sanitized diagnostics, and line-specific suppressions only after validation. |

## Secret And Artifact Checks

OpenAPI and Phase 4 artifacts were scanned for credential-shaped values:

```bash
rg -n "AKIA[0-9A-Z]{16}|BEGIN PRIVATE KEY|private_key_id\"\\s*:\\s*\"[^<]|client_secret\"\\s*:\\s*\"[^<]|refresh_token\"\\s*:\\s*\"[^<]|secret_access_key\"\\s*:\\s*\"[^<]" docs/contracts/openapi/*.openapi.json
```

Result: no credential-shaped values in generated OpenAPI snapshots.

## Regression Verification

Deployer safe suite after provider-runtime hardening:

```text
1175 passed, 1 skipped; warnings treated as errors
```

Optimizer safe suite after OpenAPI example cleanup:

```text
375 passed, 1 warning
```

## Acceptance Review

| Criterion | Result |
|---|---|
| No live credential material is committed or emitted by generated artifacts. | Passed |
| Credential-shaped examples use neutral examples or omit secret values. | Passed |
| User-facing errors remain covered by existing redaction/security tests. | Passed |
| All-severity Bandit findings are zero across all services. | Passed |

## Residual Risk

The Deployer provider-runtime findings were resolved by
[#106 Harden Deployer provider-runtime security findings](https://github.com/TVJunkie724/master-thesis/issues/106).
Live-cloud behavior remains outside this safe gate and is tracked separately by
the E2E and least-privilege issues.
