# System boundaries

```text
single PoC user
      |
      v
Flutter ----> Management API
                 |       |
                 v       v
             Optimizer  Deployer ----> AWS / Azure / GCP
```

| Component | Owns | Does not own |
|---|---|---|
| Flutter | typed interaction state and presentation | durable evidence, provider SDKs, direct Optimizer/Deployer calls |
| Management | Twins, encrypted CloudConnections, calculation/operation evidence and public workflow | pricing formulas or Terraform execution |
| Optimizer | frozen pricing catalogs, workload normalization, capability admission, cost formulas and resolved graph | users, provider mutation or deployment state |
| Deployer | package validation, graph requirements, Terraform, runtime probes and cleanup | optimization decisions or application-user state |

The public user workflow ends at Management. Optimizer and Deployer are
internal research services even when their local development ports are
reachable.

The default runtime is credential-free. Live provider credentials cross only
the explicitly supervised Management-to-Deployer operation boundary and are
never included in portable Twin data or research evidence.

Provider pricing APIs are not runtime dependencies of the thesis workflow.
Calculations use frozen, cited and hashed snapshots so all scenarios use the
same evidence date.
