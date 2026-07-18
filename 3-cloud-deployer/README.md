# Multi-Cloud Digital Twin Deployer

The Deployer is the infrastructure execution service of Twin2MultiCloud. It
validates a materialized deployment project, builds provider packages and
Terraform variables, executes Terraform, and exposes deployment status,
verification, logs, and user-function operations through an internal FastAPI
API.

The Management API is the application-facing boundary. Flutter must not call
the Deployer directly.

## Canonical Flow

```text
Flutter
  -> Management API
       -> resolves user-owned CloudConnections
       -> validates the Twin configuration
       -> creates an immutable DeploymentManifest
       -> stages one private, short-lived operation package
       -> Deployer API
            -> consumes the package through an opaque one-shot token
            -> restores protected Terraform/runtime state
            -> validates Manifest v2 + frozen deployment specification
            -> builds provider function packages
            -> generates allowlisted typed Terraform variables
            -> runs Terraform through TerraformRunner
            -> persists allowlisted runtime outputs outside project storage
            -> destroys the credential-bearing operation package
            -> emits structured operation events
       -> persists deployment state and safe evidence
```

## Ownership Boundaries

| Concern | Source of truth |
|---|---|
| User and Twin configuration | Management API database |
| Reusable cloud credentials | Encrypted Management API CloudConnections |
| Deployment intent | Versioned `DeploymentManifest` |
| Deployable service settings | Frozen `ResolvedDeploymentSpecification v1` |
| Read-only project template | `templates/digital-twin/` |
| Durable secret-free project definition | `upload/<project>/` |
| Credential-bearing operation package | Private temporary package store |
| Infrastructure/runtime state | `/var/lib/twin2multicloud-deployer/runtime-state/` |
| Product and thesis documentation | `docs-site/` |
| Planned work | GitHub Issues and repository roadmap |

Credentials are never committed, baked into the image, or retained in durable
project storage. The Management API stages each generated package through
`POST /projects/{project_name}/operation-package`; the returned opaque token is
required as `X-Operation-Package` for deployment, destruction, verification,
logs, and simulator operations. Tokens are project-bound, expire, and are
consumed once. Request-body permission checks remain the canonical provider
validation path.

Deployment and destruction require `DeploymentManifest 2.0`. The Deployer
recomputes the canonical specification digest, verifies the selected provider
path and every registered component/dimension, and rejects legacy, incomplete,
stale, or contradictory packages before runtime side effects. Only dimensions
classified as `deployable_selection` may become Terraform variables; usage
tiers, account-level state, and formula assumptions remain evidence only.

## Runtime Architecture

The API routes delegate infrastructure changes to the canonical Terraform
facade:

```text
FastAPI route
  -> request validation and OperationContext
  -> DeploymentContext factory
  -> TerraformDeployerStrategy
       -> provider package builder
       -> tfvars generator
       -> TerraformRunner
  -> structured response / SSE events
```

AWS, Azure, and GCP implementations live under `src/providers/`. Provider
runtime functions share provider-local communication helpers so deployed
packages do not depend on the Deployer process.

## Start

From the repository root:

```bash
./thesis.sh app
```

The local Deployer API is available at
`http://localhost:${THESIS_DEPLOYER_PORT:-5004}`. OpenAPI is exposed at
`/docs` and `/openapi.json`. The complete project documentation is served by
the separate docs profile:

```bash
./thesis.sh docs
```

For service-only development:

```bash
docker compose up --build 3cloud-deployer
```

Compose builds the `development` stage. The Dockerfile's `production` stage is
non-root and excludes pytest, Ruff, Bandit, Moto, and HTTP test clients.

## Quality Gates

The default suite excludes live cloud tests and is safe to run without cloud
credentials:

```bash
docker compose run --rm --no-deps 3cloud-deployer ./run_tests.sh
```

This runs unit/integration tests, Ruff, Bandit, bytecode compilation, and
`pip check`. Live E2E tests require explicit opt-in and provider credentials:

```bash
docker compose run --rm --no-deps -e RUN_E2E_TESTS=1 3cloud-deployer \
  pytest -m live tests/e2e
```

Live tests can create billable cloud resources. They are not part of the
default quality gate.

## Project Layout

```text
3-cloud-deployer/
|- rest_api.py                 FastAPI composition root
|- src/api/                    HTTP adapters and transport contracts
|- src/core/                   contexts, storage, errors, observability
|- src/providers/              AWS, Azure, GCP and Terraform implementations
|- src/validation/             project and configuration validation
|- templates/digital-twin/     versioned read-only project template
|- upload/                     ignored secret-free project definitions
|- src/operation_packages.py  private one-shot credential package lifecycle
|- src/runtime_state.py       protected durable Terraform/runtime state
|- tests/                      unit, integration and explicit E2E suites
|- requirements.txt            production dependencies
|- requirements-dev.txt        test and quality dependencies
`- requirements.lock           reproducible dependency constraints
```

## Security Properties

- Terraform commands use a fixed executable and an allowlisted argument
  contract; shell execution is not used.
- Simulator entrypoints are resolved beneath an allowlisted source root.
- Inter-cloud runtime calls accept only absolute HTTPS URLs without embedded
  user credentials.
- Runtime diagnostics are bounded and redact credential-like values.
- The canonical template is read-only and cannot resolve to runtime credential
  files.
- Credential-bearing packages use owner-only files and are destroyed after one
  operation, including failed or interrupted streams.
- Terraform state and generated device credentials live in an owner-only named
  volume outside user-visible project storage.
- Generated variables, runtime uploads, and credential files are excluded from
  image and Git contexts.
- Terraform downloads are verified against architecture-specific SHA-256
  checksums.

## API Contract

The generated OpenAPI document is the authoritative endpoint inventory. The
principal route groups are:

- `/projects`: project import, inspection, files, versions, and cleanup
- `/validation`: project and configuration validation
- `/permissions`: provider permission checks and normalized preflight
- `/infrastructure`: deploy, destroy, status, verification, and SSE operations
- `/functions`: user-function discovery and updates
- `/logs`: provider logs and operation diagnostics
- `/simulator`: simulator package and execution operations

Application integrations should use the Management API contract instead of
binding to these internal routes.

## Further Documentation

Architecture, setup, cloud bootstrap, provider permissions, deployment
internals, migration decisions, reference papers, and roadmaps are maintained
under `docs-site/`. Historical implementation plans and provider policy
references remain in this service as audit evidence where repository scripts
or bootstrap tooling still consume them.
