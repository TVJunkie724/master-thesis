# Developer Guide

This section explains how to work with the integrated Twin2MultiCloud repository.

The repository contains multiple related projects:

- `twin2multicloud_backend`: Management API and orchestration boundary.
- `twin2multicloud_flutter`: Flutter UI.
- `2-twin2clouds`: cost optimizer.
- `3-cloud-deployer`: cloud infrastructure deployer.
- `twin2multicloud-latex`: thesis source.
- `docs-site`: canonical documentation site.

See [Project Structure](project-structure.md) for the migrated project-structure diagram and directory responsibilities.

For a step-by-step local setup, use [Project Setup](setup.md). The same
practical workflow is also available from the repository root in
`HANDBOOK.md`.

## Local Service Ports

| Service | Port |
|---------|------|
| Optimizer | 5003 |
| Deployer | 5004 |
| Management API | 5005 |
| Docs Site | 5010 |

## Start The Application Stack

```bash
./thesis.sh up --no-flutter
```

Use `./thesis.sh up` when you also want to launch Flutter.

## Start The Docs Site

```bash
./thesis.sh docs up
```

Open `http://localhost:5010`.

## Run Flutter

```bash
cd twin2multicloud_flutter
flutter run -d chrome --dart-define-from-file=config/dev.json
```

The preferred root command is:

```bash
./thesis.sh flutter --device chrome
```

## Safe Verification

Unit and integration tests are safe to run. E2E tests may deploy real cloud resources and should only be run intentionally.

```bash
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v
```

See [Testing](testing.md) for the migrated optimizer testing categories and the safe command split.
