# Twin2MultiCloud

A research proof of concept that connects Digital Twin cost optimization with
multi-cloud deployment. Users describe a workload, inspect a costed provider
assignment, and prepare its deployment through one Flutter application.

## Try the PoC

Requires Git, Flutter 3.44.0 / Dart 3.12 and the
[platform toolchain](docs-site/docs/getting-started/supported-platforms.md).
The integrated stack also requires Docker Compose and Python ≥ 3.9.
Run commands from the repository root; use Git Bash on Windows.

```bash
# Offline walkthrough: no backend or cloud credentials
./thesis.sh demo --setup

# Integrated local application
./thesis.sh up --setup
```

The demo opens a populated dashboard and resets on restart. The integrated
application starts three backend services and Flutter; select **Continue in
local development** to sign in. Cloud credentials are not needed for startup.

See [Fresh Clone](docs-site/docs/getting-started/fresh-clone.md) for setup and
[PoC Walkthrough](docs-site/docs/user-guide/multi-cloud-walkthrough.md) for
what to inspect.

## Projects

| Project | Responsibility | Local port |
|---|---|---|
| [Flutter](twin2multicloud_flutter/) | configuration and result review | host app |
| [Management API](twin2multicloud_backend/) | users, twins, credentials, persisted runs and orchestration | 5005 |
| [Optimizer](2-twin2clouds/) | pricing evidence and complete-path cost comparison | 5003 |
| [Deployer](3-cloud-deployer/) | packages, Terraform and provider operations | 5004 |
| [Documentation](docs-site/) | current PoC guide and technical reference | 5010 |

Flutter calls only the Management API.

## Current boundary

The PoC implements cost calculation, immutable calculation evidence and
manifest-backed deployment orchestration. The architecture-profile resolver
defaults to **off**; new deployment packages require Manifest v3 and a resolved
architecture. The graph compiler exists, but neither local startup nor a demo
proves a working cloud deployment.

GCP L4/L5 are unsupported. Grafana's current L3-reader binding differs from the
modeled L4→L5 path. Final live-cloud verification and cost-model reconciliation
remain open. See [Results and Limits](docs-site/docs/runtime/known-limitations.md).

## Documentation and daily work

```bash
./thesis.sh docs up       # http://localhost:5010
./thesis.sh status
./thesis.sh down
```

- [Handbook](HANDBOOK.md): daily commands and where to find details.
- [Documentation home](docs-site/docs/index.md): setup, use and architecture.
- [Research notes](docs/research/README.md): scientific reasoning and evaluation design.
- [Testing](docs-site/docs/developer-guide/testing.md): safe verification commands.
- [Contributor workflow](ONBOARDING.md): repository rules and backlog ownership.

Live deploy/destroy and provider E2E operations can create costs; they are
separate from the offline demo and default local startup.
