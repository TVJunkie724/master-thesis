# Phase 1: Credential Purpose Model

**Status:** planned
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
| `scope` | enum: `user`, `twin` | yes | Pricing credentials are user-scoped; deployment credentials are usually twin-scoped |
| `provider_account_id` | string? | no | AWS account id or equivalent |
| `provider_project_id` | string? | no | GCP project id |
| `provider_subscription_id` | string? | no | Azure subscription id |
| `identity_label` | string? | no | Human-readable identity, e.g. service account/client/app name |
| `is_default_for_pricing` | bool | yes | Exactly one default per user/provider where applicable |
| `last_validated_at` | datetime? | no | Last successful validation/preflight |
| `last_used_at` | datetime? | no | Last pricing refresh/deployment use |
| `status` | enum | yes | `active`, `needs_validation`, `invalid`, `stale`, `disabled` |

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
        "scope": "user",
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

## Verification

- Migration test for existing deployment CloudConnections.
- Repository/service tests for default-pricing uniqueness.
- API tests verify no secret fields are returned.
- Delete/deactivate behavior remains blocked when a credential is in active use.

## Definition Of Done

- [ ] Schema/migration exists and is idempotent.
- [ ] Existing CloudConnections remain usable.
- [ ] Pricing and deployment purposes are queryable.
- [ ] Default pricing credential uniqueness is enforced.
- [ ] API response is secret-free.
- [ ] Tests cover migration, uniqueness, serialization, and blocked deletion.
