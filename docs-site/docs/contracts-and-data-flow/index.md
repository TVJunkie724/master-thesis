# Contracts And Data Flow

This section visualizes the implemented cross-project contracts and runtime data
flows of Twin2MultiCloud. It is developer documentation for the current system, not
a proposed architecture and not a thesis evaluation.

## Reading Order

1. [System Boundaries](system-boundaries.md) identifies the projects, external
   systems, persistence boundaries, and allowed network direction.
2. [Cross-Project Contract Map](contract-map.md) shows which project produces and
   consumes each material contract.
3. [Pricing And Optimization](pricing-optimization.md) follows pricing evidence
   from acquisition through formulas, scoring, and deployment selection.
4. [Deployment Lifecycle](deployment-lifecycle.md) follows the selected optimizer
   run through the operation package, Terraform, status, logs, and outputs.
5. [Credentials And Trust](credentials-and-trust.md) shows how bootstrap,
   pricing, and deployment credentials cross trust boundaries.
6. [State Ownership](state-ownership.md) identifies the system of record for
   editable definitions, durable application state, and generated runtime state.

## Diagram Conventions

| Shape or line | Meaning |
|---|---|
| rectangle | service, adapter, process, or contract transformation |
| cylinder | durable state or versioned artifact store |
| solid arrow | implemented production/consumption or runtime call |
| dashed arrow | non-runtime relation, explicit exclusion, or documented limitation |
| subgraph | ownership or trust boundary |

Diagram arrows show data or contract direction. They do not grant direct network
access. In particular, Flutter communicates only with the Management API; the
Optimizer and Deployer remain internal services.

## Status And Scope

The diagrams cover the current five-layer baseline and its current contract
versions. Planned architecture profiles and the proposed eventing layer belong to
research and implementation-planning material until they are implemented. Whenever
the executable contracts change, update this section in the same change and run:

```bash
docker compose --profile docs run --rm docs mkdocs build --strict
```

The prose-oriented architecture pages remain available under
[Architecture](../architecture/index.md). This section is intentionally a separate
visual contract reference rather than a replacement for those pages.
