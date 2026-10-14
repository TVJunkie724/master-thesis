# Twin2MultiCloud handbook

This is the practical entry point for local work on the thesis proof of
concept. The target scope and research rationale live in the documents linked
from the root README; this handbook intentionally contains no product roadmap.

## 1. Safe local setup

Required tools:

- Docker or OrbStack with Docker Compose;
- Flutter 3.44 with Dart 3.12;
- Python 3.9 or newer; and
- Git.

Start the complete local stack:

```bash
./thesis.sh up
```

Common variants:

```bash
./thesis.sh up --no-flutter
./thesis.sh up --setup
./thesis.sh flutter
./thesis.sh demo --setup
./thesis.sh status
./thesis.sh logs management-api
./thesis.sh down
```

`demo` uses deterministic in-memory adapters and makes no network or cloud
call. `up` starts the credential-free local services and writes the ignored
Flutter development configuration.

## 2. Runtime configuration

Flutter receives configuration through
`--dart-define-from-file=config/dev.json`. The generated local file contains
the Management API URL and a local development token and is ignored by Git.
Tracked example files define development, demo and fail-closed deployment
shapes without containing secrets.

The Management API requires one local runtime encryption key:

```text
.secrets/runtime/ENCRYPTION_KEY
```

The root script creates it with restricted permissions and never prints or
rotates an existing value. The encryption key protects stored CloudConnections;
deleting it can make local encrypted records unreadable.

Provider credentials are a separate boundary. The default stack does not need
or mount them. For the eventual supervised evaluation, store credentials only
through the Management API or ignored local secret files. Never commit, paste,
log or add real values to evidence.

## 3. Runtime ownership

```text
Flutter
   |
   v
Management API
   |          |
   v          v
Optimizer   Deployer
```

- Flutter presents typed inputs, review, readiness and operation state.
- Management owns users, Twins, CloudConnections, immutable evidence and the
  public API.
- Optimizer owns frozen pricing, formulas, admissibility and cost scoring.
- Deployer owns package validation, readiness requirements, Terraform,
  verification and cleanup.

Direct Flutter calls to Optimizer or Deployer are outside the architecture.

## 4. Offline quality gates

```bash
./thesis.sh test backend
./thesis.sh test frontend
./thesis.sh test frontend-integration
./thesis.sh test deployment-contract --focused
./thesis.sh test deployment-contract
```

The deployment-contract gate strips provider credentials, rejects live E2E
flags and performs no Terraform apply. It validates the frozen Optimizer result
through Management persistence, Manifest v4, typed Terraform variables and
credential-free mock plans.

Individual service commands:

```bash
cd 2-twin2clouds && python -m pytest
cd twin2multicloud_backend && python -m pytest
cd 3-cloud-deployer && python -m pytest
cd twin2multicloud_flutter && flutter analyze && flutter test
```

Build the documentation locally with the pinned container:

```bash
docker compose --profile docs run --rm docs mkdocs build --strict
```

Compile the thesis independently:

```bash
./thesis.sh latex once
```

## 5. Live-cloud boundary

Live provider validation, preparation, Deploy, telemetry verification and
Destroy can change external state or incur cost. They require a separate,
explicitly supervised evaluation session. Before a live run:

1. freeze the scenario, regions, pricing references and budget;
2. select isolated thesis accounts and pre-existing administrator
   CloudConnections;
3. inspect identity and graph-derived readiness without mutation;
4. review every proposed persistent provider change;
5. run one Small scenario at a time;
6. verify function immediately; and
7. Destroy, inventory remaining resources and record residual state.

Offline fixtures and Terraform plans are never reported as live evidence.

## 6. Current documentation

- `README.md` — repository overview
- `ONBOARDING.md` — branch, safety and repository rules
- `integration_vision.md` — architecture boundary
- `FRONTEND_ARCHITECTURE.md` — Flutter structure
- `docs-site/` — user and developer documentation
- `docs/plans/2026-08-26_thesis_poc_target_concept.md` — scope
- `docs/plans/2026-08-26_thesis_poc_execution_plan.md` — execution state
- `docs/development_and_decision_log.md` — durable decisions

Git history, not the active documentation tree, preserves superseded
implementation handoffs and abandoned product directions.
