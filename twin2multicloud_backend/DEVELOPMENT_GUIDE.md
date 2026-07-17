# Management API Development Guide

This guide contains service-local engineering rules. Repository setup, thesis
context, cloud bootstrap, and cross-project architecture belong in
`docs-site/`.

## Service Boundary

The Management API is the application-facing orchestration and persistence
boundary:

```text
Flutter
  -> FastAPI route adapter
  -> application service / DeploymentOrchestrator
  -> repository or typed downstream client
  -> SQLite/PostgreSQL, Optimizer, or Deployer
```

- Flutter calls only the Management API, never Optimizer or Deployer directly.
- Routes own HTTP parsing, authentication, response models, and typed error
  mapping. Business workflows belong in services.
- Repositories own persistence queries. Services must not duplicate ownership
  filters or persistence policy in route modules.
- `OptimizerClient` and `DeployerClient` are the only HTTP boundaries to the
  internal services.
- `PricingCatalogContextService` is the sole resolver for calculation,
  pricing-health, persisted evidence, and deployment-selection catalog
  references. Do not infer readiness from legacy snapshot blobs or timestamps.
- Reusable cloud credentials live only in encrypted, user-owned
  `CloudConnection` records.
- Credential-bearing deployment packages are staged for one Deployer operation
  and represented inside Management by an opaque `PreparedDeploymentProject`.

## Local Workflow

From the repository root:

```bash
docker compose build management-api
docker compose up management-api
docker compose run --rm --no-deps management-api python -m pytest -q tests
```

The repository entrypoint starts the complete development application:

```bash
./thesis.sh app
```

The development Compose profile mounts source and stores SQLite data under
`twin2multicloud_backend/data/`. Production images use the owner-only runtime
paths under `/var/lib/twin2multicloud-management/` and run as UID/GID `10002`.

## Quality Gate

Before committing behavioral changes, run:

```bash
ruff check src tests
python -m bandit -q -r src
python -m compileall -q src
python -m pip check
pytest -q tests
```

Run these commands in the development image or an isolated container with the
current worktree mounted at `/app`. Do not use a long-running container as test
evidence unless its mount points are known to reference the active worktree.

For production-image changes, additionally run:

```bash
docker build --target production \
  -t twin2multicloud-management:production \
  ./twin2multicloud_backend
```

Verify the image starts as the non-root `management` user, contains no tests,
databases, uploads, environment files, or credentials, and can create its
runtime database under `/var/lib/twin2multicloud-management/data/`.

## Engineering Rules

1. Use Pydantic response models for stable Flutter-facing JSON contracts.
2. Validate and bound multipart uploads and downstream binary/JSON responses
   before materializing them in memory.
3. Preserve safe downstream `4xx` statuses; map unavailable services and
   unexpected upstream failures to typed `5xx` service errors.
4. Redact secret-like values before logging, persistence, or API responses.
5. Keep deployment state changes and session creation compensating: failed
   preparation or scheduling must not leave twins in transitional states.
6. Schema changes require an idempotent migration and regression coverage.
7. New dependencies belong in the correct production/development requirement
   file and must remain compatible with `requirements.lock`.
8. Track new actionable work in GitHub Issues; do not add Markdown TODO or
   future-work trackers.
9. Persist exact immutable pricing references in Management; full public
   pricing catalogs remain in the Optimizer and require an explicit,
   size-bounded diagnostic read.

## Upload And Runtime Safety

- Project ZIP and GLB request bodies are read through the bounded upload helper.
- GLB files must pass the GLB 2.0 header, chunk, and JSON metadata contract
  before persistence.
- Deployer ZIP-extraction responses use a strict credential-free schema and a
  bounded response body.
- `.dockerignore` excludes runtime databases, uploads, tests, caches,
  environment files, keys, and credential-shaped files from production images.

Live cloud deployment tests can create billable resources. They are never part
of the default Management API test gate and require explicit user intent.
