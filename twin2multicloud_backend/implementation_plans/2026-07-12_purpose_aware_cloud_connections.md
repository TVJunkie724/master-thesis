# Purpose-Aware CloudConnections

## Issue

GitHub: #6

## Status

Approved for implementation after architecture and builder review on
2026-07-12. This plan is the required backend prerequisite for the Profile
Cloud Accounts & Access UI.

## Branch

- Branch: `codex/purpose-aware-cloud-access`
- Base: `codex/gcp-tiering-calculation-hardening` at `86b209e`
- Merge strategy: merge commit, never rebase
- Session: `AI-0712-01ff`

## Problem

`CloudConnection` currently represents every stored credential as the same
kind of deployment connection. The `/cloud-access` read model therefore emits
AWS and GCP pricing access as permanently missing even when the user owns a
credential that can fetch prices. Pricing Review can accept an arbitrary
deployment connection id, while the planned Profile UI cannot list, select,
validate, or delete real pricing credentials.

This violates the credential SSOT target because purpose is implicit and the
same identity can accidentally cross pricing and deployment boundaries.

## Final State

```text
CloudConnection
|-- provider: aws | azure | gcp
|-- purpose: pricing | deployment
|-- scope: user
|-- is_default_for_pricing
|-- identity and permission-set metadata
`-- encrypted provider payload

/cloud-access
|-- provider.pricing
|   `-- effective default, public capability, or missing placeholder
|-- provider.pricing_options
|   `-- every user-owned pricing connection, secret-free
`-- provider.deployment
    `-- every deployment connection with Twin binding metadata
