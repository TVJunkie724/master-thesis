# Twin2Clouds Cost Optimizer

The Optimizer is the calculation component of the Twin2MultiCloud thesis PoC.
It owns frozen pricing evidence, provider formulas, functional-completeness
admission, complete-path monetary comparison, traceability, and construction of
the immutable Six-layer deployment decision.

It does not persist users or Twins, handle deployment credentials, or mutate
cloud resources.

## Scope

- one standalone `six-layer-eventing@1` architecture;
- one estimated-monetary-cost objective and internal scoring strategy;
- exact dated/cited/hashed AWS, Azure, and GCP pricing snapshots;
- provider capability, component, edge, route, formula, and deployment
  evidence;
- resolved architecture v2 and resolved deployment specification v2;
- immutable intent-to-result traceability.

The original Five-layer v1 calculation remains an Optimizer-only offline
baseline. It is not exposed to Management, Flutter, Deployer, Terraform, or
live E2E.

The service has no objective/profile selector and no live pricing fetch,
refresh, review, approval, account-plan, currency-refresh, or credential
subsystem.

## Calculation flow

```text
Management request
  -> fixed workload + canonical architecture pin
  -> exact frozen provider snapshot references
  -> functionally complete provider assignments
  -> component + edge + transfer costs
  -> minimum monthly monetary total
  -> result + trace + resolved graph/specification
```

Candidates missing a required capability or evidence reference fail closed and
never enter ranking as zero-cost alternatives.

## API

| Method | Route | Purpose |
|---|---|---|
| `PUT` | `/calculate` | execute the fixed Six-layer cost calculation |
| `POST` | `/validate/optimizer-config` | validate calculation input/result shape |
| `GET` | `/capabilities/providers` | read calculation capability evidence |
| `GET` | `/pricing/catalogs/baseline/{provider}` | read a pinned thesis reference |
| `GET` | `/pricing/catalogs/{provider}/{region}/snapshots/{id}/reference` | verify exact identity/digest |
| `GET` | `/pricing/catalogs/{provider}/{region}/snapshots/{id}` | bounded diagnostic snapshot read |

The API is internal. Flutter calls only the Management API.

## Main directories

| Path | Purpose |
|---|---|
| `api/` | FastAPI transport adapters |
| `backend/calculation_v2/` | provider calculations, formulas, paths and traces |
| `backend/architecture_profiles/` | fixed Six-layer resolution and historical baseline adapter |
| `backend/optimization/` | cost-only scoring seam |
| `json/pricing_catalog_baselines/` | pinned reviewed pricing snapshots |
| `pricing_registry/` | formula, intent, workload and provider contracts |
| `tests/` | deterministic unit, contract and regression evidence |

## Safe verification

```bash
cd 2-twin2clouds
PYTHONPATH=. python -m pytest -q
```

Tests use repository fixtures and do not contact providers. A successful test
run is offline evidence only.
