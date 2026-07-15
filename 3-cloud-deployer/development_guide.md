# Deployer Development Guide

This file contains service-local engineering rules. Repository setup,
architecture, cloud bootstrap, and thesis context belong in `docs-site/`.

## Development Boundary

- Run the service through the repository `compose.yaml`.
- Use the Management API for application workflows.
- Keep `templates/digital-twin/` read-only.
- Keep `upload/<project>/` limited to durable, secret-free project definitions.
- Materialize credentials only through `OperationPackageStore`; operation
  routes must require and consume an `X-Operation-Package` token.
- Persist only allowlisted Terraform/runtime outputs through
  `RuntimeStateStore` under the protected Deployer data volume.
- Never add credentials, generated Terraform variables, plans, or state to Git
  or Docker build contexts.
- Keep provider runtime helpers self-contained because they are packaged into
  Lambda, Azure Functions, or Cloud Functions.

## Commands

From the repository root:

```bash
docker compose build 3cloud-deployer
docker compose up 3cloud-deployer
docker compose run --rm --no-deps 3cloud-deployer ./run_tests.sh
```

Focused tests can be passed directly to pytest:

```bash
docker compose run --rm --no-deps 3cloud-deployer \
  pytest -q tests/unit/terraform/test_function_bundler.py
```

The default pytest configuration excludes `tests/e2e`. Live tests require both
`RUN_E2E_TESTS=1` and an explicit E2E path or marker. They may create billable
resources and must never run as an incidental collection side effect.

## Change Rules

1. Route modules own HTTP parsing and response mapping only.
2. Domain and orchestration behavior belongs in `src/core/`, validation
   services, or provider strategies.
3. Provider-specific behavior must stay behind provider registries or strategy
   contracts; do not add provider switch logic to route modules.
4. All filesystem access must go through project storage/path boundaries.
5. External commands use fixed executables, validated argument lists, explicit
   timeouts where applicable, and no shell.
6. Logs and API errors must use structured operation context and redact secrets.
7. New dependencies must be declared in the correct runtime/development file;
   regenerate `requirements.lock` and verify both Docker targets.
8. New work is tracked in GitHub Issues. Do not add service-local TODO trackers.

## Verification

Every behavioral change should include focused regression tests. Before commit,
run the complete safe gate:

```bash
docker compose run --rm --no-deps 3cloud-deployer ./run_tests.sh
docker build --target production -t 3cloud-deployer:production ./3-cloud-deployer
docker run --rm 3cloud-deployer:production python -m pip check
```

For API contract changes, regenerate the repository OpenAPI snapshot and run
the cross-service contract checks from the repository root.
