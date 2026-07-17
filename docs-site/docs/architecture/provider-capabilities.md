# Provider Capabilities

Provider parity is an explicit runtime contract. A provider-layer path is not treated
as usable merely because it has a price, appears in the five-layer model, or existed
as an aspiration in the bachelor-project baseline.

## Ownership And Data Flow

Calculation and provisioning are separate capabilities with separate owners:

```text
Optimizer runtime registry              Deployer runtime registry
  calculation support                     provisioning support
          |                                      |
          v                                      v
 GET /capabilities/providers          GET /capabilities/providers
          |                                      |
          +------------------+-------------------+
                             v
                  Management API aggregation
                  - validates both contracts
                  - derives effective availability
                  - fails closed on drift/outage
                             |
                             v
          GET /platform/provider-capabilities
                             |
                             v
                   Flutter / demo adapters
```

The Optimizer is the source of truth for calculability. The Deployer is the source of
truth for provisionability. The Management API is the only platform view consumed by
Flutter. No UI provider-name condition is a capability source of truth.

## Canonical Matrix

The current platform exposes all 21 provider-layer rows:

| Provider | L1 | L2 | L3 hot | L3 cool | L3 archive | L4 | L5 |
|---|---|---|---|---|---|---|---|
| AWS | available | available | available | available | available | available | available |
| Azure | available | available | available | available | available | available | available |
| GCP | available | available | available | available | available | unsupported, planned | unsupported, planned |

`available` means that both calculation and deployment implementations exist and have
deterministic contract evidence. It does not mean that the path has passed the final
supervised live-cloud E2E gate.

## Contract Semantics

Each service publishes `provider-service-capabilities.v1`; the Management API returns
`platform-provider-capabilities.v1`.

| Field | Meaning |
|---|---|
| `availability` | `available`, `disabled`, or `unsupported` implementation state |
| `roadmap` | independent `none` or `planned` future-work marker |
| `selectable` | derived true only for aggregate `available` |
| `verification_level` | weakest source level: `not_verified`, `contract_tested`, `live_verified` |
| `sources` | Optimizer and Deployer source states for diagnostics |
| `sources_agree` | whether both service availability states match |
| `restriction_source` | service boundary that prevents selection |

Aggregation is fail-closed. `disabled` has precedence, followed by `unsupported`; a row
is available only when both services report available. Missing rows, duplicates,
unknown identities, incompatible versions, unavailable services, and malformed source
contracts never produce a partially selectable matrix.

## Enforcement

- The Optimizer marks unsupported layer results and excludes them from scoring.
- The Deployer rejects unavailable selections with `CAPABILITY_UNAVAILABLE` before a
  workspace, Terraform process, or provider call is created.
- Distributed Management API validation preserves the typed provider/layer error.
- Flutter loads the aggregate matrix through `ManagementApi`, keeps saved state
  readable, and hides unavailable editors behind an actionable capability status.
- Demo mode implements the same API and matrix without network access.

If capability discovery itself fails, configuration remains fail-closed and offers a
retry. No hard-coded fallback matrix is activated.

## Extending A Provider Or Layer

1. Implement and test the Optimizer calculator, including a supported `LayerResult`.
2. Add and test the Deployer package/provisioning path and lifecycle behavior.
3. Change each owning runtime registry only when its implementation exists.
4. Run each service's complete 3 x 7 matrix and execution-boundary tests.
5. Verify Management API aggregation, disagreement behavior, and Flutter/demo parsing.
6. Update this matrix and provider setup documentation.
7. Record supervised live evidence separately before changing a row to
   `live_verified`.

Roadmap intent alone never makes a path selectable. GCP L4/L5 implementation remains
tracked by [#54](https://github.com/TVJunkie724/master-thesis/issues/54). A separate
architecture audit is tracked by
[#112](https://github.com/TVJunkie724/master-thesis/issues/112); until an implemented
contract changes, this page documents the current runtime matrix only.
