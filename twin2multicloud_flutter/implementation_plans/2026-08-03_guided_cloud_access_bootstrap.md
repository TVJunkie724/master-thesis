# Implementation Plan: Guided Cloud Access Bootstrap

## 0.1 Contract Revision (2026-08-24)

The implementation retains the plan's UI and lifecycle but now resolves the
provider-authority review findings with active
`bootstrap.aws.admin-v2`, `bootstrap.azure.admin-v2`, and
`bootstrap.gcp.admin-v2` packs. AWS also pins
`aws.thesis-demo-v2.iam-user-v1`, which binds the frozen deployment permission
inventory to the actually implemented IAM-user/access-key identity. Historical
v1 packs remain available only as versioned evidence and compatibility input.

## 0. Git Branch

- **Branch name:** `codex/phase-8-guided-bootstrap`
- **Base branch:** reviewed `codex/phase-8-profile-workflow` commit with the
  complete-service contracts and `thesis-demo-v2` permission packs.
- **Merge strategy:** merge commit; no rebase. The user controls integration to
  the default branch.
- **Session/commit prefix:** `[AI-0803-BOOT]`.
- **Authorization:** the user explicitly requested implementation on
  2026-08-03. No live provider execution is included.

## 1. Summary

This feature replaces the current manual-first cloud credential setup with one
guided PoC bootstrap shared by Settings and Prepare Deployment. A researcher
first follows provider-specific instructions to create or obtain temporary
administrator/bootstrap authority, enters it into a write-only form, and asks
the Management API to create a bounded deployment identity. Only the generated
bounded CloudConnection persists. The submitted administrator secret is
request-scoped and is never returned, rehydrated, logged, or stored by Flutter.

The feature implements Configuration Workspace Phase 9 and FR-002. It preserves
the existing manual plan/script/import route as an explicitly labeled advanced
fallback. It does not automate commercial account creation, browser login,
organization governance, or every provider prerequisite.

Authority:

- `docs/configuration_workspace/concepts/CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md`
- `docs/configuration_workspace/phases/PHASE_09_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md`
- `docs/feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md`
- `../docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md`

## 2. Visual Layout (ASCII)

### Settings, wide desktop/web

```text
+ Settings -----------------------------------------------------------------+
| Profile                                                                    |
| Login accounts                                                             |
|                                                                            |
| Cloud accounts & access                                      [Refresh]    |
| Pricing and bounded deployment identities.                                |
| + AWS ----------------+ + Azure --------------+ + GCP ------------------+ |
| | Pricing Ready       | | Pricing Ready       | | Pricing Ready          | |
| | Deployment 0        | | Deployment 1        | | Deployment 0           | |
| | [Set up access]     | | [Set up access]     | | [Set up access]        | |
| | [Access details v]  | | [Access details v]  | | [Access details v]     | |
| +---------------------+ +----------------------+ +-------------------------+ |
|                                                                            |
| Advanced: import an existing bounded deployment identity            [v]   |
+----------------------------------------------------------------------------+
```

### Prepare Deployment, wide desktop/web

```text
+ Prepare deployment / Cloud access ---------------------------------------+
| Required by selected architecture: AWS, GCP                              |
|---------------------------------------------------------------------------|
| AWS  [Missing]   Target 123456789012 / eu-central-1  [Set up access]      |
| GCP  [Ready]     project / europe-west1                 [Validate]         |
| Azure [Not required]                                                       |
|---------------------------------------------------------------------------|
| Provider prerequisites are checked later by deployment preflight.         |
+----------------------------------------------------------------------------+
```

### Guided bootstrap stepper/dialog, wide

```text
+ Set up AWS deployment access --------------------------------------------+
| 1 Guide -------- 2 Target -------- 3 Authority -------- 4 Result          |
|---------------------------------------------------------------------------|
| Before continuing                                                         |
| 1. Sign in as a non-root administrator.                                  |
| 2. Create a dedicated temporary principal or short STS session.          |
| 3. Apply bootstrap.aws.admin-v2.                                         |
|                                                                           |
| [Open provider instructions]  [I completed these steps]                   |
|---------------------------------------------------------------------------|
| Target                                                                     |
| Account ID [____________] Region [eu-central-1 v]                         |
|---------------------------------------------------------------------------|
| Administrator/bootstrap authority (used for this request only)            |
| Access key ID     [________________________]                               |
| Secret access key [************************]                               |
| Session token     [************************] (optional)                     |
| Origin ( ) dedicated/disposable  ( ) short session  ( ) existing owned   |
|                                                                           |
| Secret fields cannot be restored after submission.                        |
|                                             [Cancel] [Create bounded access]|
+----------------------------------------------------------------------------+
```

