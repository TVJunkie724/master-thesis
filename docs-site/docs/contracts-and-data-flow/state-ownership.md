# State Ownership

## Systems Of Record

```mermaid
flowchart LR
    subgraph Editable["Editable definitions"]
        Registry["Optimizer pricing_registry/*.yaml"]
        Profiles["Repository architecture profiles<br/>and component catalog"]
        TwinConfig["Management twin configuration"]
        Template["Versioned Deployer template"]
        UserAssets["Versioned user artifacts and assets"]
    end

    subgraph Durable["Durable generated state"]
        Catalogs[("Immutable regional catalogs")]
        Runs[("Calculation runs, items, paths,<br/>specifications, architectures")]
        Selections[("Twin profile selections")]
        Operations[("Deployment lifecycle,<br/>history, logs, outputs")]
        Runtime[("Deployer runtime project state")]
    end

    subgraph Ephemeral["Operation-local state"]
        Package["One-use operation package"]
        Workspace["Ephemeral workspace"]
        Secrets["Runtime-local credential material"]
    end

    Registry --> Catalogs
    Profiles --> Selections
    Profiles --> Runs
    Catalogs --> Runs
    TwinConfig --> Runs
    Runs --> Package
    TwinConfig --> Package
    Template --> Package
    UserAssets --> Package
    Package --> Workspace
    Secrets --> Workspace
    Workspace --> Runtime
    Workspace --> Operations
```

## Ownership Matrix

| State | System of record | Mutability | Main consumers |
|---|---|---|---|
| users, sessions, twins, lifecycle | Management database | transactional | Management API, Flutter |
| reusable cloud credentials | encrypted Management `cloud_connections` | owner-scoped transactional | credential resolver |
| wizard/configuration state | Management configuration tables and versions | transactional and lifecycle-invalidating | Flutter, run/deployment builders |
| pricing intents, mappings, formulas, models, routes | versioned Optimizer YAML registry | reviewed source change | refresh, calculation, validation |
| regional pricing catalogs | Optimizer immutable catalog store | append-only snapshots plus atomic active pointer | Management context resolution, calculation |
| pricing refresh/review history | Management database | append/update by workflow | Flutter pricing review |
| calculation results and specifications | Management database | immutable after successful run creation | Flutter, deployment selection |
| reviewed architecture definitions | repository `contracts/architecture-profiles/` | reviewed source change | all three backend validators |
| Twin architecture profile selection | Management database | owner-scoped, revisioned, invalidating | Management API; Flutter in Phase 8.7 |
| resolved Twin architecture | Management database canonical JSON plus derived component/edge rows | immutable per calculation run | Management reads; Optimizer/Deployer activation in Phases 8.5/8.6 |
| operation package | Deployer package store | immutable, one acquisition | deploy/destroy operation |
| operation workspace | Deployer temporary storage | mutable only during one operation | Terraform and provider adapters |
| runtime project state and allowlisted outputs | Deployer runtime store | operation-controlled | destroy, status, verification |
| deployment history/logs | Management database | append/update by operation | Flutter REST/SSE |

## Calculation Run Lifecycle

### Atomic Run Creation

```mermaid
flowchart TD
    subgraph Processing["Request processing"]
        direction LR
        Request["Calculation request"] --> Validate["Validate request and<br/>catalog context"]
        Validate --> Execute["Optimizer execution"]
    end
    subgraph Admission["Contract admission and persistence"]
        direction LR
        Contracts["Validate result, pricing,<br/>path, and deployment contracts"]
        Contracts --> Commit["Atomic persistence"]
        Commit --> Succeeded[("Succeeded run, items,<br/>traces, and specification")]
    end
    Execute --> Contracts
    Validate -. "failure" .-> Rejected["Rejected;<br/>no run row"]
    Execute -. "failure" .-> Rejected
    Contracts -. "failure" .-> Rejected
    Commit -. "rollback" .-> Rejected
```

### Selection And Deployment Readiness

```mermaid
flowchart TD
    subgraph SelectionPhase["Selection"]
        direction LR
        Succeeded[("Succeeded run")] --> Selection["Selection-time<br/>evidence verification"]
        Selection -->|"pass"| Selected[("Selection timestamp set")]
    end
    subgraph DeploymentPhase["Deployment admission"]
        direction LR
        Readiness["Deployment readiness<br/>revalidation"]
        Readiness -->|"pass"| Deployment["Eligible for deployment"]
    end
    Selected --> Readiness
    Selection -. "fail" .-> Blocked["Selection blocked"]
    Readiness -. "fail" .-> Blocked
    Blocked --> Recalculate["Calculate a new run"]
```

This diagram combines request processing with the durable run lifecycle. The
Management API currently persists only fully validated successful runs with
`status=succeeded`; rejected requests do not create a pending or failed run row.
Selection is represented by `selected_for_deployment_at`, not by changing the run
status. Staleness and incompatibility are evaluated at selection and deployment
readiness rather than written back as a mutable run status.

Historical successful runs remain inspectable. A run becomes deployable only when
its schema, catalog/account context, path evidence, and resolved specification remain
valid. Creating a newer run does not automatically select it; selecting another run
clears the previous run's selection timestamp.

Migration 022 additionally deselects every historical run that cannot be
reconstructed from complete matching architecture evidence. The Phase 8.4
fixture-gated admission boundary persists a failed run plus payload-free audit
evidence when architecture validation fails; it never commits a partial
resolution.

## Deployment State Transition

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Configured: validated configuration and selected run
    Configured --> Draft: configuration changes
    Configured --> Deploying: deploy accepted
    Destroyed --> Deploying: redeploy accepted
    Error --> Deploying: deploy retry accepted
    Deploying --> Deployed: success
    Deploying --> Error: failure
    Deployed --> Destroying: destroy accepted
    Error --> Destroying: cleanup accepted
    Destroying --> Destroyed: success
    Destroying --> Error: failure
    Draft --> Inactive: soft delete
    Configured --> Inactive: soft delete
    Deployed --> Inactive: soft delete
    Error --> Inactive: soft delete
    Destroyed --> Inactive: soft delete
```

`TwinLifecycleService` owns lifecycle transitions. Routes, Flutter, Optimizer, and
Deployer may request or report actions but must not invent state transitions.

See [State And Persistence](../runtime/state-and-persistence.md).
