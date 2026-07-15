# Implementation Plan: Typed Flutter API Boundaries

## 0. Git Branch

- **Branch name:** `codex/flutter-typed-api-boundaries`
- **Base branch:** `master` at `5c0a2b0`
- **Tracking issue:** GitHub Issue `#72`
- **Merge strategy:** merge commit; no rebase of shared history
- **Mandatory commit slices:** plan, contract models/adapters, wizard and overview
  migration, architecture gate/documentation, review fixes

## 1. Summary

This phase removes broad `Map<String, dynamic>` values from stable Flutter
feature boundaries for twin CRUD, wizard initialization, optimizer persistence,
and twin overview. JSON decoding must happen once in the infrastructure adapter;
feature state and presentation must receive typed, immutable models.

The phase does not attempt to type payloads whose domain is intentionally open:
sanitized provider pricing snapshots, optimizer evidence details, Terraform
outputs, user-authored JSON/YAML/code artifacts, credential submission payloads,
and transport-level SSE envelopes. These values must remain contained in named
model fields and must not be traversed directly by screens or BLoCs.

The visual behavior defined by `FRONTEND_ARCHITECTURE.md` remains unchanged.
This is a contract-safety and separation-of-concerns phase, not a redesign.

## 2. Visual Layout (ASCII)

No visual components are added or removed. Desktop and Web retain the existing
layouts while their data sources become typed.

```text
Dashboard / Wizard / Twin Overview (Desktop and Web)
+------------------------------------------------------------------+
| Existing navigation and responsive layout                        |
|                                                                  |
| Existing loading | loaded | empty | error presentation           |
|                                                                  |
| Existing feature content, now fed only by typed feature models   |
+------------------------------------------------------------------+
```

Contract failures follow the existing error surfaces instead of producing a
partially populated screen:

```text
HTTP 2xx + valid contract  -> existing loaded UI
HTTP 404 optional config   -> existing empty/not-configured UI
HTTP/network failure       -> existing API error UI
HTTP 2xx + invalid JSON    -> visible contract error UI
```

## 3. Widget Tree

The widget hierarchy is unchanged. Only typed constructor inputs and state
accesses are modified.

```text
[REUSE] DashboardScreen
`-- [REUSE] TwinsTable(List<Twin>)

[REUSE] WizardScreen
`-- [MODIFY] BlocProvider<WizardBloc>
    `-- [REUSE] existing workspace/tasks

[REUSE] TwinOverviewScreen
`-- [MODIFY] BlocBuilder<TwinOverviewBloc, TwinOverviewState>
    `-- [MODIFY] TwinOverviewContent(TwinOverviewLoaded)
        |-- [REUSE] TestingUtilitiesPanel(provider: String)
        |-- [REUSE] DeploymentVerificationCard(payload/config strings)
        `-- [MODIFY] TwinOverviewConfigurationReview
            `-- [MODIFY] TwinConfigurationView.fromState(...)
