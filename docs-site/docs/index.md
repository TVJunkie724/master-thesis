# Twin2MultiCloud Documentation

Twin2MultiCloud is a thesis proof of concept for configuring, cost-optimizing,
deploying, and verifying one standalone Six-layer Digital Twin architecture
across AWS, Azure, and Google Cloud.

It is intentionally not a general cloud-management product. The implemented
scope exists to produce traceable evidence for operationalization, functional
provider comparability, cost effects, provider-local baselines, and Eventing as
an explicit responsibility.

## Current boundary

| Area | Implemented offline | Still requires supervised live evidence |
|---|---|---|
| Architecture | fixed `six-layer-eventing@1` contract | real regional service capacity |
| Optimization | cost-only strategy with full trace | sensitivity interpretation against live observations |
| Pricing | frozen, cited, hashed snapshots | no live refresh is part of the PoC |
| Credentials | encrypted deployment CloudConnections, graph readiness, bounded repair | real account permissions and external prerequisites |
| Deployment | immutable operations, packages, SSE replay, verification and cleanup contracts | provider Apply/Destroy results |
| Evaluation | deterministic fixtures and coverage design | three local plus six directed multi-cloud Small runs |

The historical Five-layer calculation remains Optimizer-only comparison
evidence. It cannot be selected or deployed.

## Choose a path

| Goal | Start here |
|---|---|
| run a safe local stack or offline demo | [Getting Started](getting-started/index.md) |
| perform the supported workflow | [User Guide](user-guide/index.md) |
| understand ownership and boundaries | [Architecture](architecture/index.md) |
| change one service | [Components](components/flutter.md) |
| inspect contracts and evidence flow | [Contracts & Data Flow](contracts-and-data-flow/index.md) |
| prepare supervised provider access | [Cloud Setup](cloud-setup/index.md) |
| test or troubleshoot | [Runtime](runtime/index.md) and [Developer Guide](developer-guide/index.md) |

## Service boundary

```text
Flutter UI
    |
    | HTTP(S) + SSE
    v
Management API  --------->  Cost Optimizer
    |
    +-------------------->  Cloud Deployer  -----> AWS / Azure / GCP
```

Flutter calls only Management. Management owns user/Twin state and durable
workflow evidence. The Optimizer owns cost semantics and the immutable
resolution. The Deployer owns provider readiness, execution, verification, and
cleanup.

Offline tests, mocks, and fixtures never count as live-cloud validation.