Provider forms render only the strict fields declared by the guide: Azure uses
tenant/subscription/client/secret; GCP uses organization-or-project target and
a write-only bootstrap service-account JSON. No browser password is requested.

### Result and external/manual follow-up

```text
+ AWS bounded access created -----------------------------------------------+
| Deployment identity  thesis-demo-...                        [Ready]        |
| Permission pack      thesis-demo-v2                                        |
| Validation           Passed                                                |
| Bootstrap authority  Released locally; manual revocation required          |
|                                                                           |
| Delete the temporary access key in AWS, then confirm.                      |
| [Open cleanup instructions] [I revoked it]                                 |
|                                                                           |
| The generated deployment credential is stored encrypted and never shown.  |
|                                                        [Done]              |
+----------------------------------------------------------------------------+
```

`existing_user_owned` instead reports that the credential remains valid and
was not deleted. An STS session reports its provider expiry and requires no
false revocation acknowledgement.

### Compact web below 800 px

```text
+ Cloud access -----------------------------+
| AWS / Missing                              |
| Step 1 of 4: Guide                         |
|--------------------------------------------|
| Provider instructions wrap vertically.    |
| [Open provider instructions              ]|
| [I completed these steps                 ]|
|--------------------------------------------|
| [Cancel]                                  |
+--------------------------------------------+
```

Cards and form controls stack full width. The guide/result body scrolls while
the current step and actions remain reachable. The lower supported width is
640 px; no mobile target is added.

## 3. Widget Tree

```text
SettingsScreen [MODIFY]
`-- _SettingsCloudAccessScope [MODIFY]
    |-- CloudAccessBloc [REUSE]
    |-- CloudBootstrapBloc [NEW]
    `-- CloudAccountsPanel [MODIFY]
        `-- _ProviderAccessCard [MODIFY]
            `-- setup action -> CloudBootstrapFlow [NEW]

WizardScreen [MODIFY composition only]
`-- CloudAccessTask [MODIFY]
    |-- selected-provider requirement rows [MODIFY]
    `-- setup action -> CloudBootstrapFlow [REUSE new]

CloudBootstrapFlow [NEW]
|-- CloudBootstrapHeader [NEW, private]
|-- CloudBootstrapProgress [NEW]
|-- CloudBootstrapGuideStep [NEW]
|-- CloudBootstrapTargetStep [NEW]
|-- CloudBootstrapAuthorityStep [NEW]
|   `-- ProviderPayloadForm [REUSE/MODIFY: write-only mode]
|-- CloudBootstrapExecutionStep [NEW]
|-- CloudBootstrapResultStep [NEW]
|-- CloudBootstrapManualRevocation [NEW]
`-- existing dialog/buttons/status primitives [REUSE]
```

State/service tree:

```text
cloud_bootstrap.dart [NEW strict DTOs]
management_api.dart -> CloudBootstrapApi [NEW]
api_service.dart [MODIFY]
demo_management_api.dart [MODIFY]
bloc/cloud_bootstrap/* [NEW]
bloc/cloud_access/* [MODIFY completion refresh only]
runtime_providers.dart [REUSE ManagementApi composition]
```

`CloudBootstrapBloc` is separate from `CloudAccessBloc` because it owns a
revisioned, multi-command session with write-only transient secret entry,
restart/re-entry, and disposal states. `CloudAccessBloc` remains the inventory
and bounded-connection mutation owner. Both Settings and Workspace load the
same owner/provider/scope session from Management, so separate screen
instances cannot create separate mutable truth.

Reuse is binding: extend `CloudAccountsPanel`, `CloudConnectionSelector`,
`CloudConnectionValidationStatus`, `ProviderPayloadForm`, existing status and
dialog patterns, theme tokens, and Material icons. Do not add another form,
stepper, state-management, secret-storage, or icon package.

