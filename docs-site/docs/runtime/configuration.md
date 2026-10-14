# Configuration reference

## Root entrypoint

| Variable | Default | Purpose |
|---|---|---|
| `THESIS_COMPOSE_PROJECT` | `master-thesis` | isolate local Compose state |
| `THESIS_DOCKER_CONTEXT` | current context | choose Docker/OrbStack context |
| `THESIS_OPTIMIZER_PORT` | `5003` | local Optimizer port |
| `THESIS_DEPLOYER_PORT` | `5004` | local Deployer port |
| `THESIS_MANAGEMENT_API_PORT` | `5005` | local Management port |
| `THESIS_DOCS_PORT` | `5010` | documentation port |
| `THESIS_API_BASE_URL` | derived | Flutter Management origin |
| `THESIS_POC_AUTH_TOKEN` | `dev-token` | local profile bearer |
| `THESIS_FLUTTER_DEVICE` | detected desktop | Flutter target |
| `THESIS_RUNTIME_SECRETS_DIR` | `.secrets/runtime` | ignored signing/encryption keys |

## Management API

The local runtime needs a database URL, signing key, encryption key, explicit
development-auth settings and internal Optimizer/Deployer URLs. Credential
rate limits and redaction remain useful safety controls even though production
identity federation is outside scope.

`SUPERVISED_EVALUATION_ENABLED` defaults to `false`. It enables only the
digest-bound exact-candidate handoff used by the approved nine-scenario thesis
matrix; the normal Flutter and optimizer-run paths never expose provider
overrides.

Cloud credential values belong only in encrypted CloudConnections or a
deliberately enabled ignored local secret overlay. They must never be compiled
into Flutter or committed as configuration.

## Optimizer and Deployer

The Optimizer reads versioned frozen pricing catalogs and does not require a
provider credential. The Deployer stores isolated runtime workspaces under
`DEPLOYER_RUNTIME_STATE_ROOT`; generated operation packages and Terraform state
must never use a tracked template directory.

Local credential-file permission probes are disabled unless a supervised cloud
overlay explicitly enables them.

### Shared Terraform provider authentication (PoC)

The shared Terraform root initializes Azure providers even in an AWS-only plan.
The approved single-user PoC retains this dependency instead of restructuring
Terraform. In a deliberately enabled local Compose overlay, mount an ignored
credential JSON read-only into the Deployer and set `TF_AZURE_PROVIDER_AUTH_FILE`
to its container path. The regular Compose configuration does not enable it.

The JSON uses the existing `azure` object with `azure_subscription_id`,
`azure_tenant_id`, `azure_client_id` and `azure_client_secret`, all nonempty
strings. No other fields are imported by this adapter. Credentials stay in
private Terraform inputs/state, not Flutter, exported Twins or tracked files.
Preserve the mount and environment setting through Destroy, and protect the
Terraform state like credentials.

This adapter is used only when Azure is absent from the selected deployment
graph and no Azure authentication fields are already present. It cannot supply
authority for an actual Azure deployment; that still requires the normal
CloudConnection. A missing or invalid configured file fails closed. The opt-in
does not add Azure resources or change the optimizer's cloud assignments. Check
the complete native plan before Apply. See the explicit
[PoC limitation](known-limitations.md).

## Flutter

Flutter receives compile-time Dart defines from the selected mode file. See
[Runtime modes](../getting-started/runtime-profiles.md). Do not add cloud or
Management secret values to these files.
