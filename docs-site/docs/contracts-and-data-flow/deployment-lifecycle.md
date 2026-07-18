# Deployment Lifecycle

## Selected Run To Provider Resources

```mermaid
sequenceDiagram
    actor Client as Flutter user
    participant API as Management API
    participant DB as Management database
    participant Deployer
    participant Cloud as AWS, Azure, or GCP

    Client->>API: Deploy configured twin
    API->>DB: Load selected run and specification
    API->>API: Revalidate context and preflight
    API->>API: Build manifest and canonical archive
    API->>Deployer: Stage archive
    Deployer->>Deployer: Validate all package contracts
    Deployer->>Deployer: Store bytes and issue one-use token
    Deployer-->>API: Package token
    API->>Deployer: Deploy with package token
    Deployer->>Deployer: Acquire token and create workspace
    Deployer->>Cloud: Terraform and bounded SDK calls
    Cloud-->>Deployer: Outputs or typed failure
    Deployer->>Deployer: Retain allowlisted outputs
    Deployer-->>API: Status, logs, and outputs
    API->>DB: Persist operation and lifecycle
    API-->>Client: REST status and SSE logs
```

## Artifact Lineage

```mermaid
flowchart TD
    subgraph Inputs["Validated inputs"]
        direction LR
        Run[("Selected run")] --> Specification["Resolved specification<br/>and digest"]
        Config["Twin configuration"]
        UserArtifacts["User functions and assets"]
    end

    subgraph Packaging["Immutable package lineage"]
        direction LR
        Manifest["Manifest 2.0"] --> Archive["Canonical archive"] --> Package["One-use package"]
    end

    subgraph Execution["Isolated execution"]
        direction LR
        Workspace["Ephemeral workspace"] --> Tfvars["Typed tfvars"]
        Tfvars --> Terraform["Terraform plan/apply"] --> Outputs[("Allowlisted outputs")]
    end

    Run --> Manifest
    Specification --> Manifest
    Config --> Manifest
    UserArtifacts --> Archive
    Package --> Workspace
```

The manifest carries the exact specification object and digest; it does not ask the
Deployer to repeat optimizer decisions. Only dimensions classified as
`deployable_selection` and registered with a `terraform_target` become tfvars.
Usage tiers, account-scoped plans, and non-deployable assumptions remain evidence.

## Validation Gates

```mermaid
flowchart TD
    subgraph PackageValidation["Package validation"]
        direction LR
        Archive["Incoming archive"] --> Limits{"Limits and<br/>path safety"}
        Limits -->|"pass"| Manifest{"Manifest<br/>contract"}
        Manifest -->|"pass"| Specification{"Specification<br/>and digest"}
    end

    subgraph ExecutionAdmission["Execution admission"]
        direction LR
        Bindings{"Provider and<br/>target bindings"} -->|"pass"| Token{"One-use token"}
        Token --> Workspace{"Isolated workspace"} --> Execute["Provider execution"]
    end

    Specification -->|"pass"| Bindings
    Limits -->|"fail"| Reject["Stable redacted rejection"]
    Manifest -->|"fail"| Reject
    Specification -->|"fail"| Reject
    Bindings -->|"fail"| Reject
```

No downstream component may recreate a missing dimension from calculator defaults,
template defaults, or Terraform defaults. Missing, stale, conflicting, unknown, or
secret-like data fails before provider execution.

## Operation Observability

The Management API persists lifecycle state and normalized operation records.
Deployer logs cross the boundary as structured events and are redacted before public
exposure. Flutter observes status through REST and logs through Management-owned SSE;
it does not connect to the Deployer stream directly.

See [Deployer](../components/deployer.md) and
[Deployment And Verification](../user-guide/deployment.md).
