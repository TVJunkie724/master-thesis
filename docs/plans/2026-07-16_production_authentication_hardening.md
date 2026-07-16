# Implementation Plan: Production Authentication Hardening

## 0. Git Branch

- **Branch:** `codex/production-auth-hardening`
- **Base:** `master`
- **Merge strategy:** merge commit, never rebase
- **GitHub owner:** `#10 Implement production authentication and UIBK login path`
- **External live gate:** `#49 Document and resolve UIBK login prerequisites`

Every item in this plan is mandatory unless it is explicitly listed as a
non-goal. The external UIBK registration blocks only live federation activation
and live-provider E2E evidence. It does not block local implementation, contract
tests, SAML validation tests, or documentation.

## 1. Summary

Replace the current demo-grade OAuth/SAML boundary with a durable,
provider-neutral login transaction and server-side session model. Flutter must
start production login through the Management API, open the provider URL in the
system browser, and poll with a separate one-time verifier. Provider callbacks
must never expose the verifier or a JWT. A successful session exchange returns a
short-lived JWT exactly once; authenticated requests validate both JWT claims and
the server-side session, so logout and expiry are enforceable.

Google and UIBK remain the implemented providers. The provider contract must
allow another OAuth/OIDC or SAML provider without changing route, transaction,
session, or Flutter state-machine semantics.

## 2. Visual Layout

Production login, all supported desktop and Web widths:

```text
+--------------------------------------------------------------+
|                      Twin2MultiCloud                         |
|             Multi-cloud Digital Twin Platform               |
|                                                              |
|  Sign in                                                     |
|  Use an identity provider enabled by this deployment.        |
|                                                              |
|  [ university ]  Sign in with UIBK                           |
|  [ account    ]  Sign in with Google                         |
|                                                              |
|  Provider availability or a sanitized inline error           |
+--------------------------------------------------------------+
```

While an external browser login is pending:

```text
+--------------------------------------------------------------+
|                      Twin2MultiCloud                         |
|                                                              |
|                 (progress indicator)                         |
|            Complete sign-in in your browser.                 |
|       This window will continue automatically afterwards.    |
|                                                              |
|                  [ Cancel sign-in ]                           |
+--------------------------------------------------------------+
```

The existing compact centered authentication surface is retained. No extra
screen, provider card grid, callback screen, modal, or verbose security copy is
introduced. At compact Web widths the same controls remain a single vertical
column within the existing page padding.

## 3. Widget Tree

```text
LoginScreen [MODIFY]
`-- AuthSurface [REUSE existing screen structure]
    |-- BrandHeader [REUSE]
    `-- Consumer/auth state branch [MODIFY]
        |-- ProviderCapabilityLoading [NEW private widget]
        |-- ProviderActions [NEW private widget]
        |   |-- ProviderButton(UIBK) [REUSE FilledButton.icon]
        |   `-- ProviderButton(Google) [REUSE FilledButton.icon]
        |-- ExternalLoginPending [NEW private widget]
        |   |-- CircularProgressIndicator [REUSE]
        |   `-- CancelButton [REUSE TextButton]
        `-- InlineAuthError [NEW private widget]

