# Twin2MultiCloud Handbook

This handbook is the practical entrypoint for developers working with the
integrated thesis repository. It explains how to start the system from a clean
clone, where responsibilities live, and which workflows are safe by default.

For broader architecture and thesis context, see:

- [`integration_vision.md`](integration_vision.md)
- [`docs-site/`](docs-site/)
- [`ASSESSMENT.md`](ASSESSMENT.md)

## 1. Fresh Clone Setup

Prerequisites:

- Docker or OrbStack with Docker Compose support.
- Flutter SDK.
- Git.

From a clean clone:

```bash
git clone <repo-url> master-thesis
cd master-thesis
./thesis.sh up
```

The script creates durable local Management API runtime secrets on first use,
starts the application stack, writes the local Flutter runtime configuration,
performs backend smoke checks, and starts Flutter.

If you only want the backend containers:

```bash
./thesis.sh up --no-flutter
```

If Flutter dependencies still need to be resolved:

```bash
./thesis.sh up --setup
```

For a backend-free product walkthrough from a clean clone:

```bash
./thesis.sh demo --setup
```

Subsequent starts can use `./thesis.sh demo`. No Docker service, cloud account,
credential file, or generated development config is required.

## 2. The Root Entrypoint

Use [`thesis.sh`](thesis.sh) from the repository root for day-to-day local work.

| Command | Purpose |
|---------|---------|
| `./thesis.sh up` | Start backend stack, write Flutter config, smoke-check APIs, run Flutter. |
| `./thesis.sh up --no-flutter` | Start backend stack and write Flutter config only. |
| `./thesis.sh flutter --device macos` | Run Flutter against the generated dev config. |
| `./thesis.sh demo` | Run the offline showcase with deterministic in-memory data. |
| `./thesis.sh demo --scenario degraded` | Run the offline degraded-state scenario. |
| `./thesis.sh config` | Generate `twin2multicloud_flutter/config/dev.json`. |
| `./thesis.sh secrets` | Create or validate durable local Management API runtime secrets without starting containers. |
| `./thesis.sh status` | Show service URLs and matching containers. |
| `./thesis.sh logs management-api` | Follow logs for one service. |
| `./thesis.sh down` | Stop local Compose services for this project. |
| `./thesis.sh test backend` | Run Management API tests, excluding E2E tests. |
| `./thesis.sh test frontend` | Run Flutter architecture, format, analyze, unit/widget/demo, and Web/macOS build gates. |
| `./thesis.sh test frontend-integration` | Run read-only Flutter contracts against the credential-free local stack. |

Useful environment overrides:

```bash
THESIS_MANAGEMENT_API_PORT=5105 ./thesis.sh up --no-flutter
THESIS_FLUTTER_DEVICE=chrome ./thesis.sh flutter
THESIS_COMPOSE_PROJECT=thesis-dev ./thesis.sh up --no-flutter
```

## 3. Runtime Configuration

Flutter is started with:

```bash
--dart-define-from-file=config/dev.json
```

Offline demo mode is started with the tracked, non-secret `config/demo.json`.
The optional `--scenario showcase|empty|degraded` argument overrides its
default fixture selection for that process.

The generated file lives at:

```text
twin2multicloud_flutter/config/dev.json
```

Default generated content:

```json
{
  "APP_MODE": "development",
  "API_BASE_URL": "http://localhost:5005",
  "DEV_AUTH_TOKEN": "dev-token"
}
```

`dev.json` is local runtime material and is ignored by Git. The committed
template is:

```text
twin2multicloud_flutter/config/dev.example.json
```

Runtime profiles are explicit and fail closed:

| Profile | Management API | Initial authentication | Startup behavior |
|---|---|---|---|
| `development` | Explicit HTTP(S) origin | Explicit local development token | Shows one local-development sign-in action |
| `production` | Explicit HTTPS origin | None | Production sign-in remains unavailable until the real OAuth/SAML flow is implemented |
| `demo` | None | Fixture identity only | Uses in-memory adapters and performs no network calls |