## 4. Component Specifications

### 4.1 Strict models

**File:** `lib/models/cloud_bootstrap.dart` [NEW]

| Type | Required fields |
|---|---|
| `CloudBootstrapGuide` | schema, provider, strict target field definitions, safe instructions/links, bootstrap pack ref/digest, generated pack ref/digest, accepted credential origins, guide digest |
| `CloudBootstrapTarget` | provider-specific strict safe target values; no secret fields |
| `CloudBootstrapSession` | schema, ID, owner-safe provider/scope, revision, state, guide/pack digests, safe findings, command permissions, timestamps, optional safe CloudConnection summary, disposal status |
| `CloudBootstrapFinding` | stable code, severity, safe message, allowed action, optional HTTPS remediation link |
| `CloudBootstrapConnectionSummary` | ID, provider, purpose deployment, display name, safe cloud scope, validation state |
| `CloudBootstrapExecuteRequest` | expected revision, idempotency key, credential origin, write-only provider secret payload |
| `CloudBootstrapManualRevocationRequest` | expected revision and explicit acknowledgement only |

Supported session states are the exact server registry, including guide-ready,
authority-required, executing, credential-reentry-required,
manual-revocation-required, ready, failed, cancelled, and expired. Unknown
state/version/field, duplicate findings, invalid action-state combinations,
wrong provider target/secret shape, non-HTTPS link, secret-like response key,
or non-deployment connection must fail closed.

The execute request is not Equatable/stringified with secret values, has no
`toJson` usable after the call, and exposes a `dispose()`/clear operation for
controllers and transient maps. Public response types contain no secret field.

### 4.2 API capability

**Files:**

- `lib/services/management_api.dart` [MODIFY]
- `lib/services/api_service.dart` [MODIFY]
- `lib/demo/demo_management_api.dart` [MODIFY]

Add `CloudBootstrapApi`:

```dart
Future<CloudBootstrapGuide> getCloudBootstrapGuide(
  CloudProvider provider,
  CloudBootstrapTarget target,
);
Future<CloudBootstrapSession> createCloudBootstrapSession(
  CloudBootstrapGuide guide,
  CloudBootstrapTarget target,
);
Future<List<CloudBootstrapSession>> listCloudBootstrapSessions({
  CloudProvider? provider,
  bool active = true,
});
Future<CloudBootstrapSession> getCloudBootstrapSession(String sessionId);
Future<CloudBootstrapSession> executeCloudBootstrapSession(
  String sessionId,
  CloudBootstrapExecuteRequest request,
);
Future<CloudBootstrapSession> acknowledgeCloudBootstrapRevocation(
  String sessionId,
  int expectedRevision,
);
Future<CloudBootstrapSession> cancelCloudBootstrapSession(
  String sessionId,
  int expectedRevision,
);
```

The adapter must disable automatic retry for execute/acknowledge/cancel. If an
execute response is lost, the BLoC GETs the stored session before permitting a
new command. No interceptor/logger may include request bodies on execute.

### 4.3 BLoC

**Files:** `lib/bloc/cloud_bootstrap/cloud_bootstrap_event.dart`,
`cloud_bootstrap_state.dart`, `cloud_bootstrap_bloc.dart`, barrel export [NEW]

State must contain provider/target, catalog-safe guide/session phases,
transient draft validity without secret values, active command/idempotency key,
safe error/finding, and completion signal. Secret controllers/payload live only
inside the write-only form until an event transfers them directly to the API
call; emitted BLoC state must never retain them.

Required events:

| Event | Payload/result |
|---|---|
| `CloudBootstrapOpened` | provider/optional target; load active session or guide |
| `CloudBootstrapGuideRequested` | safe target; fetch guide |
| `CloudBootstrapSessionStarted` | exact guide/target; create or resume one active session |
| `CloudBootstrapExecuteSubmitted` | origin + one-use secret request; execute once then dispose locally |
| `CloudBootstrapSessionRechecked` | GET session after uncertain/lost response |
| `CloudBootstrapCredentialReentryRequested` | return to write-only form without old values |
| `CloudBootstrapManualRevocationAcknowledged` | expected revision |
| `CloudBootstrapCancelled` | expected revision |
| `CloudBootstrapClosed` | clear transient local state; server session remains authoritative |

