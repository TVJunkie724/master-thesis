---
title: "Credential SSOT and Runtime Config Implementation Plan"
description: "Plan for making Flutter use Management API Cloud Connections and dart-define runtime configuration."
tags: [flutter, credentials, runtime-config, wizard, cloud-connections]
lastUpdated: "2026-05-01"
version: "1.0"
---

<!-- SOURCES:
- FRONTEND_ARCHITECTURE.md Step 1 credential workflow and Flutter architecture notes
- integration_vision.md Orchestrator and Management Platform vision
- ONBOARDING.md Management API-only integration rule and local service ports
- docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md credential SSOT target architecture
- twin2multicloud_backend/src/api/routes/cloud_connections.py Cloud Connection endpoint contract
- twin2multicloud_backend/src/schemas/cloud_connection.py Cloud Connection request/response schemas
EXTRACTED: 2026-05-01 | VERSION: 1.0
-->

# Implementation Plan: Credential SSOT and Runtime Config

## 0. Git Branch

- **Branch name:** `codex/backend-orchestrator-plan`
- **Base branch:** `master`
- **Merge strategy:** Merge commit only, no rebase.
- **Session ID:** n/a for this repository generation; use conventional commit format.
- **Backend dependency:** Cloud Connection SSOT API from commits `78d924b`, `95dd652`, `575e8ed`, `d23ce16`.
- **Status:** Implemented.

## 1. Summary

This slice makes Flutter consume the Management API Cloud Connection store as the credential source of truth and removes hardcoded runtime connection values from the app startup path.

Relevant architecture sources:

- `FRONTEND_ARCHITECTURE.md`: Wizard Step 1 currently owns credential entry and validation.
- `integration_vision.md`: Flutter is the orchestrator UI and must not call Optimizer or Deployer directly.
- `docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md`: Management API owns Cloud Connections; Flutter captures user intent and binds twins to reusable connections.
- `ONBOARDING.md`: Flutter calls Management API on port 5005 only.

After implementation, the app can start with:

```bash
cd twin2multicloud_flutter
flutter run -d chrome --dart-define-from-file=config/dev.json
```

Non-goals for this slice:

- Do not build admin credential bootstrap automation.
- Do not create cloud-side least-privilege identities from Flutter.
- Do not remove backend legacy credential fields yet; they remain a compatibility fallback.
- Do not redesign Wizard Step 2 or Step 3.

## 2. Visual Layout (ASCII)

Desktop and wide web layout, width >= 800px:

```text
Step1Configuration
+------------------------------------------------------------------------+
| Digital Twin Name                                                      |
| [ Smart Home IoT                                                   ]   |
|                                                                        |
| Mode:  [ Production ] [ Debug ]                                        |
|                                                                        |
| Cloud Connections                                                      |
| +--------------------------------------------------------------------+ |
| | AWS                                                                | |
| | Status: valid | Last validated: 2026-05-01 10:00                  | |
| | Connection: [ AWS thesis dev                         v ] [Check]  | |
| | Scope: eu-central-1 | fingerprint sha256:...                      | |
| | [New connection] [Unbind] [Delete]                                | |
| +--------------------------------------------------------------------+ |
| +--------------------------------------------------------------------+ |
| | Azure                                                              | |
| | Status: not validated                                              | |
| | Connection: [ Select Azure connection                v ] [Check]  | |
| | [New connection]                                                   | |
| +--------------------------------------------------------------------+ |
| +--------------------------------------------------------------------+ |
| | GCP                                                                | |
| | Status: no connection selected                                     | |
| | Connection: [ Select GCP connection                  v ] [Check]  | |
| | [New connection]                                                   | |
| +--------------------------------------------------------------------+ |
|                                                                        |
| Legacy credentials configured for this twin                            |
| [Replace with Cloud Connection]                                        |
|                                                                        |
| To proceed: name the twin and select or validate one provider.          |
+------------------------------------------------------------------------+
```

Compact web layout, width < 800px:

```text
Step1Configuration
+--------------------------------------+
| Digital Twin Name                    |
| [ Smart Home IoT                  ]  |
|                                      |
| Mode                                 |
| [ Production ] [ Debug ]             |
|                                      |
| Cloud Connections                    |
| +----------------------------------+ |
| | AWS                              | |
| | [ AWS thesis dev              v] | |
| | [Check] [New]                   | |
| | valid | eu-central-1             | |
| +----------------------------------+ |
| +----------------------------------+ |
| | Azure                            | |
| | [ Select Azure connection     v] | |
| | [Check] [New]                   | |
| +----------------------------------+ |
| +----------------------------------+ |
| | GCP                              | |
| | [ Select GCP connection       v] | |
| | [Check] [New]                   | |
| +----------------------------------+ |
+--------------------------------------+
```

Create dialog layout:

```text
CloudConnectionCreateDialog
+----------------------------------------------------------+
| New AWS Cloud Connection                                |
| Display name [                                      ]    |
| Region       [ eu-central-1                         ]    |
| Access key   [                                      ]    |
| Secret key   [                                      ]    |
| Session token (optional) [                           ]    |
|                                                          |
| [Cancel]                                      [Create]   |
+----------------------------------------------------------+
```

GCP dialog variant:

```text
CloudConnectionCreateDialog
+----------------------------------------------------------+
| New GCP Cloud Connection                                |
| Display name [                                      ]    |
| Region       [ europe-west1                        ]    |
| Billing account (optional) [                       ]    |
| Service account JSON                                |
| [Upload JSON] project_id: detected-project               |
|                                                          |
| [Cancel]                                      [Create]   |
+----------------------------------------------------------+
```

## 3. Widget Tree

```text
Step1Configuration [MODIFY] lib/screens/wizard/step1_configuration.dart
  SingleChildScrollView [REUSE]
    Center [REUSE]
      ConstrainedBox [REUSE]
        Column [REUSE]
          TextField twin name [REUSE]
          Mode ChoiceChips [REUSE]
          CloudConnectionsGroup [NEW] lib/widgets/cloud_connections/cloud_connections_group.dart
            CloudConnectionSection AWS [NEW] lib/widgets/cloud_connections/cloud_connection_section.dart
              CloudConnectionSelector [NEW] lib/widgets/cloud_connections/cloud_connection_selector.dart
              CloudConnectionValidationStatus [NEW] lib/widgets/cloud_connections/cloud_connection_validation_status.dart
              Action buttons [REUSE Material buttons]
            CloudConnectionSection Azure [NEW]
            CloudConnectionSection GCP [NEW]
          LegacyCredentialFallbackBanner [NEW] lib/widgets/cloud_connections/legacy_credential_fallback_banner.dart
          Step proceed hint [REUSE]

CloudConnectionCreateDialog [NEW] lib/widgets/cloud_connections/cloud_connection_create_dialog.dart
  AlertDialog [REUSE]
    ProviderPayloadForm [NEW] lib/widgets/cloud_connections/provider_payload_form.dart
      AwsPayloadFields [NEW]
      AzurePayloadFields [NEW]
      GcpPayloadFields [NEW]
        CredentialFileUploader [REUSE] lib/widgets/credentials/credential_file_uploader.dart
```

Reuse justification:

- `CredentialFileUploader` is reused for GCP JSON upload.
- Existing `CredentialSection` and `CredentialInputForm` are not extended because their primary contract is direct secret entry tied to twin config validation; the new contract is reusable stored connections plus binding.
- Existing `CredentialValidationStatus` can be reused only if its API accepts Cloud Connection validation states without legacy text assumptions. If not, create `CloudConnectionValidationStatus` with the same visual language and no secret-bearing fields.

## 4. Component Specifications

### `CloudConnectionsGroup` [NEW]

