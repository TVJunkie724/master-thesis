# Project Setup

This page describes the current local setup for the integrated thesis repository. It is intentionally practical: the credential and runtime model is being redesigned, but developers still need one clear path to start the system today.

## Prerequisites

- Docker Desktop or OrbStack with Docker Compose support.
- Flutter SDK for the web UI.
- Git.
- Cloud CLIs are optional and only needed for intentional real cloud work.

Do not commit real credential files. Real cloud credentials are transitional local material until Cloud Connections become the source of truth.

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
flutter run -d chrome
```

The current development flow uses local backend services. Authentication and seed credentials are still in transition and will be cleaned up through the credentials source-of-truth phase.

## Compile The Thesis

```bash
docker compose --profile latex run --rm thesis-latex
```

The LaTeX source lives in `twin2multicloud-latex/` and remains part of the repository.

## Credentials In The Current Stack

The current Compose stack may mount local credential files if they exist, for example root-level cloud credential JSON files. This is a known transitional state, not the target architecture.

The target flow is:

1. User creates or imports a Cloud Connection.
2. Bootstrap/admin credentials are used only when needed to create a constrained deployment identity.
3. Bootstrap/admin credentials are discarded.
4. Deployments reference the stored user-scoped Cloud Connection.
5. The Deployer receives explicit deployment context and does not discover credentials from arbitrary workspace files.

Until that is implemented, treat any real cloud deployment as intentional and manually supervised.

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
