# Credentials And Trust

Twin2MultiCloud uses preconfigured provider administrator credentials for the
supervised proof of concept. It does not create cloud identities, calculate
least-privilege permission packs, or manage credential rotation. The complete
scope decision is recorded in the repository document
`docs/plans/2026-08-26_poc_credentials.md`.

## Runtime flow

1. The operator creates a credential in an isolated thesis cloud environment.
2. The credential is submitted as a write-only CloudConnection payload.
3. Management encrypts it at rest and returns only non-secret metadata.
4. Pricing or deployment resolves the owner- and purpose-bound connection and
   forwards the secret only for the current downstream request.
5. Optimizer or Deployer performs the real provider validation required by the
   selected operation. Readiness fails when the credential is absent or the
   validation is missing, stale, or unsuccessful.

AWS and GCP pricing refreshes require an explicitly confirmed pricing
connection. Azure catalog pricing uses the public pricing API. For the PoC, an
operator may register the same preconfigured credential for pricing and
deployment purposes.

## Secret exit rules

| Boundary | Allowed | Forbidden |
|---|---|---|
| CloudConnection API | provider, purpose, label, account/project identity, validation state | secret values in responses |
| encrypted store | encrypted credential payload and owner-safe metadata | plaintext credential material |
| downstream request | request-scoped credential payload | durable retry, trace, metric, or log copies |
| Optimizer and Deployer | typed validation result and redacted diagnostic | echoed credential fragments |
| Flutter | labels, purpose, provider identity, readiness | submitted credential material in state or diagnostics |

Application signing/encryption secrets and cloud credentials remain separate
security domains. Neither substitutes for the other. `root`, tenant-wide
break-glass credentials, automated identity provisioning, rotation, and
production credential lifecycle management are outside this thesis PoC.

See [Security And Trust Boundaries](../architecture/security-boundaries.md) and
[Cloud Accounts](../user-guide/cloud-accounts.md) for the operational boundary.
