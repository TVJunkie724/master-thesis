# Twin2MultiCloud Flutter

Flutter Web/Desktop UI for the Twin2MultiCloud Management API.

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

## Quality Checks

```bash
flutter pub get
flutter analyze
flutter test
flutter build web --dart-define-from-file=config/dev.json
```

Flutter must call the Management API only. Direct calls to Optimizer or
Deployer service ports are architecture defects.
