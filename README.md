# Twin2MultiCloud

A unified platform that bridges theoretical cost optimization and practical multi-cloud infrastructure deployment for Digital Twins.

For the project vision, 5-layer architecture and component roles (Orchestrator → Brain → Muscle), see [integration_vision.md](integration_vision.md).
For agent/contributor workflow rules, see [ONBOARDING.md](ONBOARDING.md).

---

## Project Structure

| Directory | Role | Port |
|-----------|------|------|
| [`twin2multicloud_flutter/`](twin2multicloud_flutter/) | Flutter UI (macOS / web / …) | — |
| [`twin2multicloud_backend/`](twin2multicloud_backend/) | Management API (FastAPI, SQLite) | 5005 |
| [`2-twin2clouds/`](2-twin2clouds/) | Cost Optimizer — "Brain" | 5003 |
| [`3-cloud-deployer/`](3-cloud-deployer/) | Cloud Deployer — "Muscle" | 5004 |
| [`twin2multicloud-latex/`](twin2multicloud-latex/) | Thesis document | — |

---

## Prerequisites

- **Docker** (OrbStack, Docker Desktop, or similar) — used to run all three backend services
- **Flutter SDK** ≥ 3.41 (with Dart ≥ 3.11) — for the UI
- **Git**
- Cloud credentials (AWS / GCP / Azure) — only required if you actually want to run deployments; the UI and DB seeding work without them

---

## Quick Start (Fresh Clone)

### 1. Clone the repository

```bash
git clone <repo-url> master-thesis
cd master-thesis
```

### 2. Create credential files from templates

The repository ignores all real credential files. Copy the examples and fill them in:

```bash
cp config.json.example                config.json
cp config_credentials.json.example    config_credentials.json
cp google_credentials.json.example    google-credentials.json
cp google_credentials.json.example    gcp_credentials.json
```

> ⚠️ **Why two GCP files?** [`compose.yaml`](compose.yaml) currently mounts `./google-credentials.json` for `2twin2clouds` but `./gcp_credentials.json` for `3cloud-deployer`. The simplest workaround is to keep both files in sync (or symlink them). If you only work with AWS/Azure you can leave the GCP files as placeholders — the containers will still start.

Then edit `config_credentials.json` and the two GCP files with your real cloud credentials (keys, project IDs, etc.). Leave any provider you don't use as-is.

### 3. Start the backend services

From the workspace root:

```bash
docker compose up -d
```

This builds and starts four containers:

| Container | Purpose |
|-----------|---------|
| `master-thesis-2twin2clouds-1` | Cost Optimizer |
| `master-thesis-3cloud-deployer-1` | Cloud Deployer |
| `master-thesis-management-api-1` | Management API (FastAPI + SQLite) |

Verify they are up:

```bash
docker ps
```

### 4. Database initialization & seeding (automatic)

The Management API handles everything on startup — no manual commands needed.

#### 4a. Schema creation

`src/main.py` calls `Base.metadata.create_all(bind=engine)` on startup, which creates all SQLAlchemy tables in `twin2multicloud_backend/data/app.db` if they don't exist yet. The `data/` directory is persisted on the host via a bind mount, so the DB survives container rebuilds.

#### 4b. Dev user (always-on)

When `DEBUG=true` (set by default in `compose.yaml`) the backend uses a development auth bypass in [`src/api/dependencies.py`](twin2multicloud_backend/src/api/dependencies.py). The first API request with the header `Authorization: Bearer dev-token` will:
- return the first existing user, **or**
- if the DB is empty, create `dev@example.com` / "Developer" and return it.

The Flutter client hardcodes `dev-token` in [`lib/services/api_service.dart`](twin2multicloud_flutter/lib/services/api_service.dart), so **simply starting the Flutter app is enough to seed the dev user**.

#### 4c. Sample twins (opt-in via `SEED_DATA`)

[`twin2multicloud_backend/scripts/seed_twins.py`](twin2multicloud_backend/scripts/seed_twins.py) creates five pre-configured sample twins under a dedicated `seed@twin2multicloud.dev` user:

| Twin | Providers |
|------|-----------|
| `aws-single-cloud` | AWS only |
| `azure-single-cloud` | Azure only |
| `gcp-single-cloud` | GCP only |
| `mixed-all-providers` | AWS + Azure + GCP |
| `mixed-cost-optimized` | AWS + Azure + GCP (cost-optimized config) |

**Behaviour:**
- Idempotent — skips entirely if `seed@twin2multicloud.dev` already exists. Safe to restart.
- Twins with valid credentials advance to **CONFIGURED** state; invalid credentials leave them in **DRAFT**.

**Enabled by default** — `compose.yaml` already ships with:

```yaml
# management-api service
environment:
  - SEED_DATA=true
  - SEED_CREDENTIALS_FILE=/config/config_credentials.json
  - SEED_GCP_CREDENTIALS_FILE=/config/gcp_credentials.json
```

So if you filled in `config_credentials.json` and `gcp_credentials.json` (step 2), the sample twins are created automatically when the container starts.

**Disable seeding** (e.g. for production or a clean slate):

```yaml
# compose.yaml → management-api → environment
- SEED_DATA=false
```

**Re-seed from scratch** (e.g. after changing credentials):

```bash
# Option A — delete only the seed user (fast, non-destructive)
docker exec master-thesis-management-api-1 \
  python -c "
from src.models.database import SessionLocal
from src.models.user import User
db = SessionLocal()
u = db.query(User).filter_by(email='seed@twin2multicloud.dev').first()
if u: db.delete(u); db.commit(); print('Seed user deleted')
db.close()
"
docker compose restart management-api

# Option B — wipe the entire DB
docker compose down
rm twin2multicloud_backend/data/app.db
docker compose up -d
```

