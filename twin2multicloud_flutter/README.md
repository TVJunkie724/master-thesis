# Twin2MultiCloud Flutter

Flutter Web/Desktop UI for the Twin2MultiCloud Management API.

## Local Runtime

Start the backend stack from the repository root:

```bash
docker compose up -d management-api 2twin2clouds 3cloud-deployer
```

Run Flutter against the host-exposed Management API:

```bash
cd twin2multicloud_flutter
flutter run -d chrome --dart-define-from-file=config/dev.json
```

`config/dev.example.json` documents the supported runtime keys. Use
`config/dev.local.json` for personal overrides; it is gitignored.

## Quality Checks

```bash
flutter pub get
flutter analyze
flutter test
flutter build web --dart-define-from-file=config/dev.json
```

Flutter must call the Management API only. Direct calls to Optimizer or
Deployer service ports are architecture defects.
