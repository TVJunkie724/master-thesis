# Current deployment graph

Every calculation resolves one immutable `six-layer-eventing@1` graph. The
graph names the selected provider component, required input/output ports,
directed routes, cost owners, packages, identities, permissions, Terraform
bindings, probes and cleanup expectations.

```text
devices -> ingestion -> eventing -> processing -> hot storage
                                      |              |
                                      |              +-> cool -> archive
                                      |              +-> Twin projection
                                      +-> actions / bounded feedback

Twin projection and raw history -> visualization access
```

The exact order and fan-out are defined by the canonical contract rather than
reconstructed from this explanatory diagram. Provider-local paths may use a
native trigger; cross-provider paths use the contract-selected bridge and
attribute transfer cost to the directed edge.

## Source-of-truth flow

```text
typed Twin intent
      |
      v
Optimizer: admissible provider assignment + costs + resolved graph
      |
      v
Management: validate and persist immutable evidence
      |
      v
Deployer: requirements + operation package + typed Terraform inputs
      |
      v
provider resources -> probes -> access handoff -> cleanup evidence
```

The graph digest binds readiness, preparation confirmation, deployment and
verification. A changed workload, provider allocation, extension source or
contract produces a new calculation; stale evidence cannot be reused.

Five-layer v1 is an Optimizer-only offline baseline. It does not enter this
graph or any deployment operation.