```

## 4. Component Specifications

### 4.1 Contract Models

| File | Required model contract |
|---|---|
| `lib/models/twin.dart` | `Twin` validates required ID, name, lifecycle state, and timestamps; unknown extra fields remain forward-compatible. Demo-only provider and legacy log metadata remain optional compatibility fields. |
| `lib/models/twin_config.dart` | `TwinConfigData`, `BoundCloudConnection`, provider configuration metadata, typed `CalcParams?`, typed `CalcResult?`, and a contained raw optimizer-result payload for lossless re-persistence. |
| `lib/models/optimizer_config.dart` | `OptimizationResultData`, `OptimizerConfigData`, `CheapestPath`, and `ProviderPricingSnapshot`; stable fields are typed, result/evidence and snapshot payloads are immutable named exceptions. |
| `lib/models/pricing_export_snapshot.dart` | `PricingExportSnapshot` validates provider and timestamp metadata while containing the provider-owned pricing payload for persistence. |
| `lib/models/deployer_config.dart` | Existing `DeployerConfigData` remains the canonical deployer read model and gains any response metadata required by consumers without exposing raw response maps. |

All required-field and type violations must throw `FormatException` with a
field-oriented, secret-safe message. Unknown optional response fields must be
ignored. Collections exposed by models must be unmodifiable.

### 4.2 Management API Ports and Adapters

`ManagementApi`, `ApiService`, `DemoManagementApi`, and unit-test adapters must
use the same typed signatures:

```text
getTwins()                         -> Future<List<Twin>>
getTwin/createTwin/updateTwin      -> Future<Twin>
getTwinConfig/updateTwinConfig     -> Future<TwinConfigData>
getTwinConfigResult                -> Future<Result<TwinConfigData>>
calculateCosts(CalcParams)          -> Future<OptimizationResultData>
exportPricing(provider)             -> Future<PricingExportSnapshot>
getOptimizerConfig                -> Future<OptimizerConfigData?>
getDeployerConfig                 -> Future<DeployerConfigData?>
updateDeployerConfig              -> Future<DeployerConfigData>
```

The production adapter must translate an expected `404` for optional optimizer
or deployer configuration into `null`. It must not suppress JSON contract
failures, authorization failures, timeouts, or server errors.

The four unused legacy credential-validation methods that return response maps
must be removed from `ManagementApi`, production, demo, and test adapters. The
active credential workflow remains `CloudConnection` plus the typed
`CloudConnectionValidationResult`.

### 4.3 Wizard Initialization

`TwinEditData` must contain `Twin`, `TwinConfigData`, and
`DeployerConfigData?`. `WizardInitService` must use typed properties only.
Credential hydration must consume the secret-safe `TwinConfigData` provider
metadata; it must not reconstruct or expose secrets. The existing step rollback
rules and raw optimizer payload required for save compatibility must remain.
That payload must be contained by `OptimizationResultData`; `WizardState` must
not expose a raw response map. Calculation and pricing export decoding must move
from the BLoC to the API adapter.

### 4.4 Twin Overview

`TwinOverviewLoaded` must contain `OptimizerConfigData?` and
`DeployerConfigData?` instead of independent response maps. Presentation getters
may expose simple derived values such as the L1 provider, but widgets must not
index response JSON. `TwinConfigurationView` must derive artifacts from typed
deployer fields and typed optimizer fields. Pricing payload rendering is allowed
only through `ProviderPricingSnapshot`.

## 5. Responsive Behavior

No breakpoint or geometry changes are permitted in this phase.

| Breakpoint | Width | Mandatory behavior |
|---|---:|---|
| Wide Desktop | `>= 1440px` | Existing multi-column layout unchanged. |
| Narrow Desktop / Web | `800-1439px` | Existing wrapping and scrolling unchanged. |
| Compact Web | `< 800px` | Existing compact layout unchanged; no new overflow. |

## 6. State Flow (Riverpod and BLoC)

Riverpod continues to own application composition and dashboard queries. BLoC
continues to own the wizard and twin-overview workflows. This phase does not
move ownership between state-management systems.

```text
Widget
  -> Riverpod query or BLoC event
  -> ManagementApi interface
  -> ApiService / DemoManagementApi
  -> dynamic JSON decoding at adapter edge
  -> typed model OR visible FormatException
  -> typed provider/BLoC state
  -> existing widget presentation
```

Optional config flow:

```text
GET optional config -> 200 -> decode typed model -> state
                    -> 404 -> null               -> empty config state
                    -> other error               -> visible error state
