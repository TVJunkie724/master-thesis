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

Six-layer Demo runs preserve the native RTA v2/RDS v2/run/digest boundary
and deterministic illustrative component costs. Their contract-fixture edge
costs remain zero and are not thesis evaluation evidence; exact provider and
cross-cloud costs come only from the local Management-to-Optimizer workflow.

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

## PoC Deployment Access

Settings and Prepare deployment manage preconfigured CloudConnections. The
operator supplies one administrator credential per provider through the
write-only form; Flutter retains only non-secret metadata and validation state.
Identity creation, permission packs, and credential rotation are outside the
PoC.

## Post-Deployment Layer Access

For deployed `six-layer-eventing@1` evidence, Twin
Overview renders one typed L4 semantic Twin card and one typed L5 raw/rollup
Grafana card. Links,
provider-owned authentication, capabilities, limitations, and readiness come
from the owner-scoped Management API; Flutter never derives them from generic
Terraform outputs. AWS uses Identity Center, Azure uses Entra ID, and GCP L4
uses IAP. GCP Grafana alone supports an explicit Viewer-password rotation and
one-time reveal; Flutter does not persist the value.

All nine L4/L5 provider pairs pass against an isolated local Management API for
the active Phase 8 profile. That gate creates no cloud resources. Six-layer v1
is active for offline selection and evaluation; its explicit live-capacity
gates still block deployment selection. Actual
provider-console browser sign-in remains a supervised live check.

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

## Architecture Profile Workflow

The Configuration Workspace now owns a typed, server-driven profile boundary:
save the Twin identity, select an active profile, inspect its logical flow,
then enter workload and user logic before optimization. Profile changes use a
revisioned Management preview and display only the invalidations returned by
the server. Selected runs are reviewed through immutable resolved component,
edge, tiering, bridge, cost, and digest DTOs.

The real and demo catalogs expose active `six-layer-eventing@1`; new Twins pin
the selected exact digest. The connected local stack calculates strict offline
RTA/RDS evidence for the active profile, and a result cannot
be selected for deployment while a listed live-capacity gate remains. Demo
mode exposes the profile definition and its canonical offline fixture.

The UI presents only Management-owned resolved results and does not derive a
cross-profile winner from research evidence.