### 4.4 Shared flow component

**File:** `lib/widgets/cloud_connections/cloud_bootstrap_flow.dart` [NEW]

| Parameter | Type | Required/default |
|---|---|---|
| `provider` | `CloudProvider` | required |
| `initialTarget` | `CloudBootstrapTarget?` | optional |
| `entryPoint` | enum settings/workspace | required |
| `onConnectionReady` | `ValueChanged<CloudBootstrapConnectionSummary>` | required |
| `onClosed` | `VoidCallback` | required |

The component is a `BlocConsumer<CloudBootstrapBloc,...>` and contains no API
lookup. Workspace completion selects/binds the returned connection through the
existing Wizard/Cloud Access event. Settings completion refreshes inventory.

### 4.5 Entry-point modifications

| File/component | Required change |
|---|---|
| `lib/widgets/cloud_connections/cloud_accounts_panel.dart` | Add “Set up access” for deployment purpose and a collapsed advanced existing-credential action; keep pricing actions |
| `lib/features/configuration_workspace/presentation/cloud_access_task.dart` | Replace legacy path provider derivation with resolved-architecture providers; launch shared flow only for missing selected providers |
| `lib/screens/settings_screen.dart` | Compose Bootstrap and Cloud Access BLoCs; refresh inventory on ready |
| `lib/screens/wizard/wizard_screen.dart` | Provide the shared bootstrap BLoC at cloud-access task scope without changing routes |

## 5. Responsive Behavior

| Breakpoint | Width | Behavior |
|---|---|---|
| Wide Desktop | >= 1440 px | Settings provider cards three columns; bootstrap guide/target and contextual summary may use two columns |
| Narrow Desktop / Web | 800-1439 px | Provider cards wrap according to existing panel; flow content single main column with compact summary |
| Compact Web | < 800 px, supported to 640 px | Provider cards and all actions full-width; progress labels shorten but retain semantic full labels; form/result stack and scroll |

At 200% text, instructions, findings, credential-origin labels, and buttons
wrap. No secret form or result relies on hover or tooltip-only information.

## 6. State Flow (BLoC)

```text
Settings / CloudAccessTask
  -> CloudBootstrapOpened(provider, target)
  -> CloudBootstrapBloc
  -> CloudBootstrapApi
  -> Management API :5005
  -> safe guide/session DTO
  -> CloudBootstrapState
  -> CloudBootstrapFlow

write-only form controllers
  -> ExecuteSubmitted(one-use request)
  -> API call with logging disabled for body
  -> controllers + transient request cleared in finally
  -> safe session response only
  -> ready connection summary
  -> CloudAccessBloc refresh / Wizard binding
```

Only one command may be active. Revision conflicts reload the session. A lost
execute response transitions to “Check result” and never resubmits
automatically. Closing the UI clears local secret data but does not falsely
cancel a server command. A ready connection remains separate from later Twin
deployment preflight; the workspace runs that existing endpoint after binding
without requesting administrator credentials again.

## 7. Design Tokens

Reuse existing `AppSpacing`, provider colors, semantic success/warning/error
colors, ThemeData typography, form decoration, dialog/card/button/chip themes,
and motion. Add no literal color, TextStyle, spacing, radius, breakpoint, or
duration in feature widgets. Add a named token before widget code only if the
existing minimum field/action sizing cannot support the four-step flow.

## 8. Interactions & Animations

- Use standard Material focus/hover/pressed behavior and existing disclosure
  animation; no decorative animation.
- Guide and session loading show one inline progress indicator while safe
  prior content stays visible.
- Execute disables navigation and submit, shows progress beside the primary
  action, and offers no retry until the session has been rechecked.
- Field validation is inline. Guide/session GET failures show inline Retry.
  Command failures show safe server findings in the current flow; no raw
  provider message or snackbar containing input is allowed.
- “Show secret” is permitted only while typing and defaults hidden; moving
  steps or closing clears values. Paste is allowed; copy-back/download is not.
- Manual revocation uses an explicit confirmation. Escape cannot dismiss while
  a mutating request is active; focus returns to the provider setup action.
- Empty active-session result starts at the guide; expired/cancelled sessions
  offer “Start new setup” without restoring prior secret input.

## 9. Accessibility

