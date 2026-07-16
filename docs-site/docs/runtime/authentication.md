# Authentication

Production authentication uses the same capability-driven external-browser and
one-time exchange contract on Web, macOS, Windows, and Linux. Platform support
does not change provider configuration or trust boundaries.

Twin2MultiCloud has three explicit runtime profiles. Development and demo are
local capabilities; production uses an external browser and a durable,
provider-neutral Management API session flow.

## Profile Behavior

| Profile | User experience | Trust boundary |
|---|---|---|
| `development` | explicit **Continue in local development** action | fixed bearer accepted only with `DEV_AUTH_ENABLED=true` outside production |
| `demo` | pre-authenticated fixture identity | no backend, browser login, token, or network adapter |
| `production` | enabled Google/UIBK actions are reported by the API | external provider callback plus one-time session exchange |

No profile falls back to another. Production rejects a development token, and
the Flutter client keeps production access tokens in process memory only.

## Production Data Flow

```text
Flutter                     Management API                Identity provider
   | POST /providers/{p}/login   |                               |
   |---------------------------->| create durable transaction    |
   | auth URL + poll verifier    | hash state/poll verifier       |
   |<----------------------------| encrypt Google PKCE verifier   |
   |                                                             |
   | open system browser ---------------------------------------->|
   |                                  verified callback <---------|
   |                                  consume callback state once |
   |                                  bind immutable provider sub |
   |                                                             |
   | POST /session/exchange      |                               |
   | transaction + poll verifier|                               |
   |---------------------------->| consume result once            |
   | JWT + user                  | create revocable DB session    |
   |<----------------------------|                               |
   | authenticated API requests |                               |
   |---------------------------->| validate JWT and active session|
```

The callback returns a minimal no-secret HTML page. It never redirects a JWT,
authorization result, or poll verifier to Flutter. Browser state and the
client-held poll verifier are different random values and are stored only as
digests. A transaction expires, can be cancelled, and can be consumed once.

## Provider Contracts

`GET /auth/providers` is the capability source of truth. Flutter renders only
providers reported by that endpoint and keeps disabled providers visible with
a safe availability reason.

### Google OAuth

- Authorization Code flow with PKCE S256 and a server-side client secret.
- Required scopes: `openid email profile`.
- The callback accepts only a matching, unexpired, one-time state.
- UserInfo must contain an immutable subject and a verified email address.
- The redirect URI must be HTTPS in production.

### UIBK SAML

- SP-initiated SAML 2.0 with signed AuthnRequests.
- Assertions must be signed and match the stored request ID through
  `InResponseTo`; unsolicited responses are rejected.
- NameID is the immutable provider subject; `mail` is required and
  `displayName`/`cn` is optional.
- `GET /auth/uibk/metadata` serves the configured SP metadata only while SAML
  is fully enabled.

## Identity And Session Policy

`external_identities` owns the unique `(provider, subject)` binding. Email is
profile data, not an identity key. A first login creates a user only when no
existing user has that email. If the email already exists under another
identity, login fails with `IDENTITY_LINK_REQUIRED`; there is no implicit email
linking.

Issued JWTs contain `sub`, `jti`, `iss`, `aud`, `iat`, `nbf`, and `exp`. Every
authenticated request also resolves the `jti` against `auth_sessions`, so
logout revokes the server-side session immediately. Expired, revoked, unknown,
or malformed sessions return `401` and Flutter clears its in-memory token.

## Persistence And Audit

The explicit database migration creates:

| Table | Purpose |
|---|---|
| `external_identities` | immutable provider-subject bindings |
| `auth_login_transactions` | short-lived state, callback and exchange lifecycle |
| `auth_sessions` | expiry and revocation record for each JWT |
| `authentication_events` | append-only, secret-free security evidence |

Legacy Google/UIBK IDs are migrated into `external_identities`. Authentication
events contain action, outcome, provider, transaction/user references, HTTP
status, request ID, and timestamp, but no state, verifier, token, assertion, or
provider response.

## Security Controls

- login and exchange endpoints have separate moving-window limits;
- production requires shared `redis://` or `rediss://` limiter storage and
  fails closed when that control is unavailable;
- provider and callback errors use stable public error codes;
- callback HTML uses `no-store`, a deny-all CSP, `no-referrer`, and `nosniff`;
- production callbacks, CORS origins, and API transport require HTTPS;
- Management API access logging is disabled in the container so OAuth query
  parameters are not copied into access logs;
- any edge proxy must likewise omit or redact callback query strings.

## Configuration

Common settings:

| Setting | Purpose |
|---|---|
| `JWT_SECRET_KEY`, `JWT_ALGORITHM` | sign access tokens; HMAC algorithms only |
| `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_EXPIRE_MINUTES` | validate token scope and lifetime |
| `AUTH_TRANSACTION_TTL_SECONDS`, `AUTH_POLL_INTERVAL_MS` | browser transaction lifetime/client polling |
| `AUTH_RATE_LIMIT_ENABLED`, `AUTH_RATE_LIMIT_STORAGE_URI` | shared abuse-control boundary |
| `AUTH_LOGIN_RATE_LIMIT`, `AUTH_EXCHANGE_RATE_LIMIT` | per-actor operation limits |

Google requires the complete tuple `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`. UIBK requires
`SAML_ENABLED=true` plus all SP and IdP fields documented in the
[UIBK activation section](#external-uibk-activation-gate).

## External UIBK Activation Gate

The implementation is complete locally, but live UIBK login remains externally
blocked by `#49 Document and resolve UIBK login prerequisites`. Activation
requires UIBK/ACOnet coordination for the public HTTPS domain, exact entity and
ACS identifiers, SP certificate lifecycle, IdP metadata/signing certificate,
released attributes, test identities, and federation approval. Localhost is
not a valid production ACS URL.

This external gate does not justify a dev-token production fallback. Until the
institutional configuration exists, `GET /auth/providers` reports UIBK as
disabled and Flutter explains that it is unavailable.

## Verification

```bash
./thesis.sh test backend
./thesis.sh test frontend
curl http://localhost:5005/auth/providers
```

Deterministic tests cover expiry, cancellation, replay, invalid verifier/state,
identity collision, Google PKCE and verified-email parsing, SAML request
correlation, session revocation, rate limiting, migration, Flutter polling,
browser failure, cancellation, and `401` handling. Real UIBK authentication can
only be proven after the external activation gate is satisfied.
