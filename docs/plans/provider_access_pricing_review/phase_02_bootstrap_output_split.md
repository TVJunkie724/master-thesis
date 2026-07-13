# Phase 2: Bootstrap Output Split

**Status:** planned
**Primary owner:** Bootstrap scripts + Management API import
**Depends on:** Phase 1

## Goal

When a user bootstraps a cloud provider, create/import separate identities for
pricing read access and deployment access.

## Target Flow

```text
Ephemeral admin/bootstrap input
  -> provider bootstrap artifact
  -> pricing read identity
  -> deployment identity
  -> import pricing identity as user-scoped default CloudConnection
  -> import deployment identity as twin-scoped CloudConnection
  -> discard admin/bootstrap material
```

## Required Behavior

- Bootstrap scripts remain dry-run by default and require explicit `--apply`.
- Scripts must never accept admin secret values as command-line arguments.
- Bootstrap output must separate:
  - `purpose=pricing`
  - `purpose=deployment`
- AWS/GCP pricing identities must be minimal read-only identities for pricing or
  billing catalog APIs.
- Azure pricing output must represent public API access without storing a
  pricing secret.
- Generated local output files must not be overwritten without explicit flags.

## Import Contract

`POST /cloud-bootstrap/import` must accept purpose-aware output:

```json
{
  "provider": "gcp",
  "outputs": [
    {
      "purpose": "pricing",
      "scope": "user",
      "identity_label": "t2mc-pricing-reader",
      "provider_project_id": "thesis-demo",
      "permission_set_version": "pricing-read-v1",
      "connection": {
        "auth_type": "service_account_key",
        "credentials": {}
      }
    },
    {
      "purpose": "deployment",
      "scope": "twin",
      "twin_id": "twin-123",
      "identity_label": "t2mc-deployer",
      "permission_set_version": "deployment-thesis-demo-v1",
      "connection": {
        "auth_type": "service_account_key",
        "credentials": {}
      }
    }
  ]
}
```

Responses must redact secret values and return only imported metadata.

## Verification

- Shell syntax tests for provider bootstrap scripts.
- Static guardrail tests compare pricing permission artifacts with checker
  constants.
- Management API import tests cover mixed pricing/deployment outputs.
- Tests verify admin material is rejected if sent to APIs.

## Definition Of Done

- [ ] Bootstrap artifacts emit purpose-aware outputs.
- [ ] Import persists pricing and deployment credentials separately.
- [ ] Admin credentials are never persisted.
- [ ] Azure pricing remains no-secret/public.
- [ ] Permission-set versions are separate for pricing and deployment.
- [ ] Tests are offline and deterministic.
