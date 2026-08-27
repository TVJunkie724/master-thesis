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

Do not call live provider pricing APIs merely to validate a code change. The
thesis uses frozen catalog snapshots; live cloud access is a separate,
supervised evaluation boundary.

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

The thesis runtime contains only the monetary-cost implementation under
`backend/optimization/`. A future objective can reuse the metric, calculation,
and scoring boundaries only after its evidence, formula, workload, result, and
regression contracts exist; inactive declarations do not belong in runtime
configuration.

New provider layer calculators return the canonical
`backend.calculation_v2.layers.LayerResult` contract. Unsupported capabilities
must be explicit and must never enter provider selection as zero-cost options.
Provider calculator sets inherit `BaseLayerCalculatorSet`, declare their
`supported_layers`, and construct results through the provider-bound `_result`
factory. New selection logic must use the result capability state; provider-name
exceptions are not an accepted extension mechanism.

The shared provider-layer test matrix is the minimum regression gate for changes
to calculator capabilities or result fields. `LayerResult` owns an immutable
component snapshot and rejects unknown providers/layers, booleans masquerading as
numbers, negative/non-finite values, and ambiguous unsupported states.

## Planning

Check the active target, research questions, execution plan and decision log
before changing architecture. Use one temporary task plan when needed, then
move durable rationale into current documentation and let Git preserve the
completed implementation history. Do not create service-local TODO or roadmap
trees.
