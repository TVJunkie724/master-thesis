# Twin2MultiCloud: PoC Purpose and Boundaries

Twin2MultiCloud connects a Digital Twin cost optimizer and a cloud deployer
through a Management API and Flutter UI. The research question is whether a
costed provider assignment can become a functionally complete, traceable and
reproducible deployment.

## Model and responsibilities

The scientific baseline has five responsibilities: acquisition, processing,
storage, twin management and visualization. Hot, cool and archive storage
produce seven optimization slots. The Optimizer evaluates complete provider
paths, including transfer and required runtime costs.

| Project | Owns |
|---|---|
| Flutter | workload input, configuration workflow and result review |
| Management API | users, twins, Cloud Connections, immutable calculation evidence and lifecycle |
| Optimizer | pricing evidence, formulas, candidate admission and cost ranking |
| Deployer | graph compilation, packages, Terraform and provider operations |

Flutter calls only Management. Provider formulas stay in the Optimizer;
infrastructure execution stays in the Deployer.

## Implemented chain

```text
workload + exact pricing references
  -> complete-path cost result
  -> immutable calculation run and deployment specification
  -> selected resolved architecture (when profile resolution is enabled)
  -> Manifest v3
  -> Deployer graph, packages and Terraform inputs
  -> operation evidence
```

Configuration, calculation, selection and deployment are separate steps.
Clients cannot replace frozen pricing or deployment decisions with editable
provider fields. Credentials are resolved privately from user-owned Cloud
Connections at the operation boundary.

## Current limits

Architecture-profile resolution defaults to off. Graph compilation and
AWS/Azure profile mappings are implemented; GCP L4/L5 and a complete current
live-cloud proof remain unavailable. Grafana still uses an L3-reader path
rather than the modeled L4→L5 binding. Eventing is research/decision work,
not an enabled extra baseline layer.

The canonical [Results and Limits](docs-site/docs/runtime/known-limitations.md)
page records execution and evidence boundaries. [System Context](docs-site/docs/architecture/system-context.md)
and [Engineering Decisions](docs-site/docs/architecture/engineering-decisions.md)
explain the design. [Research Notes](docs/research/README.md) hold hypotheses,
comparisons and evaluation plans; they do not establish implemented behavior.
