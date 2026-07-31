# Implementation Plan: Twin Layer Access Handoff

## 0. Git Branch

- **Branch name:** `codex/phase-8-9a-layer-access`
- **Base branch:** the reviewed Phase 8.9A integrated foundation containing the
  complete-service decision and Phase 8.6 graph resolver; do not branch from
  this documentation-only worktree.
- **Merge strategy:** merge commit; no rebase. The user controls the later
  merge to the repository's integration/default branch.
- **Session/commit prefix:** `[AI-0731-LACC]` for this planning slice. The
  implementation branch must retain that prefix or record its replacement in
  the branch handoff before the first commit.
- **Approval gate:** every step below is mandatory, but builder execution stays
  blocked until the user says **Approved** or **Genehmigt** after plan review.

## 1. Summary

This plan extends the existing Twin Overview so a researcher can use, not just
technically deploy, the selected L4 and L5 services. A deployed
`five-layer-baseline@2` Twin receives two typed sibling cards:

- **L4 Semantic Twin:** AWS IoT TwinMaker console, Azure Digital Twins
  Explorer, or the GCP read-only Twin Explorer;
- **L5 Raw & Rollups:** AWS/Azure Managed Grafana or GCP Grafana OSS.

The cards expose safe HTTPS links, provider/service/authentication context,
content/readiness status, and remediation. GCP Grafana adds one explicit
Viewer-credential rotation and one-time reveal workflow. Generic Terraform
outputs remain separate technical evidence.

Authority:

- [Layer Access concept](../docs/frontend_delta/concepts/CONCEPT_TWIN_LAYER_ACCESS_HANDOFF.md)
- [FR-001](../docs/feature-requests/FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md)
- [Cross-stack feasibility contract](../../docs/plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md)
- `FRONTEND_ARCHITECTURE.md`, Twin Overview/Access & Links direction, corrected
  by the current typed Management API and Riverpod/BLoC composition boundary.

This plan adds no route, embedded provider console, L4-to-L5 path, scene/3D
surface, direct Deployer call, or direct cloud call.

## 2. Visual Layout (ASCII)

### Desktop and wide Web (content width at least 900 px)

```text
+ Twin Overview -------------------------------------------------------------+
| Back to Dashboard                                                          |
| Project name / resource name                                               |
|                                                                            |
| + Deployment readiness --------------------------------------------------+ |
| | Ready | providers | checked at | preflight / cloud accounts            | |
| +------------------------------------------------------------------------+ |
|                                                                            |
| + Layer access -----------------------------------------------------------+ |
| | Inspect semantic state in L4 and raw history/rollups in L5.             | |
| |                                                                          | |
| | + L4 Semantic Twin ----------------+  + L5 Raw & Rollups --------------+ | |
| | | [AWS] IoT TwinMaker   [Ready]    |  | [GCP] Grafana OSS   [Blocked] | | |
| | | Workspace: twin-...              |  | Viewer: poc-viewer-...        | | |
| | | Models, twins, current state,    |  | Dashboard provisioned;       | | |
| | | direct relationships             |  | browser credential required  | | |
| | |                                  |  |                               | | |
| | | [Open Twin UI]                   |  | [Open Grafana] [New password]| | |
| | | Authentication details     [v]   |  | Access details          [v]  | | |
| | +----------------------------------+  +-------------------------------+ | |
| +------------------------------------------------------------------------+ |
|                                                                            |
| + Deployment actions ----------------------------------------------------+ |
| +------------------------------------------------------------------------+ |
| + Testing utilities -----------------------------------------------------+ |
| +------------------------------------------------------------------------+ |
| + Terraform outputs -----------------------------------------------------+ |
| +------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------+
```

The aggregate badge is `Ready` only when resource, access binding, content,
and data probe are ready. `browser_sign_in=unverified` is shown in details and
does not disable Open. A blocked L4 card never disables a ready L5 card or the
Destroy action.

### Compact Web (content width below 900 px)

```text
+ Twin Overview ------------------------------+
| Back to Dashboard                            |
| Project / resource                           |
|                                              |
| + Deployment readiness --------------------+ |
| +------------------------------------------+ |
|                                              |
| + Layer access -----------------------------+|
| | + L4 Semantic Twin ----------------------+||
| | | [Azure] ADT Explorer       [Ready]     |||
| | | semantic content summary               |||
| | | [Open Twin UI                         ]|||
| | | Authentication details           [v]   |||
| | +----------------------------------------+||
| |                                          ||
| | + L5 Raw & Rollups ----------------------+||
| | | [Azure] Managed Grafana    [Ready]     |||
| | | dashboard content summary              |||
| | | [Open Grafana                         ]|||
| | | Access details                   [v]   |||
| | +----------------------------------------+||
| +-------------------------------------------+|
|                                              |
| + Deployment actions ----------------------+ |
| + Testing utilities -----------------------+ |
| + Terraform outputs -----------------------+ |
+----------------------------------------------+
```

