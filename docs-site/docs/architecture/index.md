# Architecture

Twin2MultiCloud integrates two original Bachelor projects with a new orchestration
and user-interface layer. The architecture deliberately separates user workflow,
durable state, optimization semantics, and cloud execution.

## Architectural Rules

1. Flutter calls only the Management API.
2. The Management API owns users, twins, durable workflow state, and orchestration.
3. The Optimizer owns pricing intent, evidence, normalization, formulas, and ranking.
4. The Deployer owns provider execution, Terraform state, packaging, and probes.
5. Credentials are encrypted user-scoped CloudConnections; plaintext is transient.
6. Versioned templates and registries are source material; generated artifacts are not editable truth.
7. Live-cloud E2E is opt-in because it can create resources and cost.

Read in this order:

- [System Context](system-context.md)
- [Responsibilities and Data Ownership](data-ownership.md)
- [End-to-End Flows](end-to-end-flows.md)
- [Security and Trust Boundaries](security-boundaries.md)
- [Original to Current State](evolution.md)
