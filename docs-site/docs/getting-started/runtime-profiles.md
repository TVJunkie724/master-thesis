# Runtime Profiles

Flutter fails closed when `APP_MODE` is absent or invalid. Runtime composition is
selected before the widget tree is built.

| Profile | API adapter | Authentication | Intended use |
|---|---|---|---|
| `development` | Network `ManagementApi` | Explicit local sign-in with configured token | Integrated development only. |
| `production` | Network `ManagementApi` at explicit HTTPS origin | OAuth/SAML boundary | Deployed application; identity setup is externally gated. |
| `demo` | `DemoManagementApi` and demo log stream | Fixture identity | Offline walkthrough and deterministic UI tests. |

## Development

`./thesis.sh config` writes ignored `config/dev.json` from runtime values. Its shape is:

```json
{
  "APP_MODE": "development",
  "API_BASE_URL": "http://localhost:5005",
  "DEV_AUTH_TOKEN": "dev-token"
}
```

`config/dev.example.json` is the tracked reference. The token is held in memory only
after explicit local sign-in and is forbidden in production and demo profiles.

## Demo

`config/demo.json` is tracked and contains no API URL or cloud credential. Runtime
composition throws if demo code requests a network API or network log client.

## Production

`config/production.example.json` demonstrates build shape, not deployable secrets.
Production requires an explicit HTTPS Management API origin and no development token.

```bash
cd twin2multicloud_flutter
flutter build web --release \
  --dart-define-from-file=config/production.example.json
```

This verifies configuration compatibility; it does not complete institutional
identity-provider registration or production infrastructure provisioning.
