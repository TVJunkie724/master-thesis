# Twin2MultiCloud Flutter

Flutter Web/Desktop UI for the Twin2MultiCloud Management API.

## Offline Demo

Start the application with deterministic in-memory data and no Docker,
backend, cloud credentials, or network services:

```bash
./thesis.sh demo
```

Use `--scenario showcase`, `--scenario empty`, or `--scenario degraded` to
inspect representative application states. Demo mutations remain in memory
for the current process and are reset on restart.

## Local Runtime

Start the application from the repository root:

```bash
./thesis.sh up
```

Backend only:

```bash
./thesis.sh up --no-flutter
```

Run Flutter only against the host-exposed Management API:

```bash
./thesis.sh flutter --device chrome
```

`config/dev.example.json` documents the supported runtime keys. Use
`./thesis.sh config` to generate `config/dev.json`; it is gitignored.
`config/demo.json` is tracked and contains no service URL, token, or secret.
`config/production.example.json` documents the token-free HTTPS production
shape. Flutter has no implicit runtime profile: missing or invalid
`APP_MODE`, URL, or profile-specific authentication values stop bootstrap.

Development authentication is available only after selecting the explicit
local-development action on the Login screen. Production intentionally has no
development bypass and remains fail-closed until its OAuth/SAML flow is
implemented.

## Quality Checks

```bash
flutter pub get
flutter analyze
flutter test
flutter build web --dart-define-from-file=config/dev.json
flutter build web --release \
  --dart-define-from-file=config/production.example.json
```

Flutter must call the Management API only. Direct calls to Optimizer or
Deployer service ports are architecture defects.
