# System Context

The platform implements the five-layer model from the
[EDTConf'25 engineering paper](../references/EDT_25__CloudDT_engineering.pdf):
data acquisition, processing, storage, Digital Twin management, and visualization.

![Five-layer architecture](../references/diagrams/layer_architecture_overview_1763755975125.png)

## Containers And External Systems

```text
                         external identity provider
                                   |
                                   | OAuth/SAML (production)
                                   v
+----------------+        +----------------------+        +----------------+
| Flutter client |------->| Management API :5005 |------->| Optimizer :5003|
| Web/all desktop| HTTP   | durable orchestration| HTTP   | pricing + cost |
+----------------+ + SSE  +----------+-----------+        +----------------+
                                     |
                                     | manifest/archive + operation requests
                                     v
                          +----------------------+
                          | Deployer :5004       |
                          | Terraform/providers  |
                          +----+---------+-------+
                               |         |
                         SDK/API|         |Terraform/API
                               v         v
                         AWS / Azure / Google Cloud
```

The documentation container is operationally separate and serves only the MkDocs
site. The LaTeX source is intentionally outside this application architecture.

## Runtime Topology

| Runtime | Location | Persistence |
|---|---|---|
| Flutter | host process | no application database; auth token held in memory |
| Management API | Compose container | SQLite bind mount and upload directory |
| Optimizer | Compose container | versioned YAML registry and fetched JSON artifacts in project bind mount |
| Deployer | Compose container | source bind mount plus dedicated runtime-state volume |
| Docs | optional Compose profile | source bind mount; no runtime state |

Compose uses one bridge network. Internal calls use service names, while Flutter
uses the host-published Management API port.

## Public And Internal Boundaries

The Management API is the application API. Optimizer and Deployer OpenAPI schemas
are internal service contracts and developer diagnostics. Exposing them on local
ports does not make them valid Flutter dependencies.