Path: `lib/widgets/cloud_connections/cloud_connections_group.dart`

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `connectionsByProvider` | `Map<CloudProvider, List<CloudConnection>>` | yes | - |
| `selectedConnectionIds` | `Map<CloudProvider, String?>` | yes | - |
| `loadingByProvider` | `Map<CloudProvider, bool>` | yes | - |
| `errorByProvider` | `Map<CloudProvider, String?>` | yes | - |
| `validationByProvider` | `Map<CloudProvider, CloudConnectionValidationResult?>` | yes | - |
| `legacyConfiguredProviders` | `Set<CloudProvider>` | yes | - |
| callbacks | typed callbacks | yes | - |

Must be a `StatelessWidget`. It receives all data from `WizardBloc`; it never calls `ApiService`.

### `CloudConnectionSection` [NEW]

Path: `lib/widgets/cloud_connections/cloud_connection_section.dart`

Uses existing tokens:

- Spacing: `AppSpacing.sm`, `AppSpacing.md`, `AppSpacing.lg`, `AppSpacing.maxContentWidthMedium`.
- Colors: `AppColors.getProviderColor(provider.name)`, semantic colors from `Theme.of(context).colorScheme`.
- Typography: `Theme.of(context).textTheme.*`; no inline `TextStyle`.
- Icons: Material `Icons.cloud`, `Icons.cloud_circle`, `Icons.cloud_queue`, `Icons.check_circle`, `Icons.error_outline`.

Must render loading, empty, selected, validation error, and delete-conflict states.

### `CloudConnectionCreateDialog` [NEW]

Path: `lib/widgets/cloud_connections/cloud_connection_create_dialog.dart`

Must be `StatefulWidget` because it owns temporary secret text controllers. Controllers must be cleared and disposed. Secret values must not be exposed through debug output.

On successful create, the dialog returns a `CloudConnectionCreateRequest` to the parent via `Navigator.pop(request)`. The widget does not call HTTP directly.

### `ProviderPayloadForm` [NEW]

Path: `lib/widgets/cloud_connections/provider_payload_form.dart`

Must perform client-side required-field validation:

- AWS: `access_key_id`, `secret_access_key`, `region`
- Azure: `subscription_id`, `client_id`, `client_secret`, `tenant_id`
- GCP: `service_account_json`, `region`; `project_id` is parsed or supplied as fallback

## 5. Responsive Behavior

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Wide Desktop | >= 1440px | Content remains constrained by `AppSpacing.maxContentWidthMedium`; provider panels are full-width inside the wizard column. |
| Narrow Desktop / Web | 800-1439px | Same single-column layout; controls remain in one row where labels fit. |
| Compact Web | < 800px | Provider panel controls wrap vertically; action buttons use `Wrap`; dialogs use full available width with scrollable content. |

No mobile-specific navigation or platform code is introduced.

## 6. State Flow (BLoC)

Existing owner: `WizardBloc`.

New state fields:

- `Map<CloudProvider, List<CloudConnection>> cloudConnections`
- `Map<CloudProvider, String?> selectedCloudConnectionIds`
- `Map<CloudProvider, bool> cloudConnectionLoading`
- `Map<CloudProvider, String?> cloudConnectionErrors`
- `Map<CloudProvider, CloudConnectionValidationResult?> cloudConnectionValidation`

New events:

- `WizardCloudConnectionsLoadRequested`
- `WizardCloudConnectionSelected(CloudProvider provider, String? connectionId)`
- `WizardCloudConnectionCreateRequested(CloudProvider provider, CloudConnectionCreateRequest request)`
- `WizardCloudConnectionValidateRequested(CloudProvider provider, String connectionId)`
- `WizardCloudConnectionUnbound(CloudProvider provider)`
- `WizardCloudConnectionDeleteRequested(CloudProvider provider, String connectionId)`

Data flow:

