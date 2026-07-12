# Phase 1: Credential Purpose Model

**Status:** done
**Primary owner:** Management API
**Depends on:** existing `CloudConnection` model and credential SSOT work

## Goal

Make credential intent explicit so pricing read access, deployment access, and
admin/bootstrap material cannot be confused.

## Required Backend Changes

The Management API must extend the credential model with explicit metadata:

| Field | Type | Required | Purpose |
|---|---|---:|---|
| `purpose` | enum: `pricing`, `deployment` | yes | Separates read-only pricing credentials from deployment credentials |
| `scope` | enum: `user` | yes | Persisted credentials are user-owned; Twin scope is derived from bindings |
| `is_default_for_pricing` | bool | yes | Exactly one default per user/provider where applicable |
| `last_validated_at` | datetime? | no | Last successful validation/preflight |
| `last_used_at` | datetime? | no | Last pricing refresh/deployment use |

Provider account/project/subscription identity and access status remain a
secret-free read-model concern. They are derived from `cloud_scope`, validation
metadata, and Twin bindings instead of being duplicated as mutable columns.

## Data Rules

- Admin/bootstrap credentials must not be persisted in this model.
- A user may have multiple pricing credentials per provider, but at most one
  active default pricing credential per provider.
- Azure pricing may be represented as a provider capability with no secret,
  because Azure Retail Prices API is public in the current architecture.
- Existing CloudConnections are migrated to `purpose=deployment` unless they are
  explicitly imported as pricing credentials by a later phase.

## API Contract

Management API must expose typed provider-access data:

```http
GET /cloud-access
```

```json
{
  "schema_version": "cloud-access-inventory.v1",
  "providers": {
    "aws": {
      "pricing": {
        "connection_id": "cc-aws-pricing",
        "purpose": "pricing",
        "scope": "public",
        "provider_account_id": "123456789012",
        "identity_label": "t2mc-pricing-reader",
        "is_default_for_pricing": true,
        "status": "active",
        "last_validated_at": "2026-06-13T00:00:00Z"
      },
      "deployment": []
    },
    "azure": {
      "pricing": {
        "connection_id": null,
        "purpose": "pricing",
        "scope": "user",
        "identity_label": "Public Retail Prices API",
        "status": "active"
      },
      "deployment": []
    }
  }
}
```

Each provider inventory also returns additive `pricing_options`, containing all
stored user-owned pricing connections. `pricing` remains the explicitly
selected default, the Azure public capability, or a missing placeholder. The
API never silently promotes a different option when a default is removed or
invalid.

## Verification

- Migration test for existing deployment CloudConnections.
- Repository/service tests for default-pricing uniqueness.
- API tests verify no secret fields are returned.
- Delete/deactivate behavior remains blocked when a credential is in active use.

## Definition Of Done

- [x] Schema/migration exists and is idempotent.
- [x] Existing CloudConnections remain usable.
- [x] Pricing and deployment purposes are queryable.
- [x] Default pricing credential uniqueness is enforced.
- [x] API response is secret-free.
- [x] Tests cover migration, uniqueness, serialization, purpose boundaries,
      validation, refresh usage, and blocked deletion.

Implementation detail and verification evidence are recorded in
`twin2multicloud_backend/implementation_plans/2026-07-12_purpose_aware_cloud_connections.md`.