```

The database is the SSOT for stored credential purpose. Existing rows migrate
to `purpose=deployment`, `scope=user`, and
`is_default_for_pricing=false`. Azure pricing remains a public capability and
does not create a secret record.

## Domain Contract And Invariants

Add these columns to `cloud_connections`:

| Field | Type | Null | Default | Invariant |
|---|---|---:|---|---|
| `purpose` | string enum | no | `deployment` | `pricing` or `deployment` |
| `scope` | string enum | no | `user` | persisted records in this slice are user-owned |
| `is_default_for_pricing` | boolean | no | false | true only for pricing purpose |
| `last_used_at` | datetime | yes | null | updated after successful pricing use |

Required rules:

1. Admin/bootstrap credentials are never accepted as a purpose.
2. Azure pricing uses public access and rejects persisted `purpose=pricing`.
3. AWS/GCP may have multiple pricing connections, but at most one default per
   user/provider.
4. The first AWS/GCP pricing connection becomes default automatically.
5. Creating or patching another pricing connection with
   `is_default_for_pricing=true` atomically demotes the previous default.
6. Unsetting or deleting the default leaves no implicit replacement. Pricing
   remains disabled until the user explicitly selects another default.
   An invalid selected default remains visible as the effective entry with an
   invalid status; the system neither hides it nor substitutes another option.
7. Deployment connections remain bindable to Twins. Pricing connections must
   be rejected by Twin configuration binding and deployment resolution.
8. Pricing refresh rejects deployment-purpose connections, even when provider
   and ownership match.
9. Pricing validation calls only the Optimizer pricing-permission boundary;
   deployment validation continues to call Optimizer and Deployer.
10. Every response remains secret-free and validation messages remain redacted.

## API Contract

### CloudConnection create and update

`POST /cloud-connections/` adds:

```json
{
  "provider": "aws",
  "purpose": "pricing",
  "scope": "user",
  "is_default_for_pricing": true,
  "display_name": "AWS Pricing Reader",
  "aws": {}
}
```

Defaults preserve existing clients:

- omitted `purpose` -> `deployment`
- omitted `scope` -> `user`
- omitted `is_default_for_pricing` -> false, except first pricing connection

`PATCH /cloud-connections/{id}` may update display metadata and
`is_default_for_pricing`. Purpose, scope, provider, auth type, and encrypted
payload are immutable; changing them requires a new connection.

`CloudConnectionResponse` returns the four new secret-free metadata fields.

### Inventory

`GET /cloud-access` stays backward compatible:

- `pricing` remains one effective entry for Pricing Review.
- `pricing_options` is additive and lists all stored pricing connections.
- `deployment` excludes pricing connections.
- missing/default/action metadata is computed from persisted purpose/default
  state, never inferred from display names or fingerprints.
- an effective stored default is returned regardless of validation state so
  that clients can explain and repair invalid access; its status and actions
  prevent refresh until the user validates or replaces it.

### Validation and refresh

- `POST /cloud-connections/{id}/validate` branches by persisted purpose.
- Pricing validation records only the Optimizer result and never reports a
  Deployer failure.
- `POST /optimizer/pricing-refresh/{provider}` accepts only an owned matching
  pricing-purpose connection for AWS/GCP.
- Successful pricing refresh updates `last_used_at` in the same Management API
  lifecycle after the Optimizer result is accepted.

## Persistence And Migration

Add `migrations/add_cloud_connection_purpose.py` with a callable
`migrate(database_url=None) -> list[str]` API matching the current idempotent
migration style.

The migration must:

1. Skip a missing `cloud_connections` table cleanly.
2. Add all four columns when absent.
3. Backfill every existing row to deployment/user/not-default.
4. Create lookup indexes for purpose and default selection.
5. Create a SQLite partial unique index for one pricing default per
   user/provider.
6. Be idempotent and testable against a temporary database path.
7. Never read or rewrite `encrypted_payload`.

Fresh databases enforce the same invariant through SQLAlchemy model metadata.
Service-level atomic demotion provides clear API behavior; the unique index is
the final race-condition guard.

## Ownership And Transaction Boundaries

`CloudConnectionRepository` owns purpose/default queries and bulk default
demotion. `CloudConnectionService` owns create/update invariants and commits one
transaction per command. Routes translate domain errors to existing structured
400/404/409 responses.

`permission_set_version` remains deployment-only metadata in this slice.
Pricing connections reject it at the request boundary and never participate in
deployment permission-set comparison.

`CloudAccessInventoryService` only builds read models. It must not mutate
defaults. `PricingRefreshRunService` validates purpose before decrypting and
marks usage only after a successful provider fetch.

## Error Handling

| Condition | HTTP | Required behavior |
|---|---:|---|
| unsupported purpose/scope combination on create | 422 | Pydantic rejects before service call |
| context-dependent invalid metadata patch | 400 | service rejects without persistence |
| Azure persisted pricing connection | 422 | schema rejects it |
| default requested for deployment | 422 | schema rejects it |
| duplicate/racing default write | 409 | rollback; no partial demotion |
| pricing connection used for Twin binding | 400/422 | binding unchanged |
| deployment connection used for pricing refresh | 400 | no run/fetch starts |
| pricing validation downstream unavailable | existing safe response | no secret echo |
| delete bound deployment connection | 409 | existing behavior preserved |

No error includes credential values, decrypted payloads, or raw downstream
responses.

## Implementation Slices

1. Add model/schema/repository fields and invariant helpers.
2. Add idempotent migration and migration tests.
3. Update create/update/delete/list behavior and focused API tests.
4. Make `/cloud-access` purpose-aware with additive `pricing_options`.
5. Harden Twin binding and pricing refresh purpose boundaries.
6. Add purpose-aware validation and secret-redaction regression tests.
7. Run focused and full Management API test suites.
8. Update credential and provider-access roadmaps plus GitHub #6.

Every slice is required. No compatibility fallback may infer purpose from the
credential contents or display name.

## Test Plan

### Migration

- fresh legacy table receives all columns and backfills existing rows
- rerun is idempotent
- missing table is skipped
- encrypted payload remains byte-for-byte unchanged
- partial unique index rejects two defaults for the same user/provider
- different users/providers may each own a default

### Service and API happy paths

- legacy create without purpose remains deployment
- first AWS/GCP pricing create becomes default
- explicit replacement default atomically demotes old default
- patch can unset and later select a default
- inventory returns effective default and all pricing options
- pricing refresh accepts matching pricing connection
- pricing validation invokes Optimizer only

### Unhappy paths

- Azure pricing persistence rejected
- deployment default flag rejected
- pricing connection rejected by Twin binding
- deployment connection rejected by pricing refresh
- another user's connection remains 404
- bound deployment deletion remains 409
- downstream validation secret echoes remain redacted

### Edge cases

- deleting the default leaves a missing effective pricing entry while retaining
  non-default options
- invalid default is still visible but cannot be used as active pricing access
- inactive Twin bindings do not block deletion
- empty pricing options serialize as an empty list
- permission-set metadata remains deployment-specific and does not make a
  pricing connection outdated
- concurrent/default uniqueness failure rolls back cleanly
- `last_used_at` changes only after successful refresh

No live provider call or cloud deployment E2E is run. Optimizer and Deployer
clients are mocked only in Management API unit/integration-boundary tests.

## Verification

```text
cd twin2multicloud_backend
python -m pytest tests/test_cloud_connection_purpose_migration.py -q
python -m pytest tests/test_cloud_connections.py tests/test_cloud_access.py tests/test_pricing_refresh_runs.py tests/test_config_routes.py -q
python -m pytest tests -q
```

Container equivalent is accepted when local Python dependencies are absent:

```text
docker compose run --rm management-api sh -lc \
  'cd /app && PYTHONPATH=/app pytest tests -q'
```

## Out Of Scope

- Automatic provider bootstrap output split and import (next subphase).
- Persisting admin/bootstrap credentials.
- Credential rotation or secret update in place.
- Profile Flutter UI (implemented only after this contract is green).
- Least-privilege finalization beyond the already versioned pricing/deployment
  permission artifacts.
- Live cloud E2E.

## Definition Of Done

- [x] Existing CloudConnections migrate safely to deployment purpose.
- [x] Purpose/default/scope invariants exist at schema, service, and DB layers.
- [x] `/cloud-access` exposes effective pricing plus all pricing options.
- [x] Twin binding and pricing refresh cannot cross credential purposes.
- [x] Validation is purpose-aware and secret-safe.
- [x] Default replacement is transactional and race guarded.
- [x] Migration, happy, unhappy, edge, ownership, and redaction tests pass.
- [x] Full Management API tests pass (566 tests).
- [x] Bandit and Python compile checks pass.
- [x] No live cloud E2E was run.
- [ ] Roadmaps and GitHub #6 reflect the completed backend prerequisite.
- [ ] Implementation received two review passes with all findings fixed.