Buttons are full width in compact cards. Text wraps; no horizontal scrolling
is introduced. The page keeps the existing 640 px supported lower bound.

### One-time GCP Viewer credential dialog

```text
+ GCP Grafana Viewer credential -----------------------------+
| This password is shown once. Store it securely.             |
|                                                             |
| Username  poc-viewer-...                      [Copy]         |
| Password  **************                  [Show] [Copy]      |
|                                                             |
| Creating another password invalidates this one.              |
|                                                   [Close]    |
+-------------------------------------------------------------+
```

Closing with Escape or Close discards the dialog-local credential. The app
does not offer a download or “show previous password” action.

## 3. Widget Tree

```text
TwinOverviewScreen [MODIFY]
`-- BlocProvider<TwinOverviewBloc> [REUSE]
    `-- TwinOverviewView [MODIFY]
        |-- MultiBlocListener [MODIFY]
        |   `-- pending GCP credential listener [NEW]
        |       `-- GcpGrafanaCredentialRevealDialog [NEW]
        `-- TwinOverviewContent [MODIFY]
            |-- TwinOverviewNavigationHeader [REUSE]
            |-- TwinOverviewNameHeader [REUSE]
            |-- DeploymentReadinessPanel [REUSE]
            |-- LayerAccessPanel [NEW]
            |   |-- panel header / explanation [NEW, private]
            |   |-- loading/error/unsupported presentation [NEW, private]
            |   `-- responsive Row or Column [NEW, private]
            |       |-- LayerAccessCard(layer=L4) [NEW]
            |       |   `-- access details ExpansionTile [NEW, private]
            |       `-- LayerAccessCard(layer=L5) [NEW]
            |           `-- optional GCP Viewer rotation action [NEW]
            |-- DeploymentOperationsPanel [REUSE]
            |-- TestingUtilitiesPanel [REUSE]
            |-- TerraformOutputsCard [REUSE, unchanged]
            |-- DeploymentVerificationCard [REUSE]
            `-- TwinOverviewConfigurationReview [REUSE]
```

State/service tree:

```text
runtime_providers.dart
|-- apiServiceProvider<ManagementApi> [REUSE]
`-- externalAuthLauncherProvider [REUSE]

management_api.dart [MODIFY interfaces]
api_service.dart [MODIFY HTTP adapter]
demo_management_api.dart [MODIFY strict demo parity]
deployment_access.dart [NEW strict DTOs]
twin_overview_event.dart [MODIFY]
twin_overview_state.dart [MODIFY]
`-- LayerAccessViewState [NEW]
twin_overview_bloc.dart [MODIFY]
```

Reuse decisions are binding:

- The existing Twin Overview route, screen shell, BLoC, external launcher,
  spacing/color tokens, `Card`, `Chip`, `ExpansionTile`, and dialog patterns
  must be extended.
- `TerraformOutputsCard` cannot be reused for access because it accepts an
  arbitrary map and derives labels from key names; the feature requires a
  strict two-layer contract, auth/readiness semantics, and one action.
- `DeploymentReadinessPanel` cannot be reused because it represents
  pre-deployment CloudConnection permission readiness, not post-deployment
  resource/content/browser readiness.
- No new state-management, launcher, icon, card, or layout package is allowed.

## 4. Component Specifications

### 4.1 Strict access models

**File:** `twin2multicloud_flutter/lib/models/deployment_access.dart` [NEW]

Required immutable Equatable types:

| Type | Required fields |
|---|---|
| `DeploymentLayer` | exact API values `l4`, `l5` |
| `DeploymentAccessAuthMode` | `aws_identity_center`, `azure_entra`, `gcp_iap`, `generated_viewer` |
| `LayerAccessReadinessValue` | `ready`, `failed`, `pending`, plus browser-only `unverified`/`verified` where valid |
| `LayerAccessReadiness` | `resource`, `accessBinding`, `content`, `dataProbe`, `browserSignIn` |
| `LayerAccessAuth` | `mode`, `principalLabel`, `credentialAction` (`none` or `rotate`) |
| `DeploymentAccessSurface` | layer, `CloudProvider`, serviceId, displayName, HTTPS `Uri`, auth, readiness, immutable capabilities, immutable limitations |
| `DeploymentAccessAvailability` | exact API values `available`, `unsupported` |
| `DeploymentAccessSnapshot` | schema version, twinId, deploymentId, generatedAt, availability, optional reasonCode, immutable surfaces |
| `DeploymentAccessCredential` | schema version, layer, provider, username, password, issuedAt; transient only |

