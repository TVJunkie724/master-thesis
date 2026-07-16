# Twin2MultiCloud Documentation

Twin2MultiCloud is an integrated thesis platform for configuring, cost-optimizing,
deploying, and inspecting five-layer Digital Twins across AWS, Azure, and Google
Cloud. This site is the canonical human-readable description of the application.

## Choose Your Path

| You want to... | Start with |
|---|---|
| run a clean clone or the offline demo | [Getting Started](getting-started/index.md) |
| use the UI and understand its workflows | [User Guide](user-guide/index.md) |
| understand the platform and its data flows | [Architecture](architecture/index.md) |
| work on a particular service | [Components](components/flutter.md) |
| configure credentials or a cloud provider | [Cloud Setup](cloud-setup/index.md) |
| operate, test, or troubleshoot the stack | [Runtime](runtime/index.md) and [Developer Guide](developer-guide/index.md) |
| understand what changed from the original projects and why | [Original to Current State](architecture/evolution.md) |

## Current Capability Status

| Area | Status | Meaning |
|---|---|---|
| Local integrated runtime | **Implemented** | One root script starts the credential-free backend and Flutter client. |
| Offline UI demonstration | **Implemented** | Deterministic in-memory adapters exercise the UI without Docker or cloud access. |
| Cost optimization | **Implemented** | Cost is enabled; other objectives are explicit extension declarations. |
| Provider pricing review | **Implemented** | Refresh, evidence, candidate review, and persisted decisions use the Management API. |
| Deployment orchestration | **Implemented** | Manifest-backed operation packages and isolated workspaces drive deployment. |
| Production credential controls | **Implemented** | Encryption, ownership, transport checks, rate limits, redaction, and audit events exist. |
| UIBK production login | **Externally gated** | Final SAML registration requires the UIBK/ACOnet identity team. |
| Provider least privilege | **Verification pending** | Versioned baselines exist; final live-cloud evidence remains supervised work. |
| Live-cloud E2E proof | **Verification pending** | Excluded from safe default tests because it may create billable resources. |

Status labels are used consistently throughout this site:

- **Implemented**: present in code and covered by safe verification.
- **Externally gated**: completion requires an external administrator or system.
- **Verification pending**: code exists, but final supervised evidence is outstanding.
- **Planned**: not implemented and tracked in GitHub.
- **Historical**: retained to explain provenance, not current behavior.

## Canonical Boundary

```text
Flutter UI
    |
    | HTTP(S) + SSE
    v
Management API  --------->  Optimizer
    |
    +-------------------->  Deployer  -----> AWS / Azure / GCP
```

Flutter talks only to the Management API. The Management API owns users, twins,
configuration, durable workflow state, and orchestration. The Optimizer owns
pricing and calculation semantics. The Deployer owns provider execution.

## Documentation Truth

Current code, schemas, configuration, migrations, and tests take precedence over
older prose. The original HTML pages remain historical sources; their use is summarized
in the [Source Provenance Appendix](references/source-provenance.md).
