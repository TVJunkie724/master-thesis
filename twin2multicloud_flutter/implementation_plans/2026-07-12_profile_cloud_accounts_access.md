---
title: "Implementation Plan: Profile Cloud Accounts & Access"
description: "Replace raw credential records in Settings with a compact purpose-aware cloud access workspace."
tags: [flutter, cloud-access, credentials, settings]
lastUpdated: "2026-07-12"
version: "1.0"
---

# Profile Cloud Accounts & Access

**Review status:** Approved for implementation after architect/builder review on
2026-07-12. This plan implements Provider Access roadmap Phase 3 against the
purpose-aware Management API contract from commit `0e32909`.

## 1. Goal And Boundaries

Settings must answer four questions without exposing credential internals:

1. Which provider identities can this user use?
2. Is each identity for pricing or deployment?
3. Which pricing identity is the explicit provider default?
4. Is deletion available or blocked by Twin bindings?

Flutter calls the Management API only. Secret values, payload fingerprints,
raw payload summaries, local file paths, and admin/bootstrap credentials are
never rendered. Credential rotation, bootstrap execution, RBAC, and live cloud
E2E remain out of scope.

## 2. Lean Layout

```text
Cloud accounts & access                                      [refresh]
Read-only pricing and deployment identities.

[ AWS              ] [ Azure            ] [ GCP              ]
[ Pricing: Active  ] [ Pricing: Public  ] [ Pricing: Missing  ]
[ Deployment: 2    ] [ Deployment: 1    ] [ Deployment: 0    ]
[ Account 123...   ] [ Subscription ... ] [ Project demo     ]
[              ... ] [              ... ] [              ... ]

Provider card expanded only on demand:
  Pricing
    AWS Pricing Reader       Active / Default              [...]
  Deployment
    Thesis Deployer          Used by Factory Twin          [...]
```

Default state is stat-card density. Provider access rows are collapsed behind
one disclosure per provider. Row menus contain only applicable commands:
validate, set pricing default, and delete. The header add menu offers Pricing
Access and Deployment Access; Azure omits Pricing because its catalog API is
public. No provider filter is added for only three stable providers.

At widths below the existing pricing-card breakpoint, provider cards stack.
Long labels wrap or ellipsize; actions move into a popup menu. There is no
horizontal scrolling and no nested Card.

## 3. Architecture

```text
SettingsScreen
`-- _SettingsCloudAccessScope (owns bloc lifecycle)
    `-- BlocConsumer<CloudAccessBloc, CloudAccessState>
        `-- CloudAccountsPanel (presentation only)
            `-- CloudAccessProviderCard x3
                `-- CloudAccessPurposeRow xN

CloudAccessBloc
  -> ApiService
  -> GET /cloud-access
  -> POST /cloud-connections/{id}/validate
  -> PATCH /cloud-connections/{id} {is_default_for_pricing}
  -> DELETE /cloud-connections/{id}
  -> POST /cloud-connections/ {purpose, scope=user, provider payload}
```

`CloudAccessBloc` is the command/state owner. Widgets never call `ApiService`
directly. Every successful mutation reloads `/cloud-access`; a failed mutation
keeps the last inventory visible and emits scoped feedback. An in-flight set
prevents duplicate actions for the same connection.

## 4. Contract Changes

- Parse additive `pricing_options` on `CloudAccessProviderInventory`.
- Parse `purpose`, `scope`, `is_default_for_pricing`, and `last_used_at` on
  `CloudConnection` for other consumers.
- `CloudConnectionCreateRequest` sends explicit `purpose` and `scope=user`.
- `ApiService.updateCloudConnection` accepts
  `isDefaultForPricing` without allowing purpose mutation.
- Existing request construction defaults to deployment so Wizard behavior is
  preserved.

## 5. State Contract

Events:

- `CloudAccessStarted`
- `CloudAccessReloadRequested`
- `CloudAccessCreateRequested(request)`
- `CloudAccessValidateRequested(connectionId)`
- `CloudAccessDefaultRequested(connectionId)`
- `CloudAccessDeleteRequested(connectionId)`
- `CloudAccessFeedbackCleared`

State:

- `CloudAccessInventory? inventory`
- `bool isLoading`
- `String? loadError`
- `Set<String> busyConnectionIds`
- `bool isCreating`
- typed success/error feedback

Initial-load errors show a compact retry state. Mutation errors do not replace
loaded content. Delete is disabled when the inventory action list contains
`delete_blocked`; confirmation names the identity and explains the consequence.
Setting a default is available only for non-default pricing options.

## 6. File Ownership

| File | Change |
|---|---|
| `lib/models/cloud_access_inventory.dart` | Parse pricing options |
| `lib/models/cloud_connection.dart` | Purpose-aware response/request metadata |
| `lib/services/api_service.dart` | Default-selection patch support |
| `lib/bloc/cloud_access/*` | New feature state boundary |
| `lib/screens/settings_screen.dart` | Own BLoC lifecycle; remove direct API actions |
| `lib/widgets/cloud_connections/cloud_accounts_panel.dart` | Replace raw record panel with compact inventory UI |
| `lib/widgets/cloud_connections/cloud_connection_create_dialog.dart` | Purpose-specific creation copy/request |
| `lib/providers/twins_provider.dart` | Remove settings-only raw list provider |
| matching model/BLoC/widget/screen tests | Broad regression coverage |

No package, route, color, or spacing dependency is added.

## 7. Verification Matrix

Model tests:

- pricing options parse with complete and missing optional metadata;
- old payloads without pricing options remain compatible;
- create requests emit explicit purpose/scope and preserve GCP validation.

BLoC tests:

- initial load and retry;
- create, validate, set-default, and delete reload inventory;
- mutation failure preserves inventory and exposes safe feedback;
- duplicate same-connection command is ignored;
- independent connection commands retain correct busy state.

Widget/screen tests:

- public Azure, missing pricing, active default, invalid pricing;
- deployment binding labels and blocked delete;
- compact and wide layouts without overflow;
- provider disclosure is collapsed by default;
- create purpose choice, validate, set default, delete confirmation;
- loading, initial error, mutation feedback, and empty deployment states;
- no fingerprint, secret-like values, or raw payload keys are rendered.

Gates:

```text
flutter analyze
flutter test
flutter build web --dart-define-from-file=config/dev.json
flutter build macos --dart-define-from-file=config/dev.json
```

Optional local smoke may call `GET /cloud-access`. It must not validate real
credentials, fetch provider prices, or deploy resources.

## 8. Definition Of Done

- [ ] Settings consumes the purpose-aware inventory SSOT.
- [ ] Three compact provider stat cards remain lean at all breakpoints.
- [ ] Pricing/public/default and deployment/binding states are truthful.
- [ ] Create, validate, default selection, and delete use Management API only.
- [ ] No secret-adjacent technical metadata is rendered.
- [ ] BLoC owns async state, duplicate guards, and uniform error feedback.
- [ ] Model, BLoC, widget, and screen tests cover happy/unhappy/edge states.
- [ ] Analyzer, full tests, and web/macOS builds pass.
- [ ] Provider Access roadmap Phase 3 and Issue #6 are updated.
