# Cost Optimizer

The Optimizer is an internal calculation service. It owns frozen pricing
snapshots, formulas, capability admission, complete-path cost evaluation, the
cost scorer, and construction of the immutable Six-layer deployment result.

It does not persist users/Twins, validate deployment credentials, mutate cloud
resources, or administer provider prices.

## Runtime API

| Method and route | Purpose |
|---|---|
| `PUT /calculate` | calculate the fixed cost-only Six-layer result |
| `POST /validate/optimizer-config` | validate calculation parameters/result shape |
| `GET /capabilities/providers` | read calculation/provider capability metadata |
| `GET /pricing/catalogs/baseline/{provider}` | read one pinned thesis reference |
| `GET /pricing/catalogs/{provider}/{region}/snapshots/{id}/reference` | verify exact identity and digest |
| `GET /pricing/catalogs/{provider}/{region}/snapshots/{id}` | bounded diagnostic snapshot read |

There are no credential-validation, price-fetch, refresh, stream, publication,
review, approval, health, or administration endpoints.

## Calculation boundary

`six-layer-eventing@1` supplies the closed set of responsibilities, components,
edges, extension slots, and provider implementation bundles. The Optimizer
rejects missing capability, formula, pricing, route, region, deployment, or
extension evidence before ranking candidates.

Only estimated monetary cost participates in scoring. One internal strategy
implements the scoring seam and emits a complete trace. No objective registry,
weighted scoring, or public strategy selection is active.

## Pricing boundary

Each calculation binds exact repository snapshot IDs and digests. The service
does not fetch current provider prices during a calculation and does not accept
account-specific pricing context. AWS TwinMaker uses the reviewed Standard
model required by the canonical architecture; account plan switching/tiering
administration is outside scope.

## Historical baseline

Five-layer v1 remains an immutable offline reproduction inside the Optimizer
for scientific comparison. It has no Management, Flutter, Deployer, Terraform,
or live-E2E surface.