routerProvider [MODIFY]
`-- removes obsolete /auth/callback placeholder

authProvider / AuthNotifier [MODIFY]
`-- owns app-global identity and login transaction lifecycle
```

Auth stays in Riverpod because it is app composition and a global route guard,
not a feature-local multi-step workflow. Existing feature workflows continue to
use BLoC. No second auth state machine is introduced.

## 4. Component And Contract Specifications

### Management API persistence

Add four explicit SQLAlchemy models and idempotent SQLite migration `018`:

1. `external_identities`: unique `(provider, subject)`, user foreign key,
   verified email snapshot, created/last-login timestamps.
2. `auth_login_transactions`: UUID, provider, purpose, SHA-256 state and poll
   verifier digests, encrypted PKCE verifier when applicable, SAML request ID,
   status, user/error result, one-time callback/exchange timestamps, expiry.
3. `auth_sessions`: JWT `jti`, user foreign key, issued/expiry/revocation
   timestamps.
4. `authentication_events`: append-only, secret-free evidence containing a
   closed action/outcome/provider set, optional user and transaction IDs,
   request ID, HTTP status and occurrence time.

Existing provider IDs are migrated into `external_identities`. New code must not
read or write provider-specific identity columns. Existing physical columns may
remain in upgraded SQLite files because destructive table reconstruction is out
of scope; fresh schemas and ORM ownership use the provider-neutral table.

### Provider-neutral API

| Method | Path | Contract |
|---|---|---|
| GET | `/auth/providers` | typed provider capabilities, including enabled state and safe reason code |
| POST | `/auth/providers/{provider}/login` | auth URL, transaction ID, one-time poll verifier, expiry, poll interval |
| GET | `/auth/google/callback` | validates state, PKCE-bound Google response and verified email, completes transaction, returns no secrets |
| POST | `/auth/uibk/callback` | validates RelayState, signature/assertion and stored SAML request ID, completes transaction, returns no secrets |
| POST | `/auth/session/exchange` | pending/failed result or one-time access token and current user |
| POST | `/auth/session/cancel` | verifies transaction plus poll verifier and invalidates pending server state |
| POST | `/auth/logout` | revokes the current server-side session |
| GET/PATCH | `/auth/me` | unchanged typed current-user boundary, linked providers derived from identities |

Login initiation is a `POST` because it creates durable state and must not be
cached. Old provider-specific login-initiation endpoints are removed rather than
retained as aliases.

### Transaction service

- Generate independent 256-bit state and poll verifier values.
- Persist only SHA-256 digests of values that need comparison.
- Encrypt the Google PKCE verifier with the existing application master key and
  a transaction-specific scope because it must be recovered for code exchange.
- Enforce provider match, purpose match, expiry, single callback, and single
  session exchange with conditional database updates.
- Persist only closed error codes, never provider payloads, assertions, tokens,
  authorization codes, or exception strings.
- Persist append-only authentication events for initiation, callback outcome,
  exchange, cancellation and logout. Event data must correlate an incident by
  request/transaction without containing provider payloads or secrets.
- Delete or expire stale transaction material through opportunistic bounded
  cleanup during initiation; correctness must not depend on a background job.

### Identity resolution

- Resolve an account only by the immutable provider subject.
- Require Google `email_verified=true`.
- Create a new user only when neither subject nor normalized email exists.
- Never auto-link an existing account by matching email.
- Return `IDENTITY_LINK_REQUIRED` when a verified provider identity collides
  with an existing email; do not issue a session.
- Update display metadata and last-login timestamps only after a verified
  identity has resolved successfully.

Explicit account-linking UI is a non-goal for this slice. Safe refusal is the
required behavior until a dedicated authenticated linking workflow is planned.

### Session and JWT

- JWTs must include `sub`, `jti`, `iat`, `nbf`, and `exp`.
- JWT algorithm is restricted to the configured supported HMAC allowlist.
- Every non-development bearer request must resolve an unexpired, unrevoked
  `auth_sessions` row matching `sub` and `jti`.
- Logout revokes that row and clears the Flutter in-memory token.
- Flutter does not persist the production bearer to preferences, local storage,
  files, or logs. App restart deliberately requires a new login.

### Provider hardening

Google must use authorization-code flow with PKCE S256, exact configured redirect
URI, explicit HTTP status checks, required subject/email fields, and verified
email. UIBK must use strict validation, the configured ACS origin rather than
caller-controlled host headers, RelayState, and `InResponseTo` validation using
the stored AuthnRequest ID. Provider/library failures are translated to stable,
sanitized application errors.

## 5. Responsive Behavior

| Width | Required behavior |
|---|---|
| `>= 800 px` | centered existing auth surface at `AppSpacing.authCardMaxWidth` |
| `< 800 px` | same one-column hierarchy inside existing compact page padding; buttons remain full width |

The layout must remain stable at text scale 1.5. No font size is derived from
viewport width. Provider labels wrap rather than overflow.

## 6. State Flow

`AuthNotifier` owns the global auth lifecycle:

- `loadingCapabilities`
- `ready(capabilities)`
- `startingProvider(provider)`
- `waitingForBrowser(transaction)`
- `exchangingSession`
- `authenticated(user)`
- `error(capabilities, safeMessage)`

```text
LoginScreen
  -> AuthNotifier.startExternalLogin(provider)
  -> ManagementApi POST /auth/providers/{provider}/login
  -> system browser opens provider URL
  -> provider redirects/posts to Management API callback
  -> Management API verifies provider and completes durable transaction
  -> AuthNotifier polls POST /auth/session/exchange with private poll verifier
  -> Management API atomically creates session and returns JWT once
  -> ApiService installs in-memory bearer
  -> AuthNotifier loads typed current user and router enters Dashboard
