# Provider Bootstrap

This directory contains versioned bootstrap artifacts for creating constrained
deployment identities that can be imported as Management API CloudConnections.

The scripts are intentionally manual-first:

- default mode is dry-run,
- `--apply` is required before any cloud mutation,
- credential/key rotation is explicit and provider-specific,
- existing local output files are not overwritten unless `--overwrite-output`
  is provided,
- bootstrap/admin credentials are never accepted as script arguments,
- generated deployment credentials are written only to the requested local
  output file or stdout,
- no output file in this directory should be committed.

Current CloudConnection support stores:

| Provider | Auth type | Bootstrap output |
|----------|-----------|------------------|
| AWS | `access_key` | constrained IAM user access key |
| Azure | `service_principal` | service principal client secret |
| GCP | `service_account_key` | service account key JSON embedded as a string |

## Rotation Guardrails

The scripts refuse to silently create additional long-lived deployment secrets
for an existing identity:

- AWS requires `--rotate-access-keys` before deleting existing access keys and
  creating a replacement key.
- Azure requires `--rotate-client-secret` before adding a new client secret to
  an existing app registration.
- GCP requires `--rotate-service-account-keys` before deleting existing
  user-managed service-account keys and creating a replacement key.

This is deliberately conservative. It prevents accidental key sprawl during
local testing and makes destructive rotation an explicit operator decision.

These artifacts are the static foundation for #7. A later Management API flow
can call equivalent provider-specific logic request-scoped and persist only the
generated CloudConnection, never the bootstrap/admin material.

## Verification

```bash
bash -n bootstrap/aws/bootstrap_deployment_identity.sh
bash -n bootstrap/azure/bootstrap_deployment_identity.sh
bash -n bootstrap/gcp/bootstrap_deployment_identity.sh
python3 -m json.tool 3-cloud-deployer/docs/references/aws_deployer_policy.json >/dev/null
python3 -m json.tool 3-cloud-deployer/docs/references/azure_deployer_policy.json >/dev/null
```