### 5. Run the Flutter app

In a second terminal:

```bash
cd twin2multicloud_flutter
flutter pub get
flutter run -d macos       # or: -d chrome, -d linux, -d windows
```

The first screen will auto-login as the mock developer user, hit the Management API, and thereby seed the DB (see step 4).

---

## Testing Deployments Without Cloud Cost

The Management API ships with two **mock deployment endpoints** that simulate a full Terraform deploy/destroy (with realistic SSE log streaming and mock Terraform outputs written to the DB) — **without ever touching a cloud provider**. Use these whenever you develop or test the deployment UI.

### The two toggles

| Side | Flag | Location | Default |
|------|------|----------|---------|
| Backend | `ENABLE_TEST_ENDPOINTS` (env var) | [`compose.yaml`](compose.yaml) → `management-api` | `true` |
| Flutter | `kUseTestDeploy` (compile-time const) | [`lib/bloc/twin_overview/twin_overview_bloc.dart`](twin2multicloud_flutter/lib/bloc/twin_overview/twin_overview_bloc.dart) | `true` |

Both flags must be consistent:

| Backend | Flutter | Result |
|---------|---------|--------|
| `true`  | `true`  | ✅ Mock deploys via the UI (current default) |
| `false` | `true`  | ❌ UI calls the endpoint and gets a 404 |
| `true`  | `false` | ⚠️ Real deploys — will incur cloud cost |
| `false` | `false` | ✅ Production mode |

### Backend endpoints

Both endpoints are guarded by `ENABLE_TEST_ENDPOINTS` in [`src/api/routes/twins.py`](twin2multicloud_backend/src/api/routes/twins.py). If the flag is off, they return 404. When on, they:

1. Create an SSE session and return `{session_id, sse_url}`
2. Spawn a background task that streams fake Terraform logs for `duration` seconds
3. Write a `Deployment` record with mock Terraform outputs to the DB
4. Transition the twin state (`DEPLOYING → ACTIVE` or `DESTROYING → INACTIVE`)

| Endpoint | Query params |
|----------|--------------|
| `POST /twins/{twin_id}/test-deploy`  | `duration` (5–120s, default 30), `should_fail` (bool) |
| `POST /twins/{twin_id}/test-destroy` | `duration` (5–60s, default 20), `should_fail` (bool) |

**Example — successful 15-second deploy:**
```bash
curl -X POST "http://localhost:5005/twins/<twin_id>/test-deploy?duration=15" \
  -H "Authorization: Bearer dev-token"
```

**Example — simulate a failure:**
```bash
curl -X POST "http://localhost:5005/twins/<twin_id>/test-deploy?duration=10&should_fail=true" \
  -H "Authorization: Bearer dev-token"
```

Subscribe to the returned `sse_url` (e.g. `/sse/deploy/<session_id>`) to see the streamed log events.

### Switching to real deployments

1. Edit [`compose.yaml`](compose.yaml) → set `ENABLE_TEST_ENDPOINTS=false` on the `management-api` service and restart: `docker compose up -d --build management-api`
2. Edit [`twin2multicloud_flutter/lib/bloc/twin_overview/twin_overview_bloc.dart`](twin2multicloud_flutter/lib/bloc/twin_overview/twin_overview_bloc.dart) → set `kUseTestDeploy = false` and `flutter run` again
3. Make sure your `config_credentials.json` contains valid keys for the providers you want to deploy to

> ⚠️ Once both flags are `false`, every "Deploy" click in the UI triggers a **real** multi-cloud Terraform run via `3-cloud-deployer`. Budget accordingly.

---

## Daily Usage

**Stop everything:**
```bash
docker compose down
```

**Rebuild after backend changes:**
```bash
docker compose up -d --build
```

**Tail logs:**
```bash
docker compose logs -f management-api
docker compose logs -f 2twin2clouds
docker compose logs -f 3cloud-deployer
```

**Run backend unit tests (safe — no cloud resources):**
```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1   python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v
```

> ⚠️ **Never run E2E tests (`tests/e2e/`) without explicit intent** — they deploy real cloud resources and cost money.

**Compile the LaTeX thesis (on-demand profile):**
```bash
docker compose --profile latex run --rm thesis-latex \
  latexmk -pdf -interaction=nonstopmode -cd /thesis/main.tex
```

---

## Troubleshooting

**Docker daemon not reachable**
Check your Docker context:
```bash
docker context ls
docker context use orbstack    # or: desktop-linux
```

**Flutter build errors about `FilePicker.platform` or `StateNotifier`**
These are fixed on the `ai/dev` branch. Run `flutter pub get` and rebuild.

**Backend returns 401 on every request**
Ensure `DEBUG=true` is set in the `management-api` service in `compose.yaml`, and that the client sends `Authorization: Bearer dev-token`.

**Empty `app.db` but no dev user created**
The dev user is only created on the first request. Start the Flutter app, or trigger it manually:
```bash
curl -H "Authorization: Bearer dev-token" http://localhost:5005/auth/me
```

---

## Documentation

- [integration_vision.md](integration_vision.md) — high-level project vision
- [ONBOARDING.md](ONBOARDING.md) — workflow rules for AI agents and contributors
- [FRONTEND_ARCHITECTURE.md](FRONTEND_ARCHITECTURE.md) — Flutter UI architecture
- [TODOS.md](TODOS.md) — current open work items
- Per-project guides:
  - [twin2multicloud_backend/DEVELOPMENT_GUIDE.md](twin2multicloud_backend/DEVELOPMENT_GUIDE.md)
  - [2-twin2clouds/DEVELOPMENT_GUIDE.md](2-twin2clouds/DEVELOPMENT_GUIDE.md)
  - [3-cloud-deployer/development_guide.md](3-cloud-deployer/development_guide.md)