```

Polling must use the server-provided interval, stop on cancellation/disposal,
stop at transaction expiry, tolerate a bounded set of transient transport
failures, and never run in development or demo profiles. `url_launcher` is
wrapped by an injected `ExternalAuthLauncher` so unit/widget tests do not open a
real browser.

## 7. Design Tokens

Reuse `AppSpacing.authCardMaxWidth`, `authLogoSize`, `md`, `lg`,
`actionButtonHeight`, and Material theme color/text roles. Add only a polling
interval-independent spacing token if the existing scale cannot express a
required value. No new color palette, package-specific icon set, inline color,
or inline `TextStyle` is permitted.

## 8. Interactions And Error Handling

- Provider buttons are rendered only after capabilities load and enabled only
  when the backend capability is enabled.
- A provider initiation immediately disables all provider actions.
- Successful browser launch enters the pending state; failed launch returns a
  sanitized retryable inline error.
- Cancel stops local polling and calls the verifier-authenticated cancellation
  command so pending server state is invalidated immediately.
- Pending exchange is normal state, not an error or snackbar loop.
- Expired, replayed, identity-conflict, provider-validation, and transport
  failures map to concise user messages; raw provider details stay server-side
  and secret-free.
- No automatic retry can create a second login transaction without a user
  command.

No animations beyond the existing Material progress indicator and fast theme
transitions are introduced.

## 9. Accessibility

- Focus order: first enabled provider, second enabled provider, cancel/retry.
- Buttons expose provider and action through visible text and semantics.
- Progress state is announced as a live status without repeatedly stealing
  focus on every poll.
- All states meet Material theme contrast and remain keyboard operable.
- Disabled providers include a concise visible reason when no provider is
  available, rather than relying on tooltip-only information.

## 10. Integration And Configuration

Required backend configuration:

- `AUTH_TRANSACTION_TTL_SECONDS` and `AUTH_POLL_INTERVAL_MS` with bounded
  validation;
- existing JWT lifetime and secrets;
- complete Google tuple: client ID, client secret, exact callback URI;
- complete SAML tuple when enabled: SP entity/ACS/cert/key and IdP
  entity/SSO/cert.

Partial provider configuration must fail startup. A completely absent provider
configuration means that provider is safely disabled. Production SAML and Google
callbacks must use HTTPS. The public capability response must not contain secret
configuration values.

Anonymous initiation and poll/exchange commands must use the existing shared
production rate-limit infrastructure with auth-specific quotas and hashed actor
keys. Production startup must fail if this control is not backed by Redis. A
rate-limit storage outage fails closed with the standard structured API error.
Auth domain failures must use the Management API `ErrorResponse` shape and closed
error codes; raw provider exceptions must never become response bodies.

Flutter talks only to the Management API. The obsolete `/auth/callback` Flutter
route and `FRONTEND_CALLBACK_URL` backend setting are removed because the polling
exchange has no browser-to-app secret transport.

## 11. Test And Verification Plan

### Backend unit and integration tests

- provider capability combinations: absent, partial startup rejection, complete;
- transaction creation stores only digests/encrypted verifier;
- authentication audit events are complete, append-only and secret-free;
- auth initiation/exchange quotas and fail-closed storage behavior;
- wrong state, wrong provider, expired state, callback replay, exchange replay;
- pending exchange, expiry, wrong poll verifier, transient concurrent exchange;
- immutable-subject login, new account, verified-email requirement, email
  collision without auto-linking;
- JWT/session match, expiry, revocation, logout, malformed claims;
- Google PKCE and safe upstream response handling using HTTP mock transport;
- SAML request-ID propagation and sanitized validation failures using provider
  test doubles;
- migration idempotency and legacy identity copy;
- OpenAPI schemas and route authentication policy.

### Flutter unit and widget tests

- capability parsing and malformed-contract rejection;
- provider initiation, browser-launch success/failure, pending polling,
  completion, cancellation, expiry and sanitized errors;
- bearer installation and removal, unauthorized-session signal, disposal;
- production login loading/ready/pending/error states;
- development and demo behavior remain unchanged;
- keyboard/text-scale/compact-width layout has no overflow or secret output.

### Required commands

```bash
docker --context orbstack compose run --rm management-api pytest -q
docker --context orbstack compose run --rm management-api bandit -r src -q
cd twin2multicloud_flutter && flutter analyze
cd twin2multicloud_flutter && flutter test
cd twin2multicloud_flutter && flutter build web --dart-define-from-file=config/production.example.json
cd twin2multicloud_flutter && flutter build macos --dart-define-from-file=config/production.example.json
docker --context orbstack compose --profile docs run --rm docs mkdocs build --strict
```

No real cloud deployment and no live Google/UIBK authentication are part of
automated verification. Live UIBK evidence remains explicitly gated by
`#49 Document and resolve UIBK login prerequisites`.

## 12. Definition Of Done

- [x] Durable expiring login transactions work across backend instances.
- [x] Callback and session exchange are each one-time and replay-safe.
- [x] Login cancellation invalidates both local polling and durable pending state.
- [x] No JWT, poll verifier, provider token, code, assertion, or secret appears
      in redirects, persisted diagnostics, API logs, or UI text.
- [x] External identities use immutable provider subjects and never auto-link by
      email.
- [x] Google PKCE/verified-email and UIBK request-ID/signature boundaries are
      enforced.
- [x] JWTs are backed by revocable server sessions and logout is effective.
- [x] Auth endpoints are rate-limited through shared production storage and all
      security-relevant transitions emit secret-free audit evidence.
- [x] Flutter production login is capability-driven and works on Web and macOS
      through the system-browser plus polling flow.
- [x] Development and isolated demo auth behavior does not regress.
- [x] Migration, backend, contract, Flutter, build, Bandit, and strict docs gates
      pass.
- [x] Authentication, configuration, component, security, setup, and user docs
      describe the implemented state and the remaining external UIBK live gate.
- [x] Two implementation review passes have no unresolved findings.
- [x] Structured commits reference `#10 Implement production authentication and
      UIBK login path`; the user-owned Azure pricing JSON is never staged.
