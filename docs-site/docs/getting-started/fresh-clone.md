# Fresh Clone

## Prerequisites

- Git;
- Docker Compose through OrbStack, Docker Desktop, or a compatible runtime;
- a Flutter SDK compatible with `twin2multicloud_flutter/pubspec.yaml`;
- macOS desktop tooling for the default device, or another configured Flutter device.

Cloud credentials are optional and must not be prepared for the first start.

## 1. Clone And Inspect

```bash
git clone <repository-url> master-thesis
cd master-thesis
./thesis.sh help
```

Run commands from the repository root.

## 2. Choose A Start Mode

### Offline demo

```bash
./thesis.sh demo --setup
```

After setup, use `./thesis.sh demo`. Deterministic alternatives are:

```bash
./thesis.sh demo --scenario showcase
./thesis.sh demo --scenario empty
./thesis.sh demo --scenario degraded
```

### Integrated development

```bash
./thesis.sh up --setup
```

The command:

1. creates or validates ignored Management API runtime secrets;
2. starts Optimizer, Deployer, and Management API;
3. waits for safe HTTP smoke checks;
4. writes `twin2multicloud_flutter/config/dev.json`;
5. starts Flutter with `--dart-define-from-file=config/dev.json`.

Backend only:

```bash
./thesis.sh up --no-flutter
```

Flutter only, after the backend is running:

```bash
./thesis.sh flutter --device macos
```

## 3. Verify The Runtime

```bash
./thesis.sh status
```

| Service | Default URL |
|---|---|
| Optimizer OpenAPI | `http://localhost:5003/docs` |
| Deployer OpenAPI | `http://localhost:5004/docs` |
| Management API OpenAPI | `http://localhost:5005/docs` |
| Documentation | `http://localhost:5010` after `./thesis.sh docs up` |

## 4. Optional Cloud Credential Overlay

Only enable this overlay for an intentional, supervised provider operation:

```bash
mkdir -p .secrets/local
cp config.json.example .secrets/local/config.json
cp config_credentials.json.example .secrets/local/config_credentials.json
cp google_credentials.json.example .secrets/local/google-credentials.json
cp google_credentials.json.example .secrets/local/gcp_credentials.json
./thesis.sh up --with-credentials
```

Fill only ignored files under `.secrets/local/`. Normal application credentials are
encrypted user-scoped CloudConnections; local files exist for compatibility checks
and opt-in sample seeding.

## 5. Stop The Stack

```bash
./thesis.sh down
```

The Management API database and Deployer runtime volume survive normal restarts.
Read [State and Persistence](../runtime/state-and-persistence.md) before deleting them.