Parsing rules must reject:

- schema versions other than `deployment-access.v1` and
  `deployment-access-credential.v1`;
- duplicate/missing L4 or L5 for `available`; any surface or missing reason for
  `unsupported`;
- provider/auth combinations outside the cross-stack matrix;
- GCP Viewer rotation on any surface except GCP L5;
- blank IDs/labels, non-list capability/limitation values, duplicate entries,
  non-HTTPS URLs, missing host, or URL user-info;
- credential responses other than GCP/L5 and blank username/password;
- any unknown field that matches the shared secret-key denylist. Open payload
  containers are not part of this contract.

`DeploymentAccessCredential.password` must be excluded from `toString` and
Equatable props. The type must expose no JSON serialization method and must not
be written to logs, clipboard history abstractions, preferences, or files.

### 4.2 Management API

**Files:**

- `lib/services/management_api.dart` [MODIFY]
- `lib/services/api_service.dart` [MODIFY]
- `lib/demo/demo_management_api.dart` [MODIFY]

Add to `DeploymentLifecycleApi`:

```dart
Future<DeploymentAccessSnapshot> getDeploymentAccess(String twinId);
Future<DeploymentAccessCredential> rotateGcpGrafanaViewerCredential(
  String twinId,
);
```

The network adapter must use the exact endpoints in Section 10 and parse via
the new strict DTOs. It must not retry the mutating rotation automatically.
The demo adapter must return strict AWS/AWS, Azure/Azure, GCP/GCP, and mixed
fixtures selected by the demo Twin; it must rotate to a new deterministic test
password per request without using a production-like secret.

### 4.3 `LayerAccessViewState`

**File:** `lib/bloc/twin_overview/twin_overview_state.dart` [MODIFY]

```dart
enum LayerAccessViewPhase { idle, loading, ready, unsupported, failed }

class LayerAccessViewState extends Equatable {
  final LayerAccessViewPhase phase;
  final DeploymentAccessSnapshot? snapshot;
  final String? errorMessage;
  final bool rotatingViewerCredential;
  final String? rotationError;
  final int credentialRequestToken;
  final DeploymentAccessCredential? pendingCredential; // transient
}
```

`pendingCredential` follows the existing `SimulatorDownloadViewState`
one-shot pattern: it is excluded from Equatable props, never formatted, and is
cleared immediately after the screen listener captures it. Add
`layerAccess` to `TwinOverviewLoaded`, `copyWith`, and `props` via the safe
`LayerAccessViewState` props only.

### 4.4 BLoC events and behavior

**Files:**

- `lib/bloc/twin_overview/twin_overview_event.dart` [MODIFY]
- `lib/bloc/twin_overview/twin_overview_bloc.dart` [MODIFY]

Add mandatory events:

| Event | Payload | Purpose |
|---|---|---|
| `TwinOverviewRetryLayerAccess` | none | Retry the secret-free GET after an isolated failure |
| `TwinOverviewRotateGcpGrafanaViewerCredential` | none | Start the non-retried rotation operation after confirmation |
| `TwinOverviewAccessCredentialConsumed` | request token | Clear the one-shot pending value without clearing access data |

Initial `TwinOverviewLoad` and refresh must fetch access only when the
authoritative deployment state is `deployed`. The fetch may run in parallel
with generic outputs after the base Twin/config/status calls succeed. Each
request captures the current twin ID and an incrementing generation; late
responses after navigation, destroy, redeploy, or a newer retry are ignored.

Deployment success triggers a canonical access refresh after status/outputs.
Destroy start immediately clears access and pending credentials. A failed
access GET updates only `layerAccess`; it must not convert the whole screen to
`TwinOverviewError`, discard outputs, or block Destroy. Rotation verifies from
the current snapshot that L5 is GCP with `credentialAction=rotate`; all other
states fail locally without HTTP.

### 4.5 `LayerAccessPanel`

**File:** `lib/widgets/twin_overview/layer_access_panel.dart` [NEW]

Constructor:

| Parameter | Type | Required | Default |
|---|---|---:|---|
| `state` | `LayerAccessViewState` | yes | none |
| `onRetry` | `VoidCallback` | yes | none |
| `onOpenSurface` | `ValueChanged<DeploymentAccessSurface>` | yes | none |
| `onRotateViewerCredential` | `VoidCallback` | yes | none |

