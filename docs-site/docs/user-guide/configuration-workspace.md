# Configuration Workspace

The workspace presents one dependency-aware Twin workflow through four thesis
phases. The phase row is the stable map; the task selector lists only the
current phase. Use **Back** and **Continue** for the complete ordered workflow,
or select a reachable phase directly.

| Phase | Typical content |
|---|---|
| Scenario | Twin identity, canonical Six-layer contract, workload and bounded user logic |
| Optimize | cost calculation, exclusions, assumptions, trace and immutable selection |
| Prepare | CloudConnection binding, data contracts and Twin assets |
| Review | summary, readiness findings, validation and preflight |

A phase with unmet prerequisites is disabled and explains the blocker. A task's
status remains accurate when the task is selected. The bottom bar uses one
primary next action: **Calculate** on the calculation task, otherwise
**Continue** or **Finish configuration**. Save remains a secondary draft
action.

## Dependency order

```text
Twin identity
  -> canonical contract understood
  -> workload + required bounded functions valid
  -> calculation and immutable review
  -> required deployment CloudConnections selected
  -> graph readiness complete
  -> bounded preparation/repair confirmation
  -> deployment confirmation
```

There is no architecture-profile or objective choice. A material draft edit
invalidates downstream calculation/readiness evidence and requires a new run.

## Configuration input

Typed forms are the primary path. Corresponding versioned individual files may
be imported and validated when a university experiment already has compatible
configuration. The user does not upload an arbitrary deployment directory.

Twin Export/Import packages the allowlisted configuration and bounded extension
sources for sharing, without credentials, Terraform state, operation history,
or secret outputs.

## Calculation review

The default view shows the selected placement and monthly cost. Technical
details expose exact frozen pricing/formula references, component/edge
contributions, exclusions, functional-completeness evidence, and immutable
graph/specification digests. Flutter never recalculates those values.

Real provider work begins only after the calculation is reviewed and the
required named deployment connections are bound.
