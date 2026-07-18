# System Boundaries

## Runtime Landscape

```mermaid
flowchart TD
    User["User"]
    Flutter["Flutter client<br/>Web, macOS, Windows, Linux"]
    IdP["External identity provider<br/>Google OAuth or UIBK SAML"]

    subgraph Application["Twin2MultiCloud runtime"]
        Management["Management API :5005<br/>public API and orchestration"]
        Optimizer["Optimizer :5003<br/>pricing and cost optimization"]
        Deployer["Deployer :5004<br/>infrastructure execution"]
        ManagementDB[("Management database")]
        CatalogStore[("Pricing registry and<br/>immutable regional catalogs")]
        RuntimeStore[("Deployment runtime state")]
    end

    Providers["External provider boundaries<br/>AWS APIs | Azure APIs | Google Cloud APIs"]

    Docs["MkDocs :5010<br/>documentation only"]

    User --> Flutter
    Flutter -->|"REST and SSE"| Management
    Flutter -->|"browser sign-in"| IdP
    IdP -->|"one-time callback and exchange"| Management
    Management -->|"durable state"| ManagementDB
    Management -->|"typed internal HTTP"| Optimizer
    Optimizer --> CatalogStore
    Management -->|"archive and operation commands"| Deployer
    Deployer --> RuntimeStore
    Deployer -->|"Terraform and bounded SDK calls"| Providers
    Docs -. "not part of the application data path" .-> Application
```

## Project Responsibilities

| Project | Owns | Must not own |
|---|---|---|
| Flutter | presentation, local interaction state, typed Management API adapters | durable optimizer results, provider pricing logic, direct Optimizer/Deployer calls |
| Management API | users, twins, configuration, CloudConnections, durable runs, lifecycle orchestration, public contract shaping | provider formula implementation, Terraform resource execution |
| Optimizer | pricing acquisition, immutable catalogs, pricing registry, formula execution, path scoring, resolved deployment specification production | user identity, twin lifecycle persistence, cloud deployment |
| Deployer | package validation, typed infrastructure translation, isolated workspaces, Terraform and bounded SDK operations | optimization decisions, pricing selection, application user state |
| Docs | canonical user/developer documentation | runtime application state |

## Allowed Network Direction

```mermaid
flowchart LR
    Flutter["Flutter"] --> Management["Management API"]
    Management --> Optimizer["Optimizer"]
    Management --> Deployer["Deployer"]
    Optimizer --> ProviderPricing["Provider pricing APIs"]
    Deployer --> ProviderRuntime["Provider infrastructure APIs"]

    Flutter -. "forbidden" .-> Optimizer
    Flutter -. "forbidden" .-> Deployer
    Optimizer -. "no lifecycle writes" .-> Management
    Deployer -. "no optimizer decisions" .-> Optimizer
```

The locally published Optimizer and Deployer ports are diagnostics and internal
service endpoints. Their presence does not make them supported Flutter dependencies.

## Related Detail

- [System Context](../architecture/system-context.md)
- [Responsibilities And Data Ownership](../architecture/data-ownership.md)
- [Project Structure](../developer-guide/project-structure.md)
