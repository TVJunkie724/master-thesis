# State And Persistence

## State Inventory

| State | Owner | Location | Lifecycle |
|---|---|---|---|
| Management domain data | Management API | `twin2multicloud_backend/data/app.db` bind mount | durable |
| uploaded GLB scene assets | Management API | configured upload directory | durable until twin cleanup |
| JWT/encryption keys | operator/bootstrap | `.secrets/runtime`, mounted read-only | durable, never auto-rotated |
| local cloud compatibility files | local operator | `.secrets/local`, mounted read-only | optional, ignored |
| pricing registry | Optimizer developers | `2-twin2clouds/pricing_registry` | versioned editable SSOT |
| fetched pricing/regions/currency | Optimizer | `2-twin2clouds/json/fetched_data` | generated/evidence snapshot |
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
