# Known Limitations And Verification Status

This page records the current platform's supported boundaries and verification state
for operators and developers. It does not evaluate research hypotheses or state thesis
conclusions.

## Evidence Levels

| Level | Proves | Does not prove |
|---|---|---|
| static validation | schemas, imports, registries, syntax, architecture rules | runtime behavior |
| deterministic unit/integration | logic, contracts, failures, adapters with controlled inputs | current external provider behavior |
| local stack integration | service compatibility, DB/migrations, network contracts | provider authorization/resources |
| provider read verification | current pricing/catalog/permission responses | deployment lifecycle correctness |
| supervised live E2E | deploy, data flow, verification, destroy in one target environment | universal behavior across regions/accounts/time |

## Current Evidence

- broad Python and Flutter unit/integration coverage;
- contract tests between Management API, Optimizer, Deployer, and Flutter adapters;
- provider pricing fixtures and accepted/rejected evidence tests;
- AWS/Azure/GCP tier/formula tests;
- archive/path/symlink/upload security tests;
- migration, encryption, redaction, rate-limit, audit, and transport tests;
- deterministic offline demo plus Web, macOS, Windows, and Linux build gates;
- local credential-free Compose integration.

Cross-platform support means that the same Flutter source compiles for Web and
all three desktop operating systems on native CI runners. It does not include
signed installers, notarization, store publication, or platform certification.
The current local universal macOS build may emit an upstream `objective_c`
code-asset naming warning while still producing the release application; native
single-runner CI builds complete successfully.

## Known Limitations

### Authentication

The durable OAuth/SAML transaction, one-time exchange, provider-subject identity, and
revocable session boundaries are implemented and deterministically tested. UIBK SAML
still needs institutional registration and a supervised live callback. Local
development auth is deliberately not a production substitute.

### Credential Operations

The shared in-app guide/session lifecycle, request-only credential boundary,
generated encrypted deployment connection, disposal states, and deterministic
AWS/Azure/GCP adapters are implemented. Those adapters are an offline
simulation and create no provider identity or resource; production adapters
remain disabled and fail closed. Versioned scripts plus encrypted import remain
the supervised live-provider path. Encryption-key rotation requires explicit
re-encryption tooling.

### Provider Permissions

`thesis-demo-v1` baselines are reviewable and testable, but final least privilege is
**verification pending** until all current provider operations pass supervised live
deploy/verify/destroy without broader roles.

### Pricing

Provider catalogs can drift. Evidence/review gates reduce silent errors but do not make
catalog APIs stable. Additional service tiers and historical price analytics remain
future work. AI review is contractually prepared but not implemented as an OpenAI
runtime adapter; current responses explicitly report it disabled.

The Azure fallback-hardening slice was verified against the public Retail Prices API
on 2026-07-16. It proved an important catalog property: a `meterId` can occur on rows
with different product, SKU, price type, and price. Candidate identity therefore uses
the combined provider dimensions, while reviewed matching requires semantic fields and
stable identifiers. Exact storage values and all transfer thresholds passed provider
contract validation and cumulative calculation boundary tests. This evidence supports
the selected West Europe intents; it is not a timeless guarantee for every region or
future Azure catalog revision.

AWS, Azure, and GCP transfer catalogs now use exact reviewed tier series,
provider-native GB/GiB units, explicit routing policy, and fail-closed runtime
validation. The Optimizer now scores all complete baseline paths and applies
transfer allowances once per source-provider billing pool. This is an
estimation model, not provider invoice reconciliation: it does not import
unrelated account traffic, negotiated discounts, taxes, or billing exports.

