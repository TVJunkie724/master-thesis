# Responsibilities and Data Ownership

| Concern | System of record | Consumers |
|---|---|---|
| users, Twin identity and lifecycle | Management database | Flutter and orchestration |
| canonical architecture pin | Management database plus repository contract digest | calculation, deployment, evidence reads |
| typed Twin configuration | Management database and allowlisted files | Optimizer and Deployer |
| deployment CloudConnections | encrypted Management records | Deployer request boundary only |
| frozen price snapshots and formula contracts | Optimizer repository | calculation and exact-reference checks |
| calculation result and immutable resolved graph | Management database | Flutter, readiness, package generation |
| operation history, replay cursor, verification and cleanup | Management database | Flutter REST/SSE reads |
| Terraform/runtime state | Deployer runtime storage | status and explicit Destroy |
| research method and evidence | `docs/research` | thesis analysis |

## Invariants

- Flutter cannot author calculation, cost, graph, verification, or cleanup
  evidence.
- Management stores exact pricing references rather than editable price
  copies.
- A Twin pin always identifies the one canonical contract; it is not a
  user-selectable profile.
- The Deployer workspace may change during one operation, but only allowlisted
  outputs and typed evidence return to Management.
- Secret values do not enter responses, logs, archives, events, or retry state.

Deployed Twin definitions are immutable. A changed experiment becomes a new
draft through Duplicate or typed Import, with an independent calculation and
lifecycle.