The public panel is a `StatelessWidget`. Private stateless children render the
header, phase presentation, cards, readiness chip, and details. The panel must
sort by `DeploymentLayer` even though the DTO already rejects duplicates. The
aggregate card is ready only when resource, access binding, content, and data
probe are all `ready`. The Open action requires only resource and access
binding to be ready, so a researcher can inspect a surface whose content/data
probe is degraded. Unverified browser sign-in remains informative.

Dart skeleton:

```dart
class LayerAccessPanel extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Card(
    elevation: AppSpacing.cardElevationLow,
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: _buildPhase(context),
    ),
  );
}
```

Visual requirements:

- outer/card padding `AppSpacing.lg`;
- header/body gaps `AppSpacing.sm`/`AppSpacing.md`;
- two-card gap `AppSpacing.lg`;
- Material icons `Icons.hub_outlined` for L4,
  `Icons.monitor_heart_outlined` for L5, `Icons.open_in_new` for Open,
  `Icons.key_outlined` for rotation, and standard status icons;
- provider accent from `AppColors.getProviderColor` and semantic surfaces from
  `Theme.of(context).colorScheme`;
- typography only from `ThemeData.textTheme` with `copyWith` where necessary;
- no fixed card heights. Both wide cards stretch naturally within the row;
  loading/error content keeps layout stable through normal Card padding.

### 4.6 `TwinOverviewContent`

**File:** `lib/widgets/twin_overview/twin_overview_content.dart` [MODIFY]

Add required callbacks:

| Parameter | Type |
|---|---|
| `onRetryLayerAccess` | `VoidCallback` |
| `onOpenLayerAccess` | `ValueChanged<DeploymentAccessSurface>` |
| `onRotateLayerAccessCredential` | `VoidCallback` |

When `isDeployed`, insert `LayerAccessPanel` immediately after
`DeploymentReadinessPanel` and its section gap. Do not gate it on generic
outputs. Preserve the order and behavior of every existing downstream panel.

### 4.7 Screen integration and external launch

**File:** `lib/screens/twin_overview/twin_overview_screen.dart` [MODIFY]

The screen remains a `ConsumerWidget`/`ConsumerWidget` view unless the
implementation proves the existing `MultiBlocListener` cannot support the
one-shot listener; no stateful conversion is planned.

Required behavior:

1. The credential listener detects a new `credentialRequestToken`, captures
   the transient credential, dispatches `Consumed` immediately, and then opens
   the reveal dialog. It never includes the value in banners or logs.
2. `onOpenLayerAccess` obtains the existing
   `externalAuthLauncherProvider`, synchronously reserves a handle, and
   navigates to the already validated URI. This preserves Web popup behavior.
3. Failed launch closes the handle and dispatches a safe error banner naming
   only layer/service. It does not mutate readiness.
4. GCP rotation is preceded by a confirmation dialog explaining that the old
   Viewer password becomes invalid.

### 4.8 Credential dialogs

**File:**
`lib/widgets/twin_overview/twin_overview_operation_dialogs.dart` [MODIFY]

Add:

- `RotateGcpGrafanaViewerConfirmationDialog` (`StatelessWidget`);
- `GcpGrafanaCredentialRevealDialog` (`StatefulWidget`) with local
  show/hide-password state.

Reveal constructor:

| Parameter | Type | Required |
|---|---|---:|
| `username` | `String` | yes |
| `password` | `String` | yes |

Use `AppSpacing.dialogContentMaxWidth`, standard Clipboard APIs consistent with
`TerraformOutputsCard`, `SelectableText` for username, an obscured read-only
password field, and explicit Copy buttons. No callback returns the password to
the BLoC. The dialog object becomes unreachable on close.

## 5. Responsive Behavior

| Breakpoint | Width | Mandatory behavior |
|---|---:|---|
| Wide Desktop | >= 1440 px viewport | Existing content remains capped at `AppSpacing.maxContentWidthLarge`; L4/L5 cards render as equal `Expanded` siblings |
| Narrow Desktop / Web | 900-1439 px content | Same two-column card layout with wrapping text and no fixed metadata columns |
| Compact Web | < 900 px content | Cards stack L4 then L5; Open/rotation actions stack and stretch to full width; expansion details remain inline |
| Supported lower bound | 640 px viewport | Existing page padding/tokens remain; no clipping, overflow, horizontal scroll, or hidden action |

There is no mobile target. Provider consoles open externally and may have
their own responsive limitations; the app reports only the link and access
state it owns.

## 6. State Flow (BLoC)

### Ownership

- Riverpod owns runtime composition of `ManagementApi` and the platform
  external launcher, matching the current application boundary.
