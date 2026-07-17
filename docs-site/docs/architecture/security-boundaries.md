# Security And Trust Boundaries

## Credential Categories

| Category | Lifetime | Storage | Purpose |
|---|---|---|---|
| Management API JWT key | long-lived runtime secret | read-only Docker secret | sign application access tokens |
| Management API encryption key | long-lived runtime secret | read-only Docker secret | encrypt CloudConnection payloads |
| OAuth/SAML provider secret/key | long-lived runtime secret | deployment secret/config boundary | authenticate the Management API to an external IdP |
| login state/poll verifier | one short transaction | database digest; opaque value held by browser/client | correlate and consume an external login once |
| application access token | short-lived session | Flutter process memory plus revocable DB session ID | authorize Management API calls |
| bootstrap/admin credential | one operation | transient request memory | create scoped provider credentials |
| deployment CloudConnection | reusable, user-owned | encrypted database payload | validate and deploy a twin |
| pricing CloudConnection | reusable user default | encrypted database payload | refresh provider pricing |
| local credential overlay | development compatibility | ignored read-only files | supervised checks and sample seeding |

Runtime signing/encryption keys never grant cloud access. Cloud credentials are never
valid substitutes for application runtime secrets.

## Implemented Controls

- CloudConnections are owner-scoped and encrypted with Fernet-compatible key material.
- API responses expose metadata, not decrypted payloads.
- secret redaction is applied to downstream validation messages and logs;
- bound connections cannot be silently deleted into dangling references;
- credential operations are rate limited by operation class and authenticated user;
- production requires shared Redis-compatible limiter storage and fails closed on outage;
- credential security events are append-only, owner-scoped, and exclude secret values;
- production transport enforces HTTPS as reported only by trusted proxy networks;
- production CORS accepts only explicit HTTPS origins;
- upload/archive boundaries enforce limits, traversal protection, and secret-safe file listing;
- operation workspaces reject symlinks and synchronize only allowlisted outputs.
- external login transactions persist only digests for browser state and poll
  verifiers; Google PKCE verifiers are encrypted at rest;
- JWT issuer/audience/time claims are validated and every token is backed by a
  revocable server-side session;
- provider subjects, not email addresses, are identity keys and implicit account
  linking is forbidden;
- authentication endpoints have their own fail-closed distributed limiter and
  secret-free audit events.

## Authentication Status

Development authentication is an explicit non-production capability controlled by
`DEV_AUTH_ENABLED` and `DEV_AUTH_TOKEN`; it is not inferred from generic debug mode.

Google OAuth and UIBK SAML share a durable browser-transaction and session-exchange
boundary. The UIBK production path is **externally gated** by institutional SAML
registration, metadata, certificates, and approved callback values. The API exposes
that fact through provider capabilities; production never falls back to development
authentication.

## Known Operational Limits

- `ENCRYPTION_KEY` rotation requires an explicit transactional re-encryption process;
- SQLite is suitable for the local single-node deployment but not a horizontal multi-replica database;
- final provider least-privilege claims require supervised live-cloud evidence;
- live-cloud E2E tests can create cost and are never part of the safe default suite.

See [Cloud Setup](../cloud-setup/index.md) and
[Known Limitations and Verification Status](../runtime/known-limitations.md).
