# Twin2MultiCloud Handbook

Use this command reference from the repository root. For first use, follow
[Fresh Clone](docs-site/docs/getting-started/fresh-clone.md); the
[documentation site](docs-site/docs/index.md) owns the detailed explanations.

## Daily commands

| Command | Result |
|---|---|
| `./thesis.sh demo --setup` | offline Flutter walkthrough; omit `--setup` after dependency setup |
| `./thesis.sh up --setup` | local backend stack and Flutter |
| `./thesis.sh up --no-flutter` | backend stack and generated Flutter configuration |
| `./thesis.sh flutter` | Flutter against the local Management API |
| `./thesis.sh config` | regenerate ignored `config/dev.json` |
| `./thesis.sh secrets` | create or validate local runtime keys |
| `./thesis.sh status` | service URLs and container status |
| `./thesis.sh logs management-api` | service logs; also accepts `2twin2clouds` or `3cloud-deployer` |
| `./thesis.sh down` | stop the local stack |
| `./thesis.sh docs up` | documentation at `http://localhost:5010` |
| `./thesis.sh latex once` | separate thesis build; `watch` and `clean` are also available |

Development sign-in is explicit. Production uses the implemented external
OAuth/SAML flow when configured; live UIBK activation still needs institutional
setup. See [Authentication](docs-site/docs/runtime/authentication.md).

## Verification

```bash
./thesis.sh test backend
./thesis.sh test frontend
./thesis.sh test frontend-integration
./thesis.sh test deployment-contract --focused
```

Use `./thesis.sh test deployment-contract` for the full credential-free
cross-project gate. See [Testing](docs-site/docs/developer-guide/testing.md)
for scope and prerequisites. Provider E2E is a separate supervised operation.

## Configuration and recovery

- [Runtime profiles](docs-site/docs/getting-started/runtime-profiles.md): development, demo and production.
- [Configuration](docs-site/docs/runtime/configuration.md): environment settings and port overrides.
- [Cloud setup](docs-site/docs/cloud-setup/index.md): optional provider access.
- [State and backups](docs-site/docs/runtime/state-and-persistence.md): database, encryption key and Terraform state.
- [Troubleshooting](docs-site/docs/runtime/troubleshooting.md): startup, pricing and deployment failures.

The default stack uses no cloud credential files. Normal application credentials
are encrypted Cloud Connections. `.secrets/local/` and
`./thesis.sh up --with-credentials` are optional compatibility/seeding paths.
Keep the original encryption key when restoring a database.

## Where to change what

| Change | Source |
|---|---|
| UI and workflows | `twin2multicloud_flutter/lib/` |
| Management contracts and orchestration | `twin2multicloud_backend/src/` |
| Pricing and calculation | `2-twin2clouds/backend/`, `2-twin2clouds/pricing_registry/` |
| Infrastructure execution | `3-cloud-deployer/src/` |
| Current technical/user documentation | `docs-site/docs/` |
| Research reasoning | `docs/research/` |

For responsibilities and the data path, see
[System Context](docs-site/docs/architecture/system-context.md).
