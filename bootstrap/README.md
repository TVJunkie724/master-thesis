# Provider Bootstrap

This directory contains versioned bootstrap artifacts for creating constrained
deployment identities that can be imported as Management API CloudConnections.

The scripts are intentionally manual-first:

- default mode is dry-run,
- `--apply` is required before any cloud mutation,
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