```text
UI selection
  -> WizardCloudConnectionSelected
  -> WizardBloc updates selectedCloudConnectionIds
  -> canProceedToStep2/configuredProviders recompute
  -> UI reflects configured provider

Create dialog submit
  -> WizardCloudConnectionCreateRequested
  -> WizardBloc
  -> ApiService.createCloudConnection
  -> Management API POST /cloud-connections/
  -> state list updated and new ID selected

Validate selected
  -> WizardCloudConnectionValidateRequested
  -> ApiService.validateCloudConnection
  -> Management API POST /cloud-connections/{id}/validate
  -> state validation map updated

Save draft / finish
  -> WizardBloc builds config
  -> ApiService.updateTwinConfig
  -> Management API PUT /twins/{id}/config/
  -> payload includes cloud_connections only for selected/unbound providers
```

Derived behavior:

- `canProceedToStep2` is true when the twin has a name and at least one provider has a selected Cloud Connection or valid legacy fallback.
- `configuredProviders` includes selected Cloud Connections.
- `unconfiguredProviders` compares optimizer requirements against selected Cloud Connections plus legacy fallback.
- Save draft and finish must not send `aws`, `azure`, or `gcp` legacy secret maps for providers with selected Cloud Connections.

## 7. Design Tokens

No new design tokens are expected.

Must reuse:

- `AppSpacing` for all padding, gaps, max widths, and border radius.
- `AppColors.getProviderColor` for provider identity.
- Theme `colorScheme` for surface, border, error, and disabled states.
- Theme `textTheme` for all text.

The implementation must not introduce hardcoded colors, hardcoded spacing literals, or inline `TextStyle` constructors.

## 8. Interactions & Animations

- Load connections on wizard create/edit initialization.
- Provider selector disabled while that provider is loading.
- Empty provider list shows a call-to-action to create a connection.
- Validate button disabled when no connection is selected or validation is in progress.
- Delete button asks for confirmation before dispatching delete.
- Backend `409` on delete is shown inline in the relevant provider panel and does not remove the connection locally.
- Dialog close: `Esc` and Cancel discard temporary secrets.
- Dialog submit: Enter submits only when validation passes.
- No custom animations are required; use Material dialog/indicator defaults.

## 9. Accessibility

- Focus order: twin name -> mode chips -> AWS selector/actions -> Azure selector/actions -> GCP selector/actions -> legacy fallback action.
- Each provider selector must have an accessible label with provider name.
- Icon-only buttons, if used, must have tooltips.
- Validation status must include text, not color only.
- Error messages must be associated with their provider panel.
- Dialog fields must have labels and validation messages.
- Contrast must come from Material theme colors; no custom low-contrast color literals.

## 10. Integration Points

Management API endpoints only:

| Method | Path | Request body | Response shape | Notes |
|--------|------|--------------|----------------|-------|
| GET | `/cloud-connections/` | none | `List<CloudConnection>` | Optional `provider` query. |
| POST | `/cloud-connections/` | `CloudConnectionCreateRequest` | `CloudConnection` | Creates encrypted user-scoped connection. |
| PATCH | `/cloud-connections/{id}` | metadata only | `CloudConnection` | Display name and scope only. |
| DELETE | `/cloud-connections/{id}` | none | `204` | May return `409` when bound. |
| POST | `/cloud-connections/{id}/validate` | none | `CloudConnectionValidationResult` | Runs Optimizer and Deployer validation via Management API. |
| GET | `/twins/{id}/config/` | none | `TwinConfigResponse` | Reads `*_cloud_connection_id` fields. |
| PUT | `/twins/{id}/config/` | `cloud_connections` map | `TwinConfigResponse` | Binds/unbinds selected connections. |

Forbidden:

- No direct Flutter calls to port 5003 or 5004.
- No new Optimizer or Deployer URL configuration in Flutter.
- No credential values in logs, debug prints, route params, or user-visible validation echoes.

Runtime config files:

- `twin2multicloud_flutter/config/dev.example.json`
- `twin2multicloud_flutter/config/dev.json`
- `twin2multicloud_flutter/config/dev.local.json` is intentionally not committed and may be used for personal overrides.

Runtime config keys:

```json
{
  "API_BASE_URL": "http://localhost:5005",
  "DEV_AUTH_TOKEN": "dev-token"
}
```

`ApiConfig` must use `String.fromEnvironment` with safe local defaults so existing `flutter test` and `flutter run` still work without a define file.

Because Flutter Web API calls run in the user's browser, `config/dev.json` must point to the host-exposed Management API URL (`http://localhost:5005`), not the Docker-internal service name `management-api`.

`config/dev.example.json` must contain the same keys as `config/dev.json` and is the committed template for new developers. `config/dev.json` may also be committed while it contains only non-secret local defaults. Any developer-specific or secret-bearing override belongs in gitignored `config/dev.local.json`.

Documentation phase:

- Create `twin2multicloud_flutter/docs/README.md` if missing and add the `wizard` pillar index.
- Create or update `twin2multicloud_flutter/docs/wizard/ROADMAP_WIZARD.md`.
- Add `twin2multicloud_flutter/docs/wizard/phases/PHASE_CREDENTIAL_SSOT.md` with YAML frontmatter, provenance, scope table, and links back to this implementation plan.
- Add `twin2multicloud_flutter/docs/wizard/implementation/cloud_connection_widgets.md` as the component reference for the new Cloud Connection widgets.
- Do not duplicate backend credential architecture docs; link to `docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md`.

## 11. Test Plan

### Unit and Widget Tests

| # | Type | Test Description | Expected Outcome |
|---|------|------------------|------------------|
| 1 | Happy | `CloudConnection.fromJson` parses a valid AWS response. | All typed fields, summary, timestamps, and status match input. |
| 2 | Happy | `CloudConnectionCreateRequest.toJson` emits one provider payload. | JSON contains selected provider payload only. |
| 3 | Unhappy | GCP create request without `service_account_json`. | Client validation fails before API dispatch. |
| 4 | Unhappy | Delete returns backend `409`. | Provider panel shows conflict and keeps connection in selector. |
| 5 | Edge | Empty Cloud Connection list. | Provider panel shows empty state and create action. |
| 6 | Edge | Config response contains `aws_cloud_connection_id` unknown to loaded list. | State preserves ID and shows recoverable warning. |
| 7 | Edge | Legacy-only config response has `aws_configured=true` and no connection ID. | Step 1 remains proceedable as migration fallback. |
| 8 | Edge | Selecting Cloud Connection after legacy credentials. | Save payload sends `cloud_connections.aws` and does not send legacy `aws`. |
| 9 | Edge | Rapid select/unbind/select sequence. | Final selected ID wins and state remains immutable/equatable. |
| 10 | Edge | Validation response includes nested optimizer/deployer failure. | Redacted message renders textually without secret fields. |

### BLoC Tests

| # | Type | Test Description | Expected Outcome |
|---|------|------------------|------------------|
| 1 | Happy | Create mode loads Cloud Connections. | `cloudConnections` populated, no provider selected. |
| 2 | Happy | Edit mode hydrates `*_cloud_connection_id`. | Selected IDs match config response. |
| 3 | Unhappy | List Cloud Connections API fails. | Provider error set; wizard remains usable for other providers. |
| 4 | Unhappy | Create Cloud Connection API fails validation. | Error message shown, no selected ID created. |
| 5 | Edge | Save CloudConnection-only draft. | `updateTwinConfig` called with `cloud_connections`; no secret maps. |
| 6 | Edge | Unbind provider and save. | Payload sends provider value `null`. |
| 7 | Edge | Validate selected connection succeeds. | Validation map updated and provider considered configured. |
| 8 | Edge | Validate selected connection fails. | Validation map updated; provider remains selected but invalid status visible. |
| 9 | Edge | Optimizer result requires unselected provider. | `unconfiguredProviders` includes missing provider. |

### Integration Tests Against Docker

Integration tests are allowed only against the local Management API stack and must not deploy real cloud resources.

Prep:

```bash
docker compose up -d management-api 2twin2clouds 3cloud-deployer
docker ps
```