- `TwinOverviewBloc` owns layer-access GET/rotation calls, request generation,
  retries, partial error state, lifecycle clearing, and the one-shot credential
  handoff.
- Widgets render state and emit callbacks/events only.
- Management API owns authorization and the safe read model. Deployer/cloud
  behavior is never called from Flutter.

### Load flow

```text
TwinOverviewView
  -> TwinOverviewLoad(twinId)
  -> TwinOverviewBloc
  -> ManagementApi.getDeploymentAccess(twinId)
  -> GET Management API :5005 /twins/{id}/deployment-access
  -> strict DeploymentAccessSnapshot parser
  -> LayerAccessViewState.ready | unsupported | failed
  -> LayerAccessPanel
```

### Open flow

```text
Open button
  -> presentation callback with typed surface
  -> existing injected ExternalAuthLauncher
  -> external HTTPS browser tab/window
  -> safe success/no state change OR launch-error banner
```

### GCP Viewer rotation flow

```text
New password
  -> confirmation dialog
  -> TwinOverviewRotateGcpGrafanaViewerCredential
  -> TwinOverviewBloc
  -> ManagementApi.rotateGcpGrafanaViewerCredential
  -> POST Management API :5005 .../credentials:rotate
  -> strict transient credential parser
  -> requestToken + pendingCredential (not Equatable/logged)
  -> screen listener captures, dispatches Consumed, opens reveal dialog
  -> dialog closes -> no retained Flutter credential
```

State transitions must be independent:

```text
idle -> loading -> ready
                -> unsupported
                -> failed -> loading (Retry)

ready -> rotating -> ready + one-shot reveal
                  -> ready + rotationError

any -> idle on destroy/not-deployed/new twin generation
```

## 7. Design Tokens

No new theme token is required or permitted unless implementation finds a
demonstrable missing semantic that cannot use the following existing tokens:

- spacing/layout: `AppSpacing.sm`, `md`, `lg`, `iconSm`, `iconMd`,
  `actionButtonHeight`, `dialogContentMaxWidth`,
  `twinOverviewCompactBreakpoint`, `maxContentWidthLarge`,
  `cardElevationLow`;
- provider accents: `AppColors.getProviderColor`;
- readiness: existing `AppColors.success`, `warning`, `error` only where their
  foreground/background contrast passes; otherwise use
  `Theme.of(context).colorScheme` semantic pairs;
- typography: `ThemeData.textTheme.titleMedium`, `titleSmall`, `bodyMedium`,
  `bodySmall`, `labelLarge`.

No literal color, magic spacing, inline `TextStyle(...)`, SVG/icon asset, or
third-party icon package may be introduced.

## 8. Interactions & Animations

| State/action | Mandatory behavior |
|---|---|
| Panel load | Inline `LinearProgressIndicator`; existing page remains interactive |
| GET failure | Inline safe error plus Retry in Layer Access; no global screen error |
| Unsupported historical profile | Informative empty state; no Retry loop unless backend marks transient |
| Partial readiness | Both cards visible; affected Open disabled and exact failed checks expanded by default |
| Open hover/focus/press | Standard Material button feedback; tooltip/label includes layer and service |
| External launch failure | Safe existing top banner; launcher handle closes |
| Rotation | GCP L5 action disables, replaces icon area with token-sized progress, and leaves Open behavior unchanged if current credential still works |
| Rotation failure | Inline error on L5 card with retry action; no password/dialog |
| Rotation success | Reveal dialog opens once; card returns to ready and shows the new rotation timestamp after canonical refresh if returned by the read model |
| Expansion | Standard `ExpansionTile` animation; no custom duration |
| Destroy/redeploy | Access section disappears/returns from canonical state; stale async responses are ignored |

No skeleton library, shimmer, custom animation controller, automatic external
navigation, or automatic password copy is allowed.

## 9. Accessibility

Mandatory focus order:

1. existing Back/Edit/Delete/navigation controls;
2. Deployment Readiness actions;
3. L4 Open, then L4 details;
4. L5 Open, optional New password, then L5 details;
5. existing Deployment Actions and later panels.

Requirements:

- The panel is a semantic container labeled `Layer access` plus aggregate
  readiness.
- Each card label includes layer purpose, provider, service, and readiness;
  color is never the only status signal.
- Disabled Open buttons expose the exact blocking reason in semantics and
  visible text.
- External-link actions include “opens in external browser”.
- Credential dialog autofocuses Close or the first safe Copy action, never the
  password reveal toggle; Escape closes; Tab stays inside the modal.
