# Optimizer Development Guide

Use the root [Handbook](../HANDBOOK.md) and [Onboarding](../ONBOARDING.md) as
the canonical repository workflow. This file contains only Optimizer-specific
rules.

## Runtime Boundary

- Flutter calls the Management API only.
- The Management API calls the Optimizer.
- Request-body credentials are ephemeral and must never be persisted or logged.
- Local credential files are available only through the explicit local cloud
  Compose overlay.
- GCP self-hosted L4/L5 options remain disabled until matching Deployer support
  exists.

## Docker Workflow

From the repository root:

```bash
docker compose build 2twin2clouds
docker compose up -d 2twin2clouds
docker compose logs -f 2twin2clouds
```

Run the full offline gate:

```bash
docker compose run --rm --no-deps 2twin2clouds sh -lc \
  'python -m pytest tests -q && \
   ruff check api backend rest_api.py && \
   python -m bandit -r api backend rest_api.py -q && \
   python -m compileall -q api backend rest_api.py && \
   python -m pip check'
```

Do not run live provider refreshes merely to validate a code change. Provider
catalog tests use fixtures and mocks; live access is an explicit supervised
verification step.

## Change Ownership

| Change | Required evidence |
|---|---|
| Formula or normalization | Focused formula tests plus complete suite |
| Provider matching/fetching | Provider fixture matrix, evidence assertions, complete suite |
| Pricing registry | Registry validation, traceability tests, complete suite |
| API contract | Route/OpenAPI tests and Management API compatibility tests |
| Credential, error, or logging behavior | Redaction/error tests, Bandit, complete suite |
| Cache publication | Concurrency and atomic-publication tests |

Pricing and calculation changes must remain explainable through registry IDs,
evidence, normalization metadata, formula references, and result traces.

## Extension Points

New optimization objectives belong in the established extension points under
`backend/optimization/` and must bind a compatible metric provider,
calculation model, scoring strategy, pricing intent group, formula set, workload
contract, and result schema. Disabled declarations are not executable features.

New provider layer calculators return the canonical
`backend.calculation_v2.layers.LayerResult` contract. Unsupported capabilities
must be explicit and must never enter provider selection as zero-cost options.

## Planning And Backlog

Check `implementation_plans/` and `docs/plans/` before changing architecture.
GitHub Issues are the backlog source of truth; do not create service-local TODO
lists.
