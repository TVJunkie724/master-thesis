---
title: "Phase 1.5 Review: Management Persistence And Migration Audit"
description: "Audit review for Management API models, SQLite migration coverage, startup schema creation, and persistence retention rules."
tags: [management-api, database, migrations, persistence, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/subphases/PHASE_01_05_MANAGEMENT_PERSISTENCE_MIGRATION_AUDIT.md
- twin2multicloud_backend/src/models/
- twin2multicloud_backend/migrations/
- twin2multicloud_backend/src/main.py
- twin2multicloud_backend/tests/test_schema_migrations.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1.5 Review: Management Persistence And Migration Audit

## Review Result

Phase 1.5 is implemented for the current SQLite migration posture. Fresh
developer databases continue to use SQLAlchemy `Base.metadata.create_all()`.
Existing SQLite databases now have an explicit idempotent additive-column
upgrade script for current schema columns that were not covered by the older
single-purpose migration scripts.

## Model Matrix

| Model | Table | Persistence role |
|---|---|---|
| `User` | `users` | Local user identity, auth provider linkage, theme preference |
| `DigitalTwin` | `digital_twins` | Twin lifecycle state, soft-delete state, deployment lifecycle timestamps |
| `TwinConfiguration` | `twin_configurations` | Encrypted cloud credential references and wizard Step-1 state |
| `OptimizerConfiguration` | `optimizer_configurations` | Optimizer params, result JSON, cheapest path columns, pricing snapshots |
| `DeployerConfiguration` | `deployer_configurations` | Wizard Step-3 deployer config content and validation flags |
| `Deployment` | `deployments` | Deployment/destroy operation records, outputs, status, legacy log text |
| `DeploymentLog` | `deployment_logs` | Ordered SSE/log events by session and operation type |
| `FileVersion` | `file_versions` | Versioned binary file content attached to a twin |

## Migration Coverage

Existing historical scripts:

| Script | Coverage |
|---|---|
| `add_deployment_lifecycle_columns.py` | `digital_twins.deployed_at`, `digital_twins.destroyed_at` |
| `add_error_tracking_columns.py` | `digital_twins.last_error` |
| `add_deployment_session_columns.py` | `deployments.session_id`, `deployments.operation_type`, `deployments.error_message` |
| `add_l4_l5_columns.py` | L4/L5 `deployer_configurations` columns |
| `add_requirements_columns.py` | Deployer function requirements columns |

New script:

| Script | Coverage |
|---|---|
| `ensure_current_schema_columns.py` | Current additive columns for `twin_configurations`, optimizer pricing snapshot columns, optimizer `calculated_at`, and `deployment_logs.operation_type` |

## Fresh DB And Upgrade Paths

| Scenario | Command path |
|---|---|
| Fresh local/dev DB | Start Management API; `Base.metadata.create_all(bind=engine)` creates all registered model tables. |
| Existing SQLite DB before current config/pricing/log columns | Run `python -m migrations.ensure_current_schema_columns` with `DATABASE_URL=sqlite:///path/to/db`. |
| Existing SQLite DB missing older historical columns | Run the relevant historical `migrations/add_*.py` scripts, then run `ensure_current_schema_columns.py`. |

The new migration script is additive and idempotent. It skips tables that do not
exist, adds missing columns, and reports `exists` for already migrated columns.

## Persistence Rules

| Data | Rule |
|---|---|
| Cloud credentials | Persist encrypted in `twin_configurations`; API responses expose only configured/validated status and safe metadata. |
| Pricing snapshots | Persist as optimizer calculation evidence in `optimizer_configurations`; source contracts remain governed by Optimizer pricing phases. |
| Deployment outputs | Persist in `deployments.terraform_outputs`; export paths must remain redacted. |
| Deployment logs | Persist ordered log events in `deployment_logs`; deployment stream cleanup retains session history for UI replay and debugging. |
| Uploaded GLB files | Persist on disk under `UPLOAD_DIR/{twin_id}/scene.glb`; soft-delete and explicit delete paths remove the file when possible. |
| Project ZIP uploads | Not persisted as raw upload archives; extracted content is returned to the UI and persisted only through normal config save paths. |

## Verification Evidence

Focused migration verification:

```text
python -m pytest tests/test_schema_migrations.py -q
2 passed, 3 warnings
```

Full Management API verification:

```text
python -m pytest tests -q
296 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| Historical migration scripts cover only selected columns and use inconsistent default database paths. | Added `ensure_current_schema_columns.py` with centralized SQLite URL resolution and current additive-column coverage. |
| Existing SQLite DBs could miss current provider config columns, optimizer pricing snapshot columns, or `deployment_logs.operation_type`. | New migration adds these idempotently and has regression tests. |
| Fresh DB behavior and upgrade DB behavior were implicit. | Documented separate fresh and upgrade paths in this review. |

## Residual Risk

The Management API still uses script-based SQLite migrations rather than a full
Alembic migration history. That remains acceptable for thesis scope, but future
schema changes must add either a dedicated idempotent migration script or extend
the current-schema script with tests in the same commit.