- Show/Hide announces its resulting state. Copy buttons announce whether they
  copy username or password without reading the password aloud.
- Body text meets 4.5:1 and large/status text 3:1 contrast in light and dark
  themes. Widget tests must exercise both themes.
- Text scaling to 200% at the 640 px lower bound must not overflow; buttons may
  grow vertically.

No custom keyboard shortcut is necessary: standard Tab, Shift+Tab, Enter,
Space, and Escape behavior is sufficient and must be tested.

## 10. Integration Points

### Management API endpoints

| Method | Path | Request body | Response shape | Notes |
|---|---|---|---|---|
| GET | `/twins/{id}/deployment-access` | none | exact `deployment-access.v1` from cross-stack plan | Owner-scoped; 404 for cross-user; no secrets; no automatic polling |
| POST | `/twins/{id}/deployment-access/l5/credentials:rotate` | none | exact `deployment-access-credential.v1` | GCP L5 only; owner-scoped; never automatically retried |

The existing endpoints remain unchanged:

- `GET /twins/{id}/outputs` continues to feed `TerraformOutputsCard`;
- `GET/POST` deployment status/readiness and SSE continue their existing
  lifecycle;
- Flutter performs no call to Deployer port 5004, Optimizer port 5003,
  Terraform, AWS, Azure, or GCP.

### Routes

| Route | Screen | Change |
|---|---|---|
| existing Twin Overview route for `twinId` | `TwinOverviewScreen` | No path/guard change; only post-deployment content changes |

External provider URLs are data, not `go_router` routes. They must pass the DTO
HTTPS validation and open through `externalAuthLauncherProvider`.

### Backend contract dependency

[FR-001](../docs/feature-requests/FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md)
must be implemented and its generated/fixture contract committed before the
Flutter DTO/API step. Flutter must not create a temporary output-key parser.

## 11. Test Plan

All cases below are mandatory. The count exceeds the per-unit baseline because
the feature combines strict secret handling, partial readiness, request races,
external browser behavior, and nine architecture placements.

### 11.1 DTO unit tests

**File:** `test/models/deployment_access_test.dart` [NEW]

| # | Type | Test and hard assertion |
|---:|---|---|
| 1 | Happy | AWS L4/AWS L5 fixture parses; assert exact layers, providers, URIs, auth modes, and readiness |
| 2 | Happy | Mixed GCP L4/Azure L5 fixture parses; assert IAP/Entra modes and immutable lists |
| 3 | Unhappy | Unknown schema throws exact contract error |
| 4 | Unhappy | HTTP URL or URL with user-info throws exact contract error |
| 5 | Edge | Missing L4 throws; no partial snapshot is created |
| 6 | Edge | Duplicate L5 throws |
| 7 | Edge | AWS surface with `gcp_iap` throws |
| 8 | Edge | Rotation action on non-GCP-L5 throws |
| 9 | Edge | Unknown readiness value throws |
| 10 | Edge | Mutable source lists cannot mutate parsed capabilities/limitations |
| 11 | Edge | Secret-like unexpected key throws |
| 12 | Edge | Credential parser accepts exact GCP/L5 and excludes password from `toString`/props |

### 11.2 API adapter unit tests

**File:** `test/services/api_service_deployment_access_test.dart` [NEW or
focused extension]

| # | Type | Test and hard assertion |
|---:|---|---|
| 1 | Happy | GET calls exact owner path once and returns exact snapshot |
| 2 | Happy | POST rotation calls exact path once with no body and returns exact username/password to caller |
| 3 | Unhappy | 403/404 maps through existing safe API error handling |
| 4 | Unhappy | Malformed response fails before reaching BLoC |
| 5 | Edge | Twin ID is encoded by the existing path policy |
| 6 | Edge | Rotation 503 is not automatically retried; assert one request |
| 7 | Edge | Response password is absent from captured diagnostic/log string |
| 8 | Edge | Unsupported historical response is represented by the agreed typed status/error |
| 9 | Edge | Demo adapter returns exact two-surface parity |

### 11.3 BLoC tests

**File:** `test/bloc/twin_overview/twin_overview_layer_access_test.dart` [NEW]

