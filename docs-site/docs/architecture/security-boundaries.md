# Security And Trust Boundaries

## Credential Categories

| Category | Lifetime | Storage | Purpose |
|---|---|---|---|
| Management API JWT key | long-lived runtime secret | read-only Docker secret | sign application access tokens |
| Management API encryption key | long-lived runtime secret | read-only Docker secret | encrypt CloudConnection payloads |
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

## Authentication Status

Development authentication is an explicit non-production capability controlled by
`DEV_AUTH_ENABLED` and `DEV_AUTH_TOKEN`; it is not inferred from generic debug mode.

Google OAuth and UIBK SAML provider boundaries exist in the Management API. The UIBK
production path is **externally gated** by institutional SAML registration, metadata,
certificates, and approved callback values. Until that setup and a final auth security
review are complete, documentation must not present production login as available.

## Known Operational Limits

- `ENCRYPTION_KEY` rotation requires an explicit transactional re-encryption process;
- SQLite is suitable for the thesis/local deployment but not a horizontal multi-replica database;
- final provider least-privilege claims require supervised live-cloud evidence;
- live-cloud E2E tests can create cost and are never part of the safe default suite.

See [Cloud Setup](../cloud-setup/index.md) and
[Limitations and Evidence](../thesis/limitations-and-evidence.md).
