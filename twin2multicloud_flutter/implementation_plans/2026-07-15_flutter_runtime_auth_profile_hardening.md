# Implementation Plan: Flutter Runtime And Development Auth Profile Hardening

## 0. Git Branch

- **Branch name:** `codex/flutter-dev-auth-hardening`
- **Base branch:** `master` at `0e87213`
- **Merge strategy:** merge commit; no rebase
- **Primary issue:** [#71](https://github.com/TVJunkie724/master-thesis/issues/71)
- **Related future issue:**
  [#10](https://github.com/TVJunkie724/master-thesis/issues/10) owns real
  production OAuth/SAML login, callback handling, and token lifecycle.
- **Safety boundary:** the user-owned local modification at
  `2-twin2clouds/json/fetched_data/pricing_dynamic_azure.json` must never be
  staged, rewritten, inspected as input, or included in verification.

## 1. Summary

This phase removes silent development authentication from Flutter's default
runtime. Today, absent Dart defines select `development`, `ApiService` silently
loads `dev-token`, and the login screen exposes `Skip Login (Development)` in
every non-demo mode. The backend already confines dev auth to explicit
development/test environments, but the Flutter client does not enforce the
same boundary.

The target state is one validated runtime configuration value object:

- **development:** explicit Management API URL and explicit development token;
- **production:** explicit HTTPS Management API URL and no initial token;
- **demo:** no URL, token, network adapter, or login interaction.

Production remains fail-closed until #10 supplies a real authentication flow.
This phase must not parse callback tokens, persist JWTs, enable disabled OAuth
buttons, or create a placeholder production session.

The existing state-management decision remains binding: Riverpod owns runtime
composition, auth, theme, routing, and adapter injection; BLoC owns complex
feature workflows. No state-management migration is in scope.

## 2. Visual Layout

Only the existing Login screen changes. Dashboard, Configuration Workspace,
Pricing Review, Settings, and Twin Overview layouts remain unchanged.

```text
Development, desktop and Web >= 640 px
+--------------------------------------------------------------+
|                       Twin2MultiCloud                         |
|              Multi-cloud Digital Twin Platform               |
|                                                              |
|              [ Continue in local development ]               |
|                                                              |
|  Local development profile. Requests use the explicitly      |
|  configured local Management API identity.                   |
+--------------------------------------------------------------+

Production, desktop and Web >= 640 px (until #10)
+--------------------------------------------------------------+
|                       Twin2MultiCloud                         |
|              Multi-cloud Digital Twin Platform               |
|                                                              |
|                [ Sign in with UIBK ] disabled                 |
|                [ Sign in with Google ] disabled               |
|                                                              |
|  Production sign-in is not configured in this build.         |
+--------------------------------------------------------------+

Demo
+--------------------------------------------------------------+
| Login route redirects to Dashboard through the fixture user. |
| No login card and no network-backed auth action is exposed.   |
+--------------------------------------------------------------+
```

The card keeps its existing constrained width and stacks identically on Web
and desktop. Mobile remains unsupported. At 640 px, page padding must use the
existing spacing tokens and the card must fit without horizontal overflow.

## 3. Component And File Tree

```text
twin2multicloud_flutter/
|-- config/
|   |-- dev.example.json                                  [REUSE]
|   |-- demo.json                                         [REUSE]
|   `-- production.example.json                           [NEW]
|-- lib/
|   |-- config/
|   |   |-- api_config.dart                               [REMOVE]
|   |   |-- app_runtime.dart                              [MODIFY]
|   |   `-- runtime_composition.dart                      [MODIFY]
|   |-- providers/
|   |   |-- auth_provider.dart                            [MODIFY]
|   |   `-- runtime_providers.dart                        [MODIFY]
|   |-- screens/
|   |   `-- login_screen.dart                             [MODIFY]
|   |-- theme/
|   |   `-- spacing.dart                                  [MODIFY]
|   `-- services/
|       |-- api_service.dart                              [MODIFY]
|       `-- management_api.dart                           [MODIFY]
|-- integration_test/
|   `-- management_api_readiness_test.dart                [MODIFY]
|-- test/
|   |-- config/app_runtime_test.dart                      [MODIFY]
|   |-- config/runtime_composition_test.dart              [MODIFY]
|   |-- providers/auth_provider_test.dart                 [NEW]
|   |-- screens/login_screen_test.dart                    [NEW]
|   `-- services/api_service_auth_profile_test.dart       [NEW]
|-- test/widget_test.dart                                 [MODIFY]
`-- docs/frontend_architecture_refactoring/
    `-- phases/PHASE_01_ARCHITECTURE_BASELINE.md           [MODIFY]

scripts/check_flutter_architecture.py                     [MODIFY]
scripts/tests/test_check_flutter_architecture.py           [MODIFY]
HANDBOOK.md                                                [MODIFY]
```

No backend, Optimizer, Deployer, credential, pricing-result, or LaTeX file is
modified by this phase.

## 4. Component Specifications

### 4.1 `AppRuntimeConfig`

`AppRuntimeConfig` becomes the immutable SSOT for runtime mode and network/auth
bootstrap data. Invalid combinations must be impossible to construct through
public factories.

| Factory | Required input | Stored network/auth state |
|---|---|---|
| `development` | absolute HTTP(S) Management API URI, non-empty dev token | URI + token |
| `production` | absolute HTTPS Management API URI | URI, no token |
| `demo` | optional supported fixture scenario | no URI, no token |
| `fromEnvironment` | explicit `APP_MODE` plus profile-specific defines | delegates to the factories |
| `fromValues` | raw strings for deterministic unit tests | same validation as environment |

Validation is binding:

- `APP_MODE` has no default; absent and blank values fail with a sanitized
  `StateError` naming the missing key.
- Networked modes require `API_BASE_URL` with scheme, host, no user info, query,
  fragment, or non-root path.
- Production requires `https` and rejects any `DEV_AUTH_TOKEN` value.
- Development accepts `http` or `https` and requires a non-empty token without
  whitespace or control characters.
- Demo rejects both URL and token defines so it cannot accidentally gain a
  network dependency.
- Error text names keys and rules only; it never includes token values.

Getters expose `managementApiBaseUri` and `initialAuthToken`. The latter returns
the development token only in development. No `toString`, equality props,
diagnostic map, or exception may include the token.

### 4.2 `ApiService`

Remove static access to `ApiConfig`. `ApiService` receives configuration:

| Parameter | Type | Required | Rule |
|---|---|---|---|
| `dio` | `Dio?` | no | Unit-test/injected transport; its existing base URL is retained |
| `baseUri` | `Uri?` | when `dio == null` | Required for production transport construction |
| `initialAuthToken` | `String?` | no | Used by explicit integration/session construction only; added only when non-empty |

Construction fails if neither a configured `Dio` nor `baseUri` is supplied.
The token stays private and mutable only through the auth port. Change
`ManagementApi.setToken` to accept `String?`: non-empty values set a bearer,
while `null` clears it. Empty/blank values are rejected rather than interpreted
ambiguously.
`getSseUrl` resolves relative SSE paths against the instance base URI and must
not read global configuration. Existing API behavior and DTOs remain unchanged.

### 4.3 Runtime Composition And Providers

`RuntimeComposition.bootstrap` must:

1. return only fixture adapters and fixture identity for demo;
2. construct a token-free `ApiService` with the validated URI for development;
3. construct the same token-free adapter for production; and
4. construct `SseService` from the same URI and the adapter's token provider.

Riverpod fallback providers derive adapters from `appRuntimeProvider`; they may
not call a parameterless `ApiService` or read another config singleton.

### 4.4 Auth Provider

Rename `mockLogin` to `continueInDevelopment`. It must read
`appRuntimeProvider`, throw a value-free `StateError` outside development, set
the validated development token on `apiServiceProvider`, and hydrate the
existing deterministic local user only in development. Demo remains
authenticated through `initialUserProvider`; production starts unauthenticated.

Logout must call `setToken(null)` before clearing UI auth state, so HTTP and SSE
cannot continue with a stale bearer. Server-side revocation and persisted-token
deletion belong to #10 because this phase introduces no production token store.

### 4.5 Login Screen

`LoginScreen` remains a `ConsumerWidget` and reads only `authProvider` plus
`appRuntimeProvider`.

- Development renders one explicit local-development command.
- Production does not render a development bypass. Existing OAuth/SAML buttons
  remain disabled and explain that #10's production flow is unavailable.
- Demo normally redirects before rendering; defense-in-depth rendering contains
  no development action.
- No token, endpoint, callback query, or credential value is shown.

No new widget is justified: the existing Login screen and Material controls are
sufficient. Existing theme styles and spacing tokens must be used; no new color
or typography system is introduced.

### 4.6 Tracked Runtime Templates

`production.example.json` contains only:

```json
{
  "APP_MODE": "production",
  "API_BASE_URL": "https://management.example.invalid"
}
```

It is documentation/build input only and contains no usable token. Development
and demo templates retain their current explicit profiles.

### 4.7 Architecture Checker

Move the approved runtime-key owner from removed `api_config.dart` to
`app_runtime.dart`; approve the two tracked networked templates and keep
`demo.json` forbidden from containing URL/token keys. Add a rule/test proving a
concrete `DEV_AUTH_TOKEN` default outside the development template fails. Secret
diagnostics remain redaction-safe.

## 5. Responsive Behavior

| Width | Required behavior |
|---|---|
| `>= 1440 px` | Existing 400 px login card remains centered; no extra side panels |
| `800-1439 px` | Same centered layout with bounded page padding |
| `640-799 px` | Card shrinks within available width; actions remain full-width and text wraps |
| `< 640 px` | Unsupported platform width; no new mobile contract is introduced |

No other screen changes. Light and dark themes must retain readable disabled
and informational text.

## 6. State And Data Flow

No feature BLoC changes are required.

```text
Dart defines
  -> AppRuntimeConfig.fromEnvironment (validate once)
  -> RuntimeComposition
       |-- demo -> DemoManagementApi + fixture user
       `-- networked -> token-free ApiService(baseUri)
                        + SseService(same baseUri, token provider)
  -> Riverpod overrides
       |-- authProvider
       |-- apiServiceProvider
       `-- logStreamClientFactoryProvider

Development Login command
  -> AuthNotifier.continueInDevelopment
  -> verify runtime.mode == development
  -> ManagementApi.setToken(runtime.initialAuthToken)
  -> deterministic local User state
  -> router redirects to Dashboard

Production
  -> no initial token
  -> no development login command
  -> unauthenticated Login state until #10 supplies real auth
```

Widgets never call Dio or Management API directly. Flutter continues to contact
only the Management API.

## 7. Design Tokens

The Login screen must use existing
`ThemeData`, `AppSpacing`, and the current Material icon set. Add only two
stable dimensions that have no current equivalent: `authCardMaxWidth = 400`
and `authLogoSize = 96`. Replace the touched card padding, gaps, radius,
elevation, and action height with existing tokens. Remove the hardcoded UIBK
disabled color override and let `ThemeData` provide accessible disabled colors.
Broad visual redesign remains out of scope.

## 8. Interactions And States

| State | UI behavior |
|---|---|
| Development idle | one enabled `Continue in local development` action |
| Development loading | existing stable progress indicator; duplicate command unavailable |
| Development success | router redirects to Dashboard |
| Production idle | OAuth/SAML buttons disabled; no development action |
| Production unavailable | concise inline explanation, no retry that cannot work |
| Demo | fixture-authenticated redirect; no login interaction |
| Invalid runtime config | app bootstrap fails before `runApp` with sanitized key/rule error |

No new animations are introduced. Existing button/progress transitions remain.
The status block uses `Icons.info_outline` plus text; the current emoji prefix
is removed so semantics and rendering do not depend on a decorative glyph.

## 9. Accessibility

- Development has one unambiguous, keyboard-focusable primary action.
- Disabled production buttons retain visible labels and are accompanied by
  explanatory text, not color alone.
- Loading state exposes a semantic progress indicator.
- Informational text contains no emoji-only status semantics.
- Focus order remains logo, heading, description, available action(s), status.
- Text scales and wraps at 640 px without clipping.

## 10. Integration Points

No endpoint is added or changed.

| Method | Path | Used in this phase | Notes |
|---|---|---|---|
| GET | `/auth/me` | existing authenticated calls only | Development uses explicit dev bearer; production has none initially |
| GET | existing Phase 9 read endpoints | integration regression | Proves development profile still authenticates |
| GET | `/auth/google/login` | not wired | Owned by #10 |
| GET | `/auth/uibk/login` | not wired | Owned by #10 |

The `/auth/callback` placeholder is not extended. Query-string JWT transport,
secure token storage, refresh/expiry, browser deep links, and logout revocation
must be designed and implemented in #10.

## 11. Test Plan

### 11.1 Runtime Configuration Unit Tests

Happy paths:

1. explicit development URL/token creates the development profile;
2. explicit HTTPS production URL creates a token-free profile;
3. demo scenarios create a network-free profile.

Unhappy paths:

1. missing/blank `APP_MODE` fails;
2. development without token or URL fails;
3. production with a dev token or HTTP URL fails;
4. demo with a URL or token fails.

Edge paths:

1. aliases and surrounding mode whitespace normalize;
2. URL with user info is rejected;
3. URL with query or fragment is rejected;
4. URL with a non-root path is rejected;
5. token with whitespace/control characters is rejected without echoing it;
6. trailing root slash normalizes without malformed request paths;
7. unsupported demo scenario fails without constructing adapters.

### 11.2 Adapter And Composition Unit Tests

Happy paths:

1. development auth sets exactly the configured bearer token;
2. production requests contain no Authorization header;
3. `setToken` enables a later production session without rebuilding adapters;
4. SSE URL resolution uses the instance Management API base URI.

Unhappy paths:

1. parameterless transport construction fails;
2. invalid absolute SSE URLs remain rejected by existing typed contracts.

Edge paths:

1. injected Dio is accepted without global config;
2. empty initial token is treated as absent;
3. repeated requests do not duplicate Authorization headers;
4. logout clears the HTTP/SSE token and does not leak token text into diagnostics;
5. demo composition creates no Dio/SSE adapter;
6. production and development use the same Management API host for HTTP/SSE.

### 11.3 Auth And Login Tests

Happy paths:

1. development shows the local command and authenticates the deterministic
   user exactly once;
2. demo fixture identity starts authenticated.

Unhappy paths:

1. production hides the local command;
2. calling `continueInDevelopment` in production throws and preserves an
   unauthenticated state.

Edge paths:

1. duplicate development click is unavailable while loading;
2. production disabled provider labels remain visible;
3. demo `/login` redirects to Dashboard;
4. logout returns development to Login without changing runtime mode;
5. compact 640 px development and production cards do not overflow;
6. dark/light themes render the mode-specific explanation;
7. no semantics tree contains token or API URL values.

All app-level widget tests that previously relied on provider defaults must
override `appRuntimeProvider` explicitly. `widget_test.dart` becomes the
regression proof that a test process with no Dart defines can still render only
when its intended runtime is supplied.

### 11.4 Real Local Integration

Run the existing credential-free Phase 9 integration target with generated
development config. It must still pass all eight hard contract assertions
against the real Management API. Add no production OAuth integration test until
#10 exists; a mocked OAuth flow would be misleading.

Required commands:

```bash
python3 -m unittest scripts.tests.test_check_flutter_architecture
python3 scripts/check_flutter_architecture.py
bash -n thesis.sh
./thesis.sh test frontend
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration
flutter build web --release --dart-define-from-file=config/production.example.json
docker --context orbstack compose -f compose.yaml --profile docs --profile latex config --quiet
git diff --check
```

No live cloud E2E, provider validation, pricing refresh, deployment, destroy, or
simulator cloud operation is allowed.

## 12. Definition Of Done

- [ ] `AppRuntimeConfig` is the only Flutter runtime URL/dev-auth SSOT.
- [ ] Missing `APP_MODE` fails closed; no mode silently defaults to development.
- [ ] Development requires explicit URL and token.
- [ ] Production requires HTTPS and cannot carry an initial development token.
- [ ] Demo cannot contain URL/token configuration or network adapters.
- [ ] `ApiConfig` and parameterless production `ApiService` construction are removed.
- [ ] HTTP and SSE use the same injected Management API URI.
- [ ] Development bypass is visible and callable only in development.
- [ ] Development login sets the configured token; logout clears it from the
      shared HTTP/SSE auth port.
- [ ] Production remains unauthenticated and visibly unavailable until #10;
      no fake OAuth, callback token parsing, or token persistence is added.
- [ ] Riverpod/BLoC ownership is documented and unchanged.
- [ ] Runtime, adapter, composition, auth, login, and checker tests pass with
      exact happy, unhappy, and edge assertions.
- [ ] Existing real Management API integration passes without cloud credentials.
- [ ] `flutter analyze` reports zero issues.
- [ ] Complete Flutter suite passes without weakened assertions.
- [ ] Web release and macOS debug builds pass from explicit development config.
- [ ] Web release build passes from the token-free production template.
- [ ] Architecture checker and its unit tests pass redaction-safely.
- [ ] Handbook, frontend architecture baseline, #71, and #10 boundary are synchronized.
- [ ] Two review passes have no unresolved Critical, Major, or Minor findings.
- [ ] Structured commits are merged to `master`; the user-owned pricing file is
      never staged.