| # | Type | Test and hard assertion |
|---:|---|---|
| 1 | Happy | Initial deployed load emits loading then exact ready snapshot and verifies one GET |
| 2 | Happy | Retry after GET failure returns to ready without refetching Twin/config unnecessarily |
| 3 | Unhappy | GET 500 produces isolated layer-access failure while deployment outputs and Destroy permission remain intact |
| 4 | Unhappy | Rotation 409/500 returns safe inline rotation error and no pending credential |
| 5 | Edge | Draft/configured Twin performs zero access calls and stays idle |
| 6 | Edge | Destroy clears snapshot and pending credential immediately |
| 7 | Edge | Late GET from old twin/generation is ignored |
| 8 | Edge | Older retry response cannot replace newer ready snapshot |
| 9 | Edge | Rotation on AWS/Azure or non-rotate surface performs zero POST calls |
| 10 | Edge | Successful GCP rotation increments token, exposes transient value, and `Consumed` clears it without clearing snapshot |
| 11 | Edge | Duplicate `Consumed` token is harmless and does not clear a newer credential |
| 12 | Edge | Deploy success refreshes access once after canonical deployment completion |

### 11.4 Panel widget tests

**File:** `test/widgets/twin_overview/layer_access_panel_test.dart` [NEW]

| # | Type | Test and hard assertion |
|---:|---|---|
| 1 | Happy | Ready mixed placement renders exactly one L4 and one L5 card with exact service labels and enabled Open buttons |
| 2 | Happy | GCP L5 renders exactly one New password action and invokes its callback once |
| 3 | Unhappy | Failed GET renders exact safe error and Retry; no Open buttons |
| 4 | Unhappy | Blocked L4 disables only L4 Open, expands reason, and leaves L5 Open enabled |
| 5 | Edge | Loading renders one progress indicator and no stale cards |
| 6 | Edge | Unsupported historical state renders explanation and zero links |
| 7 | Edge | `browser_sign_in=unverified` keeps Open enabled and shows unverified detail |
| 8 | Edge | At 899 px cards stack L4 then L5; at 900 px they are siblings |
| 9 | Edge | 640 px and 200% text scale produce zero overflow exceptions |
| 10 | Edge | Light/dark semantics contain layer/provider/service/readiness and disabled reason |
| 11 | Edge | Capabilities/limitations expansion renders exact bounded rows and no raw secret |

### 11.5 Dialog and screen tests

**Files:**

- `test/widgets/twin_overview/twin_overview_operation_dialogs_test.dart`
  [MODIFY]
- `test/screens/twin_overview/twin_overview_layer_access_test.dart` [NEW]

| # | Type | Test and hard assertion |
|---:|---|---|
| 1 | Happy | Open reserves injected launcher and navigates exact validated URI once |
| 2 | Happy | New password confirmation dispatches exact rotation event; reveal listener consumes then shows exact username |
| 3 | Unhappy | Popup reservation/navigation failure closes handle and shows safe banner without URL/secret leakage |
| 4 | Unhappy | Rotation failure never opens reveal dialog |
| 5 | Edge | Password starts obscured; Show toggles semantics and visual state |
| 6 | Edge | Copy username and Copy password place exact values on clipboard and show no password in feedback text |
| 7 | Edge | Escape/Close removes dialog and no BLoC state retains pending credential |
| 8 | Edge | Rapid double Open creates one action per click without modifying BLoC state |
| 9 | Edge | Credential token already consumed does not reopen on unrelated state update |
| 10 | Edge | Focus order is L4 Open/details, then L5 Open/rotation/details |
| 11 | Edge | Existing Deployment Actions, Testing Utilities, Outputs, and Configuration Review remain present after insertion |

### 11.6 Real Management API integration tests

**File:** `integration_test/twin_layer_access_flow_test.dart` [NEW]

The integration suite must call the live local Management API in Docker. It
must not mock Dio/HTTP and must not deploy cloud resources.

| # | Type | Test and hard assertion |
|---:|---|---|
| 1 | Happy | Seeded AWS/AWS deployment returns exact two surfaces and Twin Overview renders exact URLs/services |
| 2 | Happy | Seeded mixed GCP-L4/Azure-L5 deployment renders IAP/Entra auth and independently opens both injected test URLs |
| 3 | Unhappy | Owner B cannot read Owner A access; assert 404 and no links |
| 4 | Unhappy | Backend seeded blocked access shows exact failure code/remediation and unaffected card stays enabled |
| 5 | Edge | Iterate all nine placement fixtures and assert exact L4/L5 provider pairs and exactly two surfaces each |
| 6 | Edge | Historical v1 fixture shows unsupported with zero fabricated links |
| 7 | Edge | Destroyed fixture returns no active access and Flutter clears cards |
| 8 | Edge | GCP rotation returns a new credential/fingerprint and a second rotation invalidates/replaces it in fixture state without exposing Admin/reader values |
| 9 | Edge | Generic outputs remain separately rendered and redacted after access load |

### 11.7 Mandatory commands and environment discipline

Run the focused Flutter tests first from `twin2multicloud_flutter`:

