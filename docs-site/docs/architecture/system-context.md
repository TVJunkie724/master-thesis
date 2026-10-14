# System Context

The runtime operationalizes six responsibilities: acquisition, processing,
storage, Twin management, visualization/access, and independently placed
Eventing. The sixth responsibility makes delivery behavior, trust, directed
cross-cloud routes, verification, and cost explicit.

```text
                         external identity provider
                                   |
                                   v
+----------------+        +----------------------+        +----------------+
| Flutter client |------->| Management API :5005 |------->| Optimizer :5003|
| Web + desktop  | HTTP   | durable orchestration| HTTP   | cost + graph   |
+----------------+ + SSE  +----------+-----------+        +----------------+
                                     |
                                     | immutable package + operation
                                     v
                          +----------------------+
                          | Deployer :5004       |
                          | readiness + Terraform|
                          +----+---------+-------+
                               |         |
                               v         v
                         AWS / Azure / Google Cloud
```

## Public and internal boundaries

The Management API is the application API. Optimizer and Deployer schemas are
internal service contracts and diagnostics. Flutter must never call their
ports directly.

The MkDocs and LaTeX sources are documentation/research artifacts, not runtime
components. Ordinary CI is credential-free and performs no provider mutation.
