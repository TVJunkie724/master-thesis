# Results and Limits

Twin2MultiCloud is a research PoC. This page distinguishes implemented
mechanisms from activation and live evidence; it is not a claim of production readiness.

## What the PoC demonstrates

| Result | Evidence available in the repository | Limit |
|---|---|---|
| Unified configuration and review | Flutter/demo tests and typed Management API contracts | demo data proves UI behavior, not backend or cloud execution |
| Cost-aware provider placement | complete-path, formula, tier and pricing-evidence tests | estimated costs under recorded assumptions, not provider invoices |
| Reproducible deployment inputs | immutable run/specification contracts, Manifest v3, graph and Terraform binding tests | static/mock validation is not proof of live provisioning |
| Explicit state and credential ownership | persistence, migration, encryption, access-control and redaction tests | local SQLite and operator-managed keys; no multi-replica production setup |
| Cross-platform client | Web/macOS/Windows/Linux build gates | no signed installers, notarization or platform certification |

[Testing](../developer-guide/testing.md) describes how to reproduce the safe
checks. A test's presence is not evidence that it passed on an arbitrary
checkout; record the revision and output when using it as thesis evidence.

## Current execution boundary

- **Implemented:** architecture-profile APIs, immutable architecture persistence,
  Optimizer profile resolution and Deployer graph compilation.
- **Default off:** `ARCHITECTURE_PROFILE_RESOLUTION_ENABLED` in Management and
  Optimizer. New deployment packages require Manifest v3 and a resolved
  architecture; starting the default stack does not enable that path.
- **Contract support:** AWS/Azure baseline profiles are marked supported; GCP
  L4/L5 remain unsupported. Support flags do not establish live provider parity.
- **Open runtime gap:** Grafana currently binds to L3 hot readers, while the
  modeled final edge is L4→L5. See [Current Deployment Graph](../architecture/current-deployment-graph.md).
- **Planned:** the Flutter architecture-profile workflow and executable Eventing
  extension. Research decisions and offline scenarios are not runtime support.
- **Verification pending:** final supervised deploy, data-flow verification and
  destroy for the current implementation.

The [Architecture Profiles reference](../contracts-and-data-flow/architecture-profiles.md)
defines the contracts. Historical live E2E results must retain their own
revision/scenario context and cannot certify later changes.

## Practical limitations

| Area | Current limit |
|---|---|
| Authentication | OAuth/SAML session flow is implemented; UIBK still needs institutional registration and a live callback |
| Cloud setup | versioned CLI bootstrap and Management plan/import API exist; Flutter does not expose that bootstrap workflow |
| Credentials | encryption-key rotation requires explicit re-encryption; retain the original key with database backups |
| Permissions | `thesis-demo-v1` is a reviewed baseline; final least privilege still needs live provider evidence |
| Pricing | catalogs can drift; ambiguous refreshes require review; AI-assisted runtime review is not implemented |
| Error handling | `integrateErrorHandling=true` is rejected as `UNSUPPORTED_ERROR_HANDLING_TOPOLOGY`; event checking and notification behavior are separate |
| Simulator | existing controls and verification probes do not by themselves prove complete cloud telemetry delivery |
| Operations | single-node local runtime; external storage, replication and production operation are outside the demonstrated scope |

## Cost interpretation

Transfer pricing uses reviewed routes, native GB/GiB units and allowances
pooled by source provider. Destination glue allowances are aggregated across
glue routes. Layer functions and unrelated account workloads are not reconciled
into one account-wide request/compute allowance pool.

Azure Function host storage remains necessary even when Azure owns no
cool/archive slot; its usage is not a separate selected cost component.
Negotiated discounts, taxes, unrelated account traffic and billing exports
are also outside the model. These limits matter when comparing estimates to
invoices; empirical reconciliation remains in
[formula validation #42](https://github.com/TVJunkie724/master-thesis/issues/42).

Trace records distinguish shared layer/component totals from additive
field-level costs. Do not sum shared trace values or treat a registry reference
as an exact selected provider row. See [Optimizer](../components/optimizer.md).

## Reading evidence

| Evidence | Supports |
|---|---|
| schema/static checks | structure, mappings and architecture rules |
| deterministic tests | logic and failure behavior under controlled inputs |
| local integration | service compatibility and persistence |
| provider reads | the selected catalog/permission response at that time |
| supervised live E2E | deployment, data flow and cleanup in the recorded environment |

For scientific interpretation, keep scenario, commit, configuration, pricing
snapshot and verification output together. Evaluation and observability
concepts remain in the repository's research notes until implemented and measured.