```bash
flutter test test/models/deployment_access_test.dart
flutter test test/bloc/twin_overview/twin_overview_layer_access_test.dart
flutter test test/widgets/twin_overview/layer_access_panel_test.dart
```

Then run from the repository root:

```bash
./thesis.sh test backend
./thesis.sh test deployment-contract
./thesis.sh test frontend
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration
docker --context orbstack compose --profile docs run --rm docs mkdocs build --strict
```

Before integration, record
`docker --context orbstack compose ps --services --filter status=running`.
After integration, stop only services started by this run; never issue blanket
`compose down`, prune, or stop user-owned containers. No command receives cloud
credentials, `apply`, or live flags.

Then run from `twin2multicloud_flutter`:

```bash
flutter analyze
flutter test
flutter build web
flutter build macos
flutter build windows
flutter build linux
```

Run only build targets supported by the current host/CI; the implementation
evidence must distinguish executed from pending platform builds. Real cloud
browser sign-in is a separate, explicitly approved supervised gate and is not
part of these automated tests.

### 11.8 Mandatory documentation phase

After code/tests and before the final review, update all of the following in
the same clean documentation commit:

- `twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_08_TWIN_OVERVIEW_DEPLOYMENT_OPERATIONS.md`:
  mark 8.6 implemented and replace planned evidence with exact tests/builds;
- `twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md`:
  move 8.6 from planned to complete without changing earlier phase numbers;
- `twin2multicloud_flutter/docs/feature-requests/FR_TRACKER.md` and FR-001:
  mark the exact backend/Deployer contract implemented;
- `twin2multicloud_flutter/README.md` and `FRONTEND_ARCHITECTURE.md`: describe
  only behavior that is actually available;
- Phase 8 service closure, access handoff, mini-roadmap, and handoff: record
  exact provider outputs, residual IAP/Firestore/certificate limitations, and
  offline versus supervised-live evidence;
- docs-site deployment result/provider capability pages: expose the access
  contract without publishing a credential, raw URL fixture, or cloud secret.

New component reference documentation is mandatory at
`twin2multicloud_flutter/docs/frontend_delta/implementation/layer_access_panel.md`.
It must list the two public widgets, state phases, Management endpoints,
provider/auth matrix, and secret-handling boundary. Strict MkDocs must catch
every broken link before commit.

## 12. Definition of Done

- [ ] The implementation branch is created from the reviewed integrated Phase
      8.9A foundation, not the planning worktree.
- [ ] FR-001 backend/Deployer contracts and strict fixtures are implemented
      before Flutter consumes them.
- [ ] Every `[NEW]` and `[MODIFY]` item in Sections 3-4 is implemented exactly;
      no checklist item is optional.
- [ ] `deployment-access.v1` rejects unknown versions, invalid provider/auth
      pairs, invalid URLs, duplicate/missing layers, and secret-like fields.
- [ ] All nine placements return and render exactly one L4 and one L5 surface.
- [ ] L4/L5 partial readiness remains independent and Destroy is never blocked
      by access-read failure.
- [ ] External links use only the existing injected launcher; no widget calls
      `url_launcher`, Dio, Deployer, Optimizer, Terraform, or cloud APIs.
- [ ] GCP rotation is explicit, non-retried, Viewer-only, and one-time; Admin,
      datasource, provider, and reader secrets never cross the UI contract.
- [ ] Destroy, redeploy, navigation, retry, and stale-response races clear or
      ignore old access/credential data.
- [ ] Desktop, narrow Web, compact Web, 640 px, 200% text scale, keyboard,
      semantics, and light/dark behavior match Sections 2, 5, and 9.
- [ ] No hardcoded color, spacing, typography, third-party icon, route, or
      state-management package is added.
- [ ] Every test in Section 11 has hard assertions and passes; integration
      tests use the real local Management API and no real cloud.
- [ ] `flutter analyze`, complete Flutter tests, supported Web/Desktop builds,
      backend/deployment-contract suites, frontend integration, `git diff
      --check`, and strict MkDocs pass with executed/pending evidence recorded.
- [ ] Phase 8.6 frontend docs, concept, feature-request tracker, cross-stack
      plan, handoff, and current-system docs are updated to distinguish planned,
      implemented, offline-verified, and live-verified behavior.
- [ ] Each cross-stack slice receives a clean `[AI-0731-LACC]` commit and a
      zero-finding review before the next slice.
- [ ] Two final reviews pass from both architect and builder perspectives with
      zero unresolved findings.
- [ ] Builder/auditor handoff is emitted only after explicit **Approved** or
      **Genehmigt**.
