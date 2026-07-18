# Credentials And Trust

## Credential Categories

```mermaid
flowchart TB
    subgraph RuntimeSecrets["Application runtime secrets"]
        JWT["JWT signing key"]
        Encryption["CloudConnection encryption key"]
        IdentitySecret["OAuth or SAML secret/key"]
    end

    subgraph ExternalBootstrap["External bootstrap boundary"]
        Admin["Authenticated provider CLI<br/>admin session"]
        Plan["Management bootstrap plan<br/>contains no admin secret"]
        Script["Versioned static provider script<br/>dry-run before explicit apply"]
        Generated["Ignored local deployment<br/>CloudConnection JSON"]
    end

    subgraph Durable["Durable user-owned cloud access"]
        Import["Authenticated import/create boundary"]
        Pricing["Pricing CloudConnection"]
        Deployment["Deployment CloudConnection"]
        Store[("Encrypted Management database payload")]
    end

    Admin --> Script
    Plan --> Script
    Script -->|"creates scoped material"| Generated
    Generated --> Import --> Deployment
    Import -->|"separate AWS/GCP pricing import"| Pricing
    Pricing --> Store
    Deployment --> Store
    Encryption --> Store
    JWT -. "never grants cloud access" .-> Durable
    IdentitySecret -. "never grants cloud access" .-> Durable
```

Application runtime secrets and cloud-provider credentials are different security
domains. Neither may substitute for the other. The current bootstrap scripts create
deployment identities only; AWS and GCP pricing connections are imported separately,
while Azure pricing uses a public API.

## Bootstrap And Reuse

```mermaid
sequenceDiagram
    actor Operator
    participant API as Management API
    participant CLI as Provider CLI and static script
    participant DB as Encrypted CloudConnection store

    Operator->>API: Request plan through authenticated API
    API-->>Operator: Static script path, dry-run/apply commands, permission-set version
    Operator->>CLI: Authenticate through the provider CLI outside the app
    Operator->>CLI: Review dry-run, then apply explicitly
    CLI-->>Operator: Ignored local deployment CloudConnection JSON
    Operator->>API: Import generated scoped connection
    API->>DB: Encrypt payload and append security audit event
    API-->>Operator: Non-secret metadata and validation actions
```

The Management API never receives the bootstrap/admin credential. The reusable object
is the generated scoped deployment CloudConnection. Admin authentication remains in
the external provider CLI session, and the generated local JSON must not be committed.
The API contract is implemented, but Flutter does not currently expose the bootstrap
plan/import workflow; use authenticated OpenAPI/HTTP access for this operation.
See [Cloud Setup](../cloud-setup/index.md) for the operator sequence.

## Purpose-Aware Runtime Resolution

```mermaid
flowchart LR
    Store[("Encrypted CloudConnections")]
    Resolver["Owner- and purpose-aware resolver"]
    Pricing["Pricing request"]
    Deployment["Twin deployment request"]
    Optimizer["Optimizer"]
    Deployer["Deployer"]
    Workspace["Ephemeral operation workspace"]
    Logs["Redacted logs and public errors"]

    Store --> Resolver
    Pricing --> Resolver
    Deployment --> Resolver
    Resolver -->|"pricing purpose and confirmed account"| Optimizer
    Resolver -->|"deployment purpose and twin binding"| Deployer
    Deployer -->|"runtime-local materialization"| Workspace
    Optimizer --> Logs
    Deployer --> Logs
```

AWS and GCP pricing refreshes require an explicitly confirmed pricing
CloudConnection. Azure catalog pricing uses its public API path. Deployment
connections are bound to twins and are not silently reused as pricing defaults.

## Secret Exit Rules

| Boundary | Allowed to leave | Forbidden to leave |
|---|---|---|
| bootstrap plan API | provider/account metadata, permission-set version, static commands | admin credential plaintext |
| external bootstrap script | ignored local scoped deployment credential | admin secrets as script arguments or committed output |
| encrypted store | owner-safe CloudConnection metadata | decrypted payload |
| Optimizer validation | typed status, safe error code/message | echoed credential fragments |
| Deployer operation | structured redacted logs, status, allowlisted outputs | credential files, Terraform secret values |
| Flutter API | labels, purpose, provider, account/project identity, validation state | secret material |

See [Security And Trust Boundaries](../architecture/security-boundaries.md) and
[Cloud Accounts](../user-guide/cloud-accounts.md).