There is no default profile, URL, or token in Flutter code. A missing
`APP_MODE` stops bootstrap before the UI starts. The tracked production
template is `twin2multicloud_flutter/config/production.example.json`; it is a
non-secret build example, not a deployable environment configuration.

Validate a production-profile Web build with:

```bash
cd twin2multicloud_flutter
flutter build web --release \
  --dart-define-from-file=config/production.example.json
```

Development tokens are process configuration for local execution only. They
are held in memory after the deliberate local sign-in action, cleared on
logout, and forbidden in production and demo profiles.

### Local Management API secrets

`./thesis.sh setup`, `up`, `test backend`, and `test frontend-integration`
create or validate two ignored files:

```text
.secrets/runtime/JWT_SECRET_KEY
.secrets/runtime/ENCRYPTION_KEY
```

The runtime directory is restricted to `0700`, files to `0600`, and Compose
mounts them read-only into the Management API. Existing values are preserved;
they are never rotated automatically or printed. `ENCRYPTION_KEY` protects
persisted CloudConnections, so deleting or replacing it can make existing
credential records unreadable. If local encrypted records exist and the file
is missing, bootstrap fails until the original key is supplied explicitly via
the `ENCRYPTION_KEY` environment variable. Databases written with a removed
insecure development placeholder must be migrated explicitly or reset as local
development data; the bootstrap never reactivates a known weak key.

This auto-generation is a local development capability only. Production must
receive operator-provisioned keys through its deployment platform and fails at
startup when keys are missing, weak, duplicated, malformed, or known
development placeholders.

### Production credential security boundary

Production deployments additionally require:

```text
REQUIRE_HTTPS=true
TRUSTED_PROXY_CIDRS=<edge proxy networks>
CREDENTIAL_RATE_LIMIT_ENABLED=true
CREDENTIAL_RATE_LIMIT_STORAGE_URI=rediss://<shared-redis-endpoint>/<database>
CORS_ORIGINS=https://<frontend-origin>
```

The edge proxy terminates TLS. Uvicorn's implicit proxy-header handling is
disabled, so the Management API accepts `X-Forwarded-Proto: https` only from a
direct peer in `TRUSTED_PROXY_CIDRS`. Plain HTTP is rejected without redirecting
credential-bearing requests; accepted production responses carry HSTS.

CloudConnection mutation, bootstrap, preflight, and validation endpoints are
limited per authenticated user and operation class. Production must use one
shared Redis-compatible store across all API replicas; `memory://` is local and
test only. A limiter outage fails closed before credential processing.

The append-only `credential_security_events` table records typed, owner-scoped
actions, outcomes, resource IDs, status, request ID, and time. It never stores
request bodies, authorization headers, credential values, arbitrary metadata,
raw IP addresses, or secret-derived values. `GET /credential-security-events/`
exposes only the authenticated user's events. Backups and retention are an
operator policy; the application intentionally provides no event deletion API.

Runtime key rotation is not automatic. Rotating `ENCRYPTION_KEY` requires a
separate transactional re-encryption procedure for every stored
CloudConnection and remains explicit future work.

## 4. Cloud Credentials

The default stack is credential-free. A clean clone can start without real cloud
credentials.

Cloud credentials and bootstrap/admin credentials are separate from the two
local Management API runtime keys above. The runtime keys sign local sessions
and encrypt stored CloudConnections; they never grant cloud-provider access.

Local credential files are only needed for supervised cloud validation, sample
seeding, or intentional deployment tests. They belong under `.secrets/local/`,
which is ignored by Git:

```bash
mkdir -p .secrets/local
cp config.json.example                .secrets/local/config.json
cp config_credentials.json.example    .secrets/local/config_credentials.json
cp google_credentials.json.example    .secrets/local/google-credentials.json
cp google_credentials.json.example    .secrets/local/gcp_credentials.json
```

Then start with the credential overlay:

```bash
./thesis.sh up --with-credentials
```

Do not commit, paste, print, or document real credential values. Use only
example files when documenting credential shape.

