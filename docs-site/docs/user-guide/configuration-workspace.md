# Configuration Workspace

The workspace presents one dependency-aware Twin workflow.

| Responsibility | Typical content |
|---|---|
| Define Twin | unique identity and draft metadata |
| Architecture | read-only canonical Six-layer explanation |
| Workload | scenario, devices, traffic, processing, retention and Twin inputs |
| User logic | bounded processor/rule/feedback extensions |
| Optimize and review | cost calculation, exclusions, assumptions, trace and immutable selection |
| Deployment preparation | connection binding, readiness, repair, plan review and validation |

## Dependency order

```text
Twin identity
  -> canonical contract understood
  -> workload + required bounded functions valid
  -> calculation and immutable review
  -> required deployment CloudConnections selected
  -> graph readiness and repair complete
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
