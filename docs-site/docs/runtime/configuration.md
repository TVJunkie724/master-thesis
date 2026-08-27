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
| `THESIS_DEV_AUTH_TOKEN` | `dev-token` | local single-user bearer |
| `THESIS_FLUTTER_DEVICE` | detected desktop | Flutter target |
| `THESIS_RUNTIME_SECRETS_DIR` | `.secrets/runtime` | ignored signing/encryption keys |

## Management API

The local runtime needs a database URL, signing key, encryption key, explicit
development-auth settings and internal Optimizer/Deployer URLs. Credential
rate limits and redaction remain useful safety controls even though production
identity federation is outside scope.

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

## Flutter

Flutter receives compile-time Dart defines from the selected mode file. See
[Runtime modes](../getting-started/runtime-profiles.md). Do not add cloud or
Management secret values to these files.
