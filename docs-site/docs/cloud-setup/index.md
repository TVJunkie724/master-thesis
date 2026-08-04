# Cloud Setup

Cloud setup is intentionally split by purpose and privilege. A credential that can
create identities is not the credential that should remain stored for normal pricing or
deployment work.

## Credential Model

```text
guided UI
   -> safe provider guide and permission packs
   -> one execute request with a transient bootstrap credential
   -> deterministic provider adapter (offline PoC only)
   -> encrypted generated deployment CloudConnection

supervised live fallback
   -> authenticated provider CLI
   -> versioned bootstrap script, dry-run before apply
   -> ignored local deployment CloudConnection JSON
   -> secure Management import
```

Both paths are implemented. The in-app guide/session flow exercises the whole
lifecycle with deterministic AWS, Azure, and GCP adapters; it does not create a
provider identity or cloud resource. Production adapters fail closed. The
versioned static script plus secure import therefore remains the current
supervised live-provider path. Neither path persists administrator credentials.
AWS and GCP pricing CloudConnections use a separate secure create/import path;
Azure pricing uses the public Retail Prices API and needs no pricing credential.

## Current Baseline

Historical manual scripts use permission-set version `thesis-demo-v1`.
Generated guided deployment connections use `thesis-demo-v2`, whose permission
artifacts are already frozen for Five-layer v2. Both are reviewable thesis
baselines, not final universal least-privilege guarantees. Supervised live
deployment evidence is still required before finalizing provider policies.

## Safe Sequence

For the offline PoC, open **Settings -> Cloud Accounts & Access** or
**Prepare deployment -> Cloud access**, review the server-owned guide and
authority packs, submit the temporary credential once, and inspect the returned
connection and disposal state. Resume, recheck, cancel, credential re-entry,
and manual-revocation acknowledgement use the same owner-scoped session.

For supervised live-provider setup:

1. choose provider and target account/subscription/project;
2. run the provider script without `--apply` and review planned mutations;
3. authenticate the provider CLI through its normal secure mechanism;
4. apply explicitly and write output only to an ignored private path;
5. import the output as a CloudConnection;
6. validate and inspect account/scope metadata;
7. bind the deployment connection only after validation;
8. rotate/revoke through explicit provider controls when retiring it.

Never commit generated keys, pass administrator secrets as command-line arguments, or
store bootstrap credentials in Flutter configuration.

- [AWS](aws.md)
- [Azure](azure.md)
- [Google Cloud](gcp.md)
- [Provider Links](provider-links.md)
