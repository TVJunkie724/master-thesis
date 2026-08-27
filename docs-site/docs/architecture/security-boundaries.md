# Security and trust boundaries

Twin2MultiCloud is a single-user research PoC. It does not claim production
authentication, role management, multi-tenancy or a complete provider
credential lifecycle.

## Secret classes

| Secret | Owner | Runtime use |
|---|---|---|
| Management signing/encryption keys | local operator | local session and encrypted CloudConnection storage |
| provider deployment administrator credential | operator | identity probe, graph readiness, confirmed preparation and deployment |
| Twin-scoped runtime identity | deployed infrastructure | only the graph edge or component that requires it |
| service-local Viewer secret, when applicable | deployed visualization service | one-time access handoff, never deployment authority |

Cloud credential values are write-only. APIs return IDs, labels, provider
account metadata and validation state, never the stored secret. Secrets must be
absent from logs, SSE events, archives, errors, Terraform evidence and research
artifacts.

## Mutation boundary

Readiness is non-mutating. Supported account preparation is graph-derived,
digest-bound, idempotent and requires explicit confirmation. Billing, quota,
organization policy, tenant consent and provider-side credential revocation
remain manual operator responsibilities.

Deploy and Destroy are durable, idempotent operations. A reconnect resumes
recorded progress rather than issuing another provider command. Each live run
requires separate supervision, a cost boundary and cleanup evidence.

The repository document `docs/plans/2026-08-26_poc_credentials.md` defines the
detailed provider-specific boundary.
