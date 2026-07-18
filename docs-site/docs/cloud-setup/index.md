# Cloud Setup

Cloud setup is intentionally split by purpose and privilege. A credential that can
create identities is not the credential that should remain stored for normal pricing or
deployment work.

## Credential Model

```text
operator/admin session (transient, outside persisted CloudConnection)
   -> versioned bootstrap script, dry-run by default
   -> constrained deployment credential output
   -> import into Management API deployment CloudConnection
   -> validate permission-set version
   -> bind to a twin
```

The current implemented bootstrap is **manual static script + secure import**. The API
returns a plan and command arguments but does not persist administrator credentials.
AWS and GCP pricing CloudConnections use a separate secure create/import path. Azure
pricing uses the public Retail Prices API and needs no pricing credential.

## Current Baseline

All providers use permission-set version `thesis-demo-v1`. It is a reviewable thesis
baseline, not a final universal least-privilege guarantee. Scope-review artifacts and
preflight tests document known permissions; supervised live deployment evidence is
still required before finalizing provider policies.

## Safe Sequence

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
