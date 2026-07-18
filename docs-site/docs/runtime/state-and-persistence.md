# State And Persistence

## State Inventory

| State | Owner | Location | Lifecycle |
|---|---|---|---|
| Management domain data | Management API | `twin2multicloud_backend/data/app.db` bind mount | durable |
| uploaded GLB scene assets | Management API | configured upload directory | durable until twin cleanup |
| JWT/encryption keys | operator/bootstrap | `.secrets/runtime`, mounted read-only | durable, never auto-rotated |
| local cloud compatibility files | local operator | `.secrets/local`, mounted read-only | optional, ignored |
| pricing registry | Optimizer developers | `2-twin2clouds/pricing_registry` | versioned editable SSOT |
| pricing baseline seed | Optimizer developers | `2-twin2clouds/json/pricing_catalog_baselines` | versioned, reviewed, read-only |
| runtime pricing catalogs | Optimizer | `optimizer_pricing_catalogs` volume | durable immutable snapshots plus atomic regional pointers |
| fetched regions/currency | Optimizer | `2-twin2clouds/json/fetched_data` | replaceable local cache |
| deployment template | Deployer developers | `3-cloud-deployer/templates/digital-twin` | versioned source |
| legacy/example template material | Deployer history | `3-cloud-deployer/upload/template` | protected compatibility/provenance |
| Deployer project definitions | Deployer | `3-cloud-deployer/upload/<project>` in source bind | durable non-secret project definition |
| Terraform/device runtime outputs | Deployer | `deployer_runtime_state` volume | durable private operation state |
| staged operation package | Deployer | private temporary package root | short-lived, one-use token-scoped |
| deployment workspace | Deployer | secure temporary directory | ephemeral per operation |
| generated Flutter dev config | root script | `twin2multicloud_flutter/config/dev.json` | local, ignored, replaceable |
| demo fixtures | Flutter | `lib/demo` | versioned deterministic data |

## Management Database

SQLite holds application truth: users, twins, configurations, file versions,
CloudConnections, calculation runs/results, pricing refresh/review records, deployment
preflight/history/logs, and credential security events. Startup creates missing tables
and applies explicit idempotent migrations to existing databases.

Calculation runs and optimizer projections persist only
`provider-pricing-catalog-context.v1`: one exact immutable reference for AWS,
Azure, and GCP. Full pricing payloads remain in the Optimizer catalog volume.
Legacy provider snapshot/timestamp columns may remain after the non-destructive
migration, but live readiness, calculation, evidence, and deployment selection
never read them.

Modern successful calculation runs also persist one immutable
`resolved-deployment-specification.v1`, its digest, compatibility state, and
selection timestamp. The Management API permits at most one selected run per twin.
Creating a newer run does not transfer the older selection. Flutter and deployment
readiness therefore use the newest run for review, while the Deployer receives only
the explicitly selected compatible run through `DeploymentManifest v2`.
Flutter snapshots workload inputs, the result projection, and deployment run as one
unit. Input changes invalidate that unit; discard restores the complete saved unit,
so the UI cannot combine values from different calculations.

Deleting the database deletes durable application history and encrypted credentials.
Deleting the encryption key without first re-encrypting CloudConnections makes those
records unreadable.

## Deployer State

Terraform state and provider-generated device/simulator material are needed for destroy
and follow-up operations. The Deployer migrates legacy outputs out of visible upload
projects, restores private state into the short-lived operation package, and synchronizes
allowlisted outputs back to the named-volume state store. Do not manually copy complete
workspaces back into runtime projects.

## Backup Considerations

For a coherent local backup, stop mutating operations and preserve together:

- the Management API database;
- the exact `ENCRYPTION_KEY` used for its CloudConnections;
- the Deployer runtime-state volume if live deployments must later be destroyed;
- versioned registry/template source from Git.

Credential audit retention and production backup policy are operator responsibilities.
The Optimizer pricing volume is also part of a reproducible audit backup when
calculation reference sets point to runtime catalogs newer than the committed baseline.
Catalog documents contain public pricing evidence only; credentials and
account-scoped observations are forbidden.
