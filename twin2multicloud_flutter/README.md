# Twin2MultiCloud Flutter

Flutter UI for the Twin2MultiCloud Management API. Supported targets are Web,
macOS, Windows, and Linux. Android, iOS, and Fuchsia are unsupported.

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
development bypass. It discovers enabled Google/UIBK providers from the Management
API, completes authentication in an external browser, and consumes the result through
a one-time polling exchange. Production tokens stay in process memory and are cleared
on logout or session expiry. Live UIBK activation still requires the institutional
federation setup documented in the docs site.

## Quality Checks

```bash
./thesis.sh test frontend
```

The local gate builds Web and the current host desktop. The repository Flutter
workflow additionally builds macOS, Windows, and Linux releases on native CI
runners. See the docs-site Supported Platforms page for prerequisites and the
boundary between build support and signed distribution packages.

Flutter must call the Management API only. Direct calls to Optimizer or
Deployer service ports are architecture defects.