Run:

```bash
cd twin2multicloud_flutter
flutter test integration_test/credential_ssot_flow_test.dart \
  --dart-define-from-file=config/dev.json
```

Teardown:

```bash
docker compose stop management-api 2twin2clouds 3cloud-deployer
```

Integration cases:

| # | Type | Test Description | Expected Outcome |
|---|------|------------------|------------------|
| 1 | Happy | List seeded/dev Cloud Connections through Management API. | HTTP 200 and parsed list. |
| 2 | Happy | Create a fake-format connection rejected by backend validation path without leaking secret. | UI/API error is redacted and structured. |
| 3 | Unhappy | Delete a bound connection. | HTTP 409 shown in UI state. |
| 4 | Unhappy | Start app with missing backend. | User sees recoverable loading/error state, not blank screen. |
| 5 | Edge | Run app with `config/dev.json`. | `ApiConfig.baseUrl` points to localhost 5005. |

No E2E deployment tests run in this slice.

Verification commands:

```bash
cd twin2multicloud_flutter
flutter pub get
flutter analyze
flutter test
flutter build web --dart-define-from-file=config/dev.json
```

## 12. Definition of Done

Every item below is required. Builders must not skip or silently defer any item unless the user explicitly approves a scoped deferral.

- [ ] `config/dev.json` exists and starts Flutter against `http://localhost:5005`.
- [ ] `config/dev.example.json` exists with the same non-secret keys as `config/dev.json`.
- [ ] `ApiConfig` reads `API_BASE_URL` and `DEV_AUTH_TOKEN` from Dart defines with local defaults.
- [ ] No hardcoded backend URL or dev token remains outside `ApiConfig`.
- [ ] `CloudConnection` models parse backend responses without secret fields.
- [ ] `ApiService` exposes typed Cloud Connection methods and uses Management API only.
- [ ] `WizardState`, `WizardEvent`, and `WizardBloc` support loading, selecting, creating, validating, unbinding, and delete-conflict handling.
- [ ] Step 1 renders Cloud Connection selectors as the primary credential path.
- [ ] Secret inputs exist only in the create dialog and are cleared/disposed after use.
- [ ] Saving a CloudConnection-only twin sends `cloud_connections` IDs and no legacy secret maps.
- [ ] Editing a CloudConnection-only twin hydrates selected provider IDs correctly.
- [ ] Legacy-only credentials remain a visible migration fallback and do not regress existing twins.
- [ ] Provider panels have loading, empty, error, selected, validating, valid, invalid, and conflict states.
- [ ] New widgets use `AppSpacing`, `AppColors`, `ThemeData`, and Material `Icons`.
- [ ] No direct Flutter calls to Optimizer or Deployer ports are introduced.
- [ ] `twin2multicloud_flutter/README.md` documents `--dart-define-from-file=config/dev.json`.
- [ ] `twin2multicloud_flutter/docs/README.md` exists or is updated with the `wizard` pillar.
- [ ] `twin2multicloud_flutter/docs/wizard/ROADMAP_WIZARD.md` exists or is updated.
- [ ] `twin2multicloud_flutter/docs/wizard/phases/PHASE_CREDENTIAL_SSOT.md` documents the implemented phase with frontmatter and provenance.
- [ ] `twin2multicloud_flutter/docs/wizard/implementation/cloud_connection_widgets.md` documents the new widget responsibilities.
- [ ] Unit/model tests cover request/response mapping and client validation.
- [ ] BLoC tests cover selection, creation failure, validation, unbinding, save payloads, and legacy fallback.
- [ ] Widget tests cover provider panels and create dialogs.
- [ ] Integration test plan is implemented or explicitly deferred with user approval; no real cloud deployment test is run.
- [ ] `flutter pub get` succeeds.
- [ ] `flutter analyze` succeeds with zero issues.
- [ ] `flutter test` succeeds.
- [ ] `flutter build web --dart-define-from-file=config/dev.json` succeeds.