Destination glue free tiers are aggregated across glue routes in one
calculation. Existing provider layer calculators still price several
serverless components independently, so account-wide request and compute
allowances shared between layer functions, glue functions, and unrelated
workloads are not yet reconciled as one provider invoice pool. This must be
measured and corrected, where material, under
[formula validation issue #42](https://github.com/TVJunkie724/master-thesis/issues/42)
before final thesis evaluation and supervised E2E.

Storage mover runtime ownership is now explicit in calculation, evidence,
resolved specification, Management validation, and Deployer tfvar translation.
AWS resource values are specification-bound under
[#132](https://github.com/TVJunkie724/master-thesis/issues/132), and Azure
resource/runtime values are specification-bound under
[#133](https://github.com/TVJunkie724/master-thesis/issues/133). GCP Function
profiles, Firestore mode, storage classes, transition schedules, and runtime
writers are specification-bound under
[#120](https://github.com/TVJunkie724/master-thesis/issues/120). The final
credential-free cross-stack drift gate remains
[#128](https://github.com/TVJunkie724/master-thesis/issues/128).

Azure Function Apps always require a host storage account. When Azure owns no
cool/archive Blob slot, the Deployer retains Standard/LRS as an explicit
support-resource invariant, but that account's actual operation/storage usage
is not a separate selected cost component. Empirical reconciliation remains in
[#42](https://github.com/TVJunkie724/master-thesis/issues/42).

The legacy `integrateErrorHandling` field is not an executable capability of
the current baseline. Flutter keeps it disabled and exposes historical `true`
values as legacy, non-deployable state. Optimizer, Management API, Deployer
validation, package loading, and preflight reject new or historical execution
attempts with `UNSUPPORTED_ERROR_HANDLING_TOPOLOGY` before calculation,
persistence, credential resolution, or Terraform. Event checking, notification
workflows, device feedback, and user event actions remain separate supported
capabilities. This boundary was hardened under
[#135](https://github.com/TVJunkie724/master-thesis/issues/135).

Core Azure Function HTTP adapters now use one bounded typed error contract,
response-to-log correlation, and central secret/path redaction under
[#136](https://github.com/TVJunkie724/master-thesis/issues/136). Provider
response bodies, telemetry/query payloads, signed function URLs, and raw
exceptions are excluded from their public diagnostics. Timer- and
Event-Grid-triggered functions do not expose this HTTP response contract and
instead use diagnostic-suppressed correlation logs while preserving the
original Azure retry semantics under
[#137](https://github.com/TVJunkie724/master-thesis/issues/137).

Calculation traceability now connects the optimization profile and selected path to
provider pricing contracts, source classifications, formula bindings, evidence
references, verification gates, and bounded result scopes. This improves auditability;
it is not billing reconciliation. Where the calculator exposes only a component or
layer total, field-level records deliberately identify the value as shared and
non-additive instead of inventing false per-field precision. Registry evidence
references likewise do not claim to be exact runtime selected catalog rows.

### Provider Parity

AWS, Azure, and GCP do not expose equivalent managed Digital Twin and
visualization services. The profile-neutral capability contract therefore
keeps generic GCP L4/L5 unsupported. The active Five-layer v2 profile closes
that bounded PoC path through a separately registered provider-hosted
composition: BifroMQ/GKE plus Pub/Sub, Firestore Native Standard edition, a
typed Cloud Run reader, a bounded Cloud Run Twin API/Explorer, and Grafana on
GKE. When GCP owns L3 and L4, they share one deployment database with separate
collections and identities rather than claiming strict collection-level IAM.

All three v2 provider bundles and cross-cloud adapters are contract-tested
offline, but browser access, provider policy, quota, and live capacity remain
supervised gates. They cannot be presented as deployment-ready. See
[Provider Capabilities](../architecture/provider-capabilities.md).
Firestore L3 uses scenario-derived timestamp shards; Firestore L4 is
deliberately limited to point and one-hop relationship queries. Arbitrary graph
algorithms are not supported. The current Pub/Sub acquisition path and retired
`google.cloud.iot_v1` feedback template do not provide this target today.

The successor target keeps L3 hot and L5 provider-local while allowing L4 to
use any provider. It exposes one raw-history visualization read and carries
selected state/model/relationship changes from L3 to L4 through a typed
projection event. L4-to-L5 Twin context, 3D scenes, cross-provider raw
visualization, historical Twin graph analysis, Spanner Graph, ADX migration,
dedicated Grafana node pools, and storage-specific CDC/outbox/broker pipelines
remain outside Five-layer v2 unless a later versioned requirement justifies
them.

Azure retains Cosmos DB for L3 hot. Small and Medium select serverless; Large
is admissible only after calculated autoscale RU/s, hot-storage minimum,
20-GB-per-device logical-partition, and partitioned-mover proofs pass. ADX
would provide stronger native time-series analytics and Managed Grafana
integration, but selecting it would change a second experimental variable.
Cosmos reader latency and autoscale behavior remain `live_capacity_pending`.

The GCP Infinity datasource similarly requires a pre-live-readiness
`Save & test` plus bounded raw and hourly-rollup queries through the typed
Cloud Run reader. The offline target remains `live_capacity_pending`. The
reader has access only to the named L3 Firestore database; the Grafana pod
receives no Firestore role or service-account JSON key.

AWS and Azure currently use the Grafana JSON API datasource only as a
time-bounded PoC dependency. Grafana has deprecated it and ends support on
2027-02-01. The planned implementation therefore freezes and rechecks the
managed-provider catalog/support evidence and rejects the affected bundle on
absence, incompatibility, or support expiry; it does not silently change
storage or datasource technology.

GCP Grafana uses a TLS `LoadBalancer` Service restricted to configured source
CIDRs, generated access credentials, and a deployment-generated certificate
whose fingerprint is returned as evidence. It deliberately does not add public
DNS, a public-CA certificate, or IAP. Browser trust of the recorded certificate
and CIDR reachability remain supervised PoC gates. No custom unsigned
Twin/scene plugin is selected.

### Simulator And Live Data Flow

Simulator/session architecture exists, but selected bugs and provider-specific behavior
need further hardening. A successful simulator UI interaction is not equivalent to a
complete production telemetry proof.

### Persistence And Scale

SQLite is appropriate to the local single-node runtime. Multi-replica production
requires external relational storage, coordinated migrations, backups, and operations.

## Quality Terminology

“Enterprise-grade” in this repository means explicit ownership, typed contracts,
fail-closed security, auditability, broad deterministic tests, and visible limitations.
It does not mean unsupported claims of universal provider correctness or production
scale without external evidence.
