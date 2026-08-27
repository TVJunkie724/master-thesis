# Twin2MultiCloud

Twin2MultiCloud is a research proof of concept for translating a typed Digital
Twin scenario into a cost-optimized Six-layer deployment across AWS, Azure and
Google Cloud. It is built to answer the thesis research questions with
traceable contracts, reproducible cost evidence and supervised live-cloud
verification; it is not a production cloud-management product.

The active scope is defined by:

- [`docs/plans/2026-08-26_thesis_poc_target_concept.md`](docs/plans/2026-08-26_thesis_poc_target_concept.md)
- [`docs/plans/2026-08-26_thesis_poc_execution_plan.md`](docs/plans/2026-08-26_thesis_poc_execution_plan.md)
- [`docs/research/research_questions_and_evaluation_design.md`](docs/research/research_questions_and_evaluation_design.md)
- [`docs/development_and_decision_log.md`](docs/development_and_decision_log.md)

## Repository

| Directory | Responsibility |
|---|---|
| `twin2multicloud_flutter/` | Flutter research workflow |
| `twin2multicloud_backend/` | Management API, persistence and orchestration |
| `2-twin2clouds/` | deterministic cost optimizer |
| `3-cloud-deployer/` | graph validation, Terraform execution and verification |
| `contracts/` | canonical cross-service architecture contract |
| `docs-site/` | current user and developer documentation |
| `docs/research/` | research method and evidence |
| `twin2multicloud-latex/` | thesis source |

Flutter communicates only with the Management API. Management owns the public
workflow and calls the Optimizer and Deployer through bounded internal
contracts.

## Supported boundary

The only deployable architecture is `six-layer-eventing@1`. It models
Ingestion, Processing, Storage, Management, Visualization and Eventing as
explicit responsibilities. Five-layer v1 exists only as an Optimizer-side
offline comparison baseline and is not selectable or deployable.

The normal workflow provides:

1. draft Twin creation, typed configuration and bounded import;
2. cost-only optimization against frozen, cited pricing snapshots;
3. selection of existing encrypted CloudConnections;
4. graph-derived readiness, confirmed bounded preparation and repair guidance;
5. immutable deployment with durable operation progress;
6. access handoff, one telemetry roundtrip and explicit Destroy; and
7. typed secret-free Twin Duplicate/Export/Import for reproduction.

Live cloud work is never part of ordinary CI or local startup. It requires an
explicitly supervised run, a cost limit and cleanup evidence.

## Local start

Prerequisites are Docker with Compose, Flutter 3.44/Dart 3.12, Python and Git.

```bash
./thesis.sh up
```

Useful safe variants:

```bash
./thesis.sh up --no-flutter
./thesis.sh demo --setup
./thesis.sh status
./thesis.sh down
```

The default Compose stack is credential-free. Local Management API signing and
encryption keys are generated under ignored `.secrets/runtime/`; real provider
credentials are neither required nor mounted.

For detailed setup and safe commands, use [`HANDBOOK.md`](HANDBOOK.md). The
published documentation can be served with:

```bash
./thesis.sh docs up
```

## Offline verification

```bash
./thesis.sh test backend
./thesis.sh test frontend
./thesis.sh test deployment-contract
```

The deployment-contract gate is credential-free and performs no Terraform
apply. Service-specific test commands are documented in the component READMEs
and [`docs-site/docs/developer-guide/testing.md`](docs-site/docs/developer-guide/testing.md).

Do not run live E2E tests or provider mutations merely to verify a code change.
The nine final Small scenarios are a separate, supervised evaluation phase.

## Documentation map

- [`HANDBOOK.md`](HANDBOOK.md) — local development and verification
- [`ONBOARDING.md`](ONBOARDING.md) — repository boundaries and contribution rules
- [`integration_vision.md`](integration_vision.md) — end-to-end architecture
- [`FRONTEND_ARCHITECTURE.md`](FRONTEND_ARCHITECTURE.md) — current Flutter structure
- [`docs-site/`](docs-site/) — current user and developer guide