The target architecture is Credentials SSOT through the Management API:

```text
User imports or creates Cloud Connection
  -> Management API stores encrypted user-scoped credentials
  -> Twin configuration references CloudConnection IDs
  -> Deployer receives explicit deployment context
```

Root-level credential files are compatibility material only.

## 5. Service Responsibilities

| Project | Responsibility |
|---------|----------------|
| `twin2multicloud_flutter/` | User interface, configuration workflow, review screens, deployment control. |
| `twin2multicloud_backend/` | Management API, persistence, user/twin state, Cloud Connections, orchestration boundary. |
| `2-twin2clouds/` | Cost optimizer, pricing inputs, formulas, optimization strategies. |
| `3-cloud-deployer/` | Deployment execution, provider-specific infrastructure logic, deployment logs. |
| `twin2multicloud-latex/` | Thesis source. |
| `docs-site/` | Canonical documentation site. |

The Flutter UI must call the Management API only:

```text
Flutter UI
  -> Management API
    -> Optimizer
    -> Deployer
```

Direct Flutter calls to Optimizer or Deployer are architectural defects.

## 6. LaTeX Workflow

The thesis build is intentionally separate from application startup.

```bash
./thesis.sh latex once
./thesis.sh latex watch
./thesis.sh latex clean
./thesis.sh latex logs
```

The LaTeX source lives in:

```text
twin2multicloud-latex/
```

## 7. Documentation Workflow

Start the documentation site:

```bash
./thesis.sh docs up
```

Open:

```text
http://localhost:5010
```

Markdown changes under `docs-site/docs/` reload automatically.

Use the docs site for thesis-facing and developer-facing explanations. Use
service-local READMEs for service-specific commands and implementation notes.

## 8. Safe Verification

Safe default checks:

```bash
bash -n thesis.sh
docker compose -f compose.yaml --profile docs --profile latex config --quiet
./thesis.sh test backend
./thesis.sh test frontend
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration
```

`test frontend` does not start Docker or contact cloud providers.
`test frontend-integration` starts or reuses only the default credential-free
local services and calls read-only Management API routes. It does not load the
credential overlay, refresh provider pricing, validate provider permissions,
deploy infrastructure, destroy resources, or run simulator cloud operations.

E2E tests can deploy real cloud resources and may cost money. Do not run E2E
tests unless the work explicitly requires it and the cloud impact is understood.

## 9. Common Troubleshooting

### Flutter cannot find `config/dev.json`

Generate it from the repository root:

```bash
./thesis.sh config
```

Then run Flutter through the script:

```bash
./thesis.sh flutter --device macos
```

### A port is already in use

Override the affected host port:

```bash
THESIS_MANAGEMENT_API_PORT=5105 ./thesis.sh up --no-flutter
```

### Backend containers start but Flutter cannot connect

Check the generated API base URL:

```bash
cat twin2multicloud_flutter/config/dev.json
./thesis.sh status
```

### Credentials are missing

Start without `--with-credentials` unless you intentionally need local cloud
credential files. The default development path does not require them.

## 10. Where To Change What

| Change | Start Here |
|--------|------------|
| UI flow, screens, visual state | `twin2multicloud_flutter/lib/` |
| API contract exposed to Flutter | `twin2multicloud_backend/src/api/` |
| Twin persistence and state | `twin2multicloud_backend/src/models/` and `src/services/` |
| Cost formulas or pricing strategy | `2-twin2clouds/src/` |
| Deployment behavior or manifests | `3-cloud-deployer/src/` |
| Thesis text | `twin2multicloud-latex/` |
| Developer/thesis docs | `docs-site/docs/` |

When a change crosses project boundaries, update the contract at the Management
API boundary first, then adapt the caller and downstream service.

## 11. Working Rules

- Keep credentials out of Git and out of logs.
- Keep generated runtime files out of architectural source folders.
- Prefer the root entrypoint for local startup.
- Keep Flutter behind the Management API boundary.
- Run unit and integration tests before committing.
- Treat live cloud E2E tests as deliberate, supervised work only.
