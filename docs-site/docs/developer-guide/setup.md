# Project Setup

This page describes the current local setup for the integrated thesis repository. It is intentionally practical: the credential and runtime model is being redesigned, but developers still need one clear path to start the system today.

## Prerequisites

- Docker Desktop or OrbStack with Docker Compose support.
- Flutter SDK for the web UI.
- Git.
- Cloud CLIs are optional and only needed for intentional real cloud work.

Do not commit real credential files. Real cloud credentials are transitional local material until Cloud Connections become the source of truth. Local cloud credential files belong under `.secrets/local/`, which is ignored by Git.

## Start The Backend Stack

From the repository root:

```bash
docker compose up -d
```

This starts:

| Service | URL |
|---------|-----|
| Optimizer | `http://localhost:5003` |
| Deployer | `http://localhost:5004` |
| Management API | `http://localhost:5005` |

The Management API is the UI-facing backend. Flutter should call the Management API, not the Optimizer or Deployer directly.

## Start The Documentation Site

```bash
docker compose --profile docs up -d docs
```

Open `http://localhost:5010`. Markdown edits under `docs-site/docs/` reload automatically.

## Run The Flutter App

```bash
cd twin2multicloud_flutter
flutter pub get
flutter run -d chrome --dart-define-from-file=config/dev.json
```

The current development flow uses local backend services. The Flutter app should be started with an environment config file when you need to point it at non-default backend URLs.

## Compile The Thesis

```bash
docker compose --profile latex run --rm thesis-latex
```

The LaTeX source lives in `twin2multicloud-latex/` and remains part of the repository.

## Credentials In The Current Stack

The default Compose stack is intentionally credential-free. Root-level credential files are not mounted by default, and sample data seeding starts disabled.

Use the local cloud override only when you intentionally need `.secrets/local/` credential files for sample seeding or supervised local cloud tests:

```bash
docker compose -f compose.yaml -f compose.cloud.local.yaml up -d
```

Prepare the local files from placeholders:

```bash
mkdir -p .secrets/local
cp config.json.example                .secrets/local/config.json
cp config_credentials.json.example    .secrets/local/config_credentials.json
cp google_credentials.json.example    .secrets/local/google-credentials.json
cp google_credentials.json.example    .secrets/local/gcp_credentials.json
```

If older valid credential files still exist at the repository root, move or copy them manually after verifying your local setup. The project does not migrate or delete live credentials automatically.

When sample seeding is enabled, the Management API stores provider credentials once as encrypted Cloud Connections for the seed user and binds the sample twins to those records. Legacy per-twin credential seeding is disabled; setting `SEED_LEGACY_TWIN_CREDENTIALS=true` now fails fast so duplicated per-twin secrets cannot be reintroduced.

The local-cloud override also sets `ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS=true` for Optimizer and Deployer. That gate enables their debug/local-cloud `GET /permissions/verify/*` endpoints that read mounted files. Normal app flows use request-body or CloudConnection-derived credentials instead.

The target flow is:

1. User creates or imports a Cloud Connection.
2. Bootstrap/admin credentials are used only when needed to create a constrained deployment identity.
3. Bootstrap/admin credentials are discarded.
4. Deployments reference the stored user-scoped Cloud Connection.
5. The Deployer receives explicit deployment context and does not discover credentials from arbitrary workspace files.

Treat any real cloud deployment as intentional and manually supervised.

## Safe Verification

Unit and non-E2E integration tests are safe to run:

```bash
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v
```

E2E tests can create real cloud resources and should only run after an explicit decision to test cloud deployment.

## Stop Local Services

```bash
docker compose --profile docs down
```

Use volume deletion only when you intentionally want to reset local persisted state.