- Focus order: heading, progress, instructions/links, target fields, secret
  fields, origin group, secondary action, primary action.
- Every step announces “step N of 4”, provider, state, and blocking finding.
- Secret inputs have provider-specific labels, obscured semantics, and no value
  in validation/error announcements.
- Enter submits only a valid idle step; Escape closes only when safe. Radio
  origins and acknowledgement controls expose group/checked semantics.
- External links announce provider and that a browser opens.
- Color is never the only status signal; contrast meets 4.5:1 body and 3:1
  large/status requirements.
- Keyboard, screen reader, 200% text, and 640 px width all retain every action.

## 10. Integration Points

| Method | Path | Request | Response/notes |
|---|---|---|---|
| POST | `/cloud-bootstrap/{provider}/guide` | strict safe target only | `cloud-bootstrap-guide.v1`; no credentials |
| POST | `/cloud-bootstrap/sessions` | provider, target, guide/pack digests | safe `cloud-bootstrap-session.v1`; one active per owner/provider/scope |
| GET | `/cloud-bootstrap/sessions?provider={provider}&active={bool}` | - | owner-scoped safe sessions |
| GET | `/cloud-bootstrap/sessions/{session_id}` | - | safe session; used after uncertain execute |
| POST | `/cloud-bootstrap/sessions/{session_id}/execute` | revision, idempotency key, origin, one-use provider secret | safe session only; body logging/retry prohibited |
| POST | `/cloud-bootstrap/sessions/{session_id}/acknowledge-manual-revocation` | expected revision | safe updated disposal state |
| POST | `/cloud-bootstrap/sessions/{session_id}/cancel` | expected revision | safe cancelled state |
| GET | `/cloud-connections/inventory` | - | refresh bounded deployment access |
| POST | `/twins/{twin_id}/deployment-preflight` | no admin secret | later selected-Twin prerequisite check |

The historical `POST /cloud-bootstrap/{provider}/plan` and
`POST /cloud-bootstrap/import` remain backend-compatible but are not used by
the guided UI. No new route is added: Settings and the existing
`/twins/{id}/edit` Configuration Workspace remain authenticated.

## 11. Test Plan

### Models/API/security

| # | Type | Test | Hard assertion |
|---|---|---|---|
| 1 | Happy | Parse each provider guide/session ready fixture | Exact fields, actions, digests, connection summary |
| 2 | Happy | Execute adapter sends each provider request | Exact path/body once; safe response parsed |
| 3 | Unhappy | Unknown state/version/action or wrong provider shape | Fail closed |
| 4 | Unhappy | Response contains secret-like key/non-HTTPS link | Rejected and not rendered |
| 5 | Edge | Duplicate active session | Existing session resumed; no second POST |
| 6 | Edge | Lost execute response | GET recheck; execute call verified exactly once |
| 7 | Edge | STS/session expiry | Exact provider expiry shown; no revocation claim |
| 8 | Edge | existing user-owned credential | Not deleted; correct disposal state |
| 9 | Edge | dedicated credential manual cleanup | Acknowledgement allowed only in exact state/revision |
| 10 | Edge | logging/toString/equality | Secret values absent from all strings/state/diagnostics |

### BLoC

| # | Type | Test | Hard assertion |
|---|---|---|---|
| 1 | Happy | Guide -> execute -> ready | Ordered phases and exact connection completion |
| 2 | Happy | Manual revocation -> acknowledgement | Exact final disposal state |
| 3 | Unhappy | Guide/session API error | Retryable safe state; target preserved |
| 4 | Unhappy | Execute fails after provider partial success | Server finding shown; no blind retry/duplicate |
| 5 | Edge | Cancel while idle vs executing | Allowed only by session command permissions |
| 6 | Edge | Revision conflict | Reload exact session and require fresh action |
| 7 | Edge | credential re-entry | Empty fields; no old value in state |
| 8 | Edge | Close/reopen in Settings/Workspace | Same server session hydrated |
| 9 | Edge | Ready completion | CloudAccess refresh/binding exactly once |
| 10 | Edge | Later preflight external action | Uses bounded connection; no admin prompt |

### Widgets/accessibility

