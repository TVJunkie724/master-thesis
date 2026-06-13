# Phase 3: Profile Cloud Accounts & Access UI

**Status:** planned
**Primary owner:** Flutter + Management API
**Depends on:** Phase 1

## Goal

Show user-owned cloud access in the profile/settings area so users can see which
accounts/projects/subscriptions are configured and remove access they no longer
want to use.

## Desktop Layout

```text
Settings
`-- Cloud Accounts & Access
    |-- Provider Filter / Refresh
    |
    |-- AWS Account 123456789012
    |   |-- Pricing read access      Active      Default
    |   |-- Deployment access        Used by Twin A
    |   `-- Validate | Delete
    |
    |-- GCP Project thesis-demo
    |   |-- Pricing read access      Needs validation
    |   |-- Deployment access        Used by Twin B
    |   `-- Validate | Delete
    |
    `-- Azure
        |-- Pricing                  Public API
        `-- Deployment SP            Used by Twin C
```

## Compact Web Layout

```text
Settings
`-- Cloud Accounts & Access
    |-- AWS Account 123456789012
    |   |-- Pricing read access
    |   |-- Actions menu
    |
    |-- GCP Project thesis-demo
    |   |-- Pricing read access
    |   |-- Actions menu
    |
    `-- Azure
```

## Widget Tree

```text
SettingsScreen [MODIFY]
`-- CloudAccessSection [NEW]
    |-- CloudAccessBlocProvider [NEW]
    |-- CloudAccessHeader [NEW]
    |-- CloudAccessProviderFilter [NEW]
    |-- CloudAccountAccessList [NEW]
    |   `-- CloudAccountAccessCard [NEW]
    |       |-- ProviderIdentityHeader [NEW]
    |       |-- AccessPurposeRow [NEW]
    |       `-- CloudAccessActions [NEW]
    `-- CloudAccessEmptyState [NEW]
```

## State Flow

```text
SettingsScreen
  -> CloudAccessLoadRequested
  -> CloudAccessBloc
  -> CloudAccessService
  -> Management API GET /cloud-access
  -> CloudAccessLoaded
```

Deletes and validation use Management API only:

- `POST /cloud-connections/{connection_id}/validate`
- `DELETE /cloud-connections/{connection_id}`

Credential rotation is intentionally not part of this phase because no rotation
contract exists yet. A future rotation feature must define provider-specific
backend behavior before Flutter exposes a rotation action.

## UI Rules

- Secret values are never displayed.
- Delete is blocked or warned when a credential is used by a twin.
- Pricing credential delete is allowed after confirmation; provider refresh
  becomes disabled until a new pricing credential exists.
- Use existing theme tokens from `lib/theme/`.
- Use Material icons only.

## Verification

- Widget tests for loaded, empty, error, delete-blocked, and delete-confirmed
  states.
- Unit tests for BLoC transitions.
- Integration tests against Management API with real HTTP.

## Definition Of Done

- [ ] Profile shows Cloud Accounts & Access.
- [ ] Provider identity metadata is visible.
- [ ] No secret values or file paths are rendered.
- [ ] Validate/delete/blocked states are implemented.
- [ ] Flutter calls only Management API.
- [ ] Unit/widget/integration tests cover the workflow.