```

## 7. Design Tokens

No theme, spacing, color, typography, or icon changes are required. Existing
tokens and Material icons remain untouched.

## 8. Interactions and Animations

No interaction or animation changes are permitted. Existing loading, retry,
empty, and error interactions remain. A malformed successful API response must
take the same visible error path as other load failures and must never be shown
as an empty optional configuration.

## 9. Accessibility

Existing focus order, semantics, keyboard behavior, and contrast remain
unchanged. Typed model failures must surface through existing readable error
components, not console-only output.

## 10. Integration Points

All calls continue through the Management API on the configured base origin.
Direct Flutter calls to Optimizer or Deployer are forbidden.

| Method | Path | Typed response |
|---|---|---|
| GET/POST | `/twins/` | `List<Twin>` / `Twin` |
| GET/PUT | `/twins/{id}` | `Twin` |
| GET/PUT | `/twins/{id}/config/` | `TwinConfigData` |
| PUT | `/optimizer/calculate` | `OptimizationResultData` |
| GET | `/optimizer/pricing/export/{provider}` | `PricingExportSnapshot` |
| GET | `/twins/{id}/optimizer-config` | `OptimizerConfigData?` (`404` means absent) |
| GET/PUT | `/twins/{id}/deployer/config` | `DeployerConfigData?` / `DeployerConfigData` |

No route registrations change.

### Raw Payload Exception Register

| Payload | Owner and constraint |
|---|---|
| Provider pricing snapshots | `ProviderPricingSnapshot.payload`; immutable, display/export only. |
| Optimizer evidence and comparison rows | Existing typed optimizer trace containers; no screen-level map traversal. |
| Terraform outputs | `DeploymentOutputsSnapshot`; sanitized by backend, display only. |
| User-authored JSON/YAML/code | `DeployerConfigData` string and keyed-string fields. |
| Credential submissions | Typed request wrapper containing provider-specific payload; never returned as UI-readable secrets. |
| SSE envelopes | Transport decoder only; converted immediately to typed deployment log events. |

## 11. Test Plan

### Unit: Models and Adapters

- Happy: decode complete twin, twin config, optimizer config, and deployer config.
- Happy: decode calculation result and all three pricing export snapshots at the adapter edge.
- Happy: ignore unknown additive fields and preserve named unstructured payloads.
- Unhappy: reject missing required IDs/names/timestamps and wrong field types.
- Unhappy: reject unknown lifecycle/provider values and malformed nested objects.
- Edge: null optional optimizer/deployer config via `404`.
- Edge: `401`, `403`, `500`, timeout, and malformed `200` must propagate.
- Edge: date offsets normalize without losing the instant.
- Edge: empty optional artifact collections become immutable empty collections.
- Edge: demo adapter returns the same typed contracts as production.

### Unit: Feature State

- Wizard create/edit initialization preserves current step rollback behavior.
- Canonical CloudConnection bindings hydrate inherited credential metadata only.
- Missing optimizer result rolls a saved step back without hiding decode errors.
- Twin overview exposes project/resource names, L1 provider, artifacts, pricing,
  and simulator context without dynamic indexing.
- Optional absent configs preserve existing empty states.

### Widget/Provider Regression

- Dashboard renders typed twin rows and sorting/provider metadata still works.
- Twin overview renders verification inputs and configuration artifacts.
- Existing loading, error, empty, retry, and demo scenarios remain green.

### Safe Verification Commands

```bash
cd twin2multicloud_flutter
dart format --output=none --set-exit-if-changed lib test
flutter analyze
flutter test
flutter test integration_test/management_api_readiness_test.dart \
  --dart-define-from-file=config/dev.example.json
flutter build web --release --dart-define-from-file=config/dev.example.json
flutter build macos --debug --dart-define-from-file=config/dev.example.json
```

The read-only Docker integration suite must additionally decode the twin list
and, when at least one twin exists, its twin/config/optional optimizer/deployer
read models with hard field assertions. An empty twin list must remain a valid
asserted state, not a skipped failure. Tests that deploy cloud resources remain
forbidden and must not be run in this phase.

## 12. Definition of Done

- [ ] All stable twin/config/optimizer/deployer read boundaries are typed.
- [ ] Cost calculation and pricing export responses are decoded before entering BLoC state.
- [ ] Wizard and twin-overview BLoC state expose no raw API response maps.
- [ ] Screens/widgets perform no dynamic JSON traversal for these workflows.
- [ ] Expected optional `404` is distinguished from contract and service errors.
- [ ] Contract failures are visible, field-oriented, secret-safe, and tested.
- [ ] Raw payload exceptions are contained and documented.
- [ ] Production, demo, and test adapters implement identical typed ports.
- [ ] Model, adapter, BLoC, provider, widget, and demo tests are green.
- [ ] `flutter analyze` reports zero issues.
- [ ] Full `flutter test` passes.
- [ ] Web release and macOS debug builds pass.
- [ ] No direct Optimizer/Deployer call is introduced.
- [ ] Phase documentation and Issue `#72` contain verification evidence.
- [ ] User-owned Azure pricing data remains untouched.