| # | Type | Test | Hard assertion |
|---|---|---|---|
| 1 | Happy | Complete AWS and GCP forms by keyboard | Correct focus/order and submit state |
| 2 | Happy | Settings and Workspace open same active session | Same safe session ID/state rendered |
| 3 | Unhappy | Invalid target/secret | Exact inline errors; no API event |
| 4 | Unhappy | Safe server finding | Exact remediation/action; no raw response |
| 5 | Edge | 640/799/800/1439/1440 widths | Expected layout and zero overflow |
| 6 | Edge | 200% text/long guide | All text/actions reachable |
| 7 | Edge | Escape during execute | Flow remains open; focus stable |
| 8 | Edge | Show/hide then navigate | Secret is cleared and cannot return |
| 9 | Edge | Light/dark/semantics | Exact labels and non-color status |
| 10 | Edge | Advanced fallback disclosure | Labeled advanced; does not execute scripts/CLI |

### Real Management integration and commands

The Docker Management API must use deterministic fake provider adapters and
real HTTP. Integration covers all providers; owner isolation; duplicate
session/idempotency; successful bounded connection; partial failure/re-entry;
manual revocation; cancellation; Settings/workspace resume; subsequent Twin
preflight with the generated connection; and request/log/database scans proving
the bootstrap secret did not persist.

```bash
./thesis.sh test backend
./thesis.sh test deployment-contract
./thesis.sh test frontend
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration
docker --context orbstack compose --profile docs run --rm docs mkdocs build --strict
```

Run Web and available macOS/Linux release builds; Windows runs in CI. Teardown
must stop only services started by this run, including after failures; blanket
prune/down of user-owned containers is forbidden. Real AWS/Azure/GCP adapters
and paid resources remain forbidden in default verification.

### Documentation phase

After code/tests and before final review, update Phase 9, its roadmap, FR-002
and the FR tracker with exact implemented evidence; update Flutter README,
`FRONTEND_ARCHITECTURE.md`, Phase 8 bootstrap/service/access plans, and docs-site
setup/cloud-access/troubleshooting pages. Create
`twin2multicloud_flutter/docs/configuration_workspace/implementation/guided_cloud_bootstrap.md`
as the public component/state/API/security reference. Strict MkDocs, link, and
secret scans are mandatory. LaTeX remains untouched.

## 12. Definition of Done

- [ ] FR-002 guide/session contracts and deterministic fake provider adapters
      are committed before Flutter adapter work.
- [ ] Settings and Prepare Deployment use one shared flow and hydrate the same
      server-owned active session.
- [ ] All three provider forms follow guide-declared strict fields and collect
      no browser password.
- [ ] Administrator/bootstrap secrets are request-only, cleared in `finally`,
      absent from state, persistence, logs, responses, demo data, exports, and
      diagnostics.
- [ ] Only a validated bounded deployment CloudConnection persists.
- [ ] Release, expiry, provider revocation, manual cleanup, and user-owned
      validity remain truthful distinct states.
- [ ] Lost responses, duplicate commands, partial success, re-entry, restart,
      cancellation, revision conflict, and owner errors fail safely.
- [ ] Later deployment preflight uses bounded access and never requests the
      bootstrap secret again.
- [ ] Advanced manual import compatibility remains available and clearly
      secondary.
- [ ] Flutter uses Management API only; live/demo parity is strict.
- [ ] Analyzer, full tests, real Management integration, security scans,
      Web/macOS/Linux builds, and Windows CI pass without cloud creation.
- [ ] Accessibility/responsive/light-dark/200% text gates pass.
- [ ] Documentation is current and LaTeX remains unchanged.
- [ ] Clean `[AI-0803-BOOT]` commits and two zero-finding implementation reviews
      close the branch.

### Plan review record

| Pass | Perspective | Result |
|---|---|---|
| 1 | Architect | Zero unresolved findings on 2026-08-03 after proving the shared Settings/Workspace composition, separating durable Cloud Access inventory from bootstrap session workflow, reusing existing cloud widgets, and defining all wide/compact/error/manual-cleanup states |
| 2 | Builder | All 20 plan-review criteria pass on 2026-08-03 with zero unresolved findings after pinning strict request/response types, one-use secret ownership, uncertain-response/idempotency behavior, provider-specific tests, real-Management fake-adapter integration, exact OrbStack commands, documentation, and commit gates |
