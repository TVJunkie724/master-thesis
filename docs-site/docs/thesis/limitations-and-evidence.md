# Limitations And Evidence

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

Versioned provider bootstrap scripts and encrypted import are implemented. Fully
request-scoped in-app administrator bootstrap is not yet the canonical runtime path.
Encryption-key rotation requires explicit re-encryption tooling.

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

Calculation traceability now connects the optimization profile and selected path to
provider pricing contracts, source classifications, formula bindings, evidence
references, verification gates, and bounded result scopes. This improves auditability;
it is not billing reconciliation. Where the calculator exposes only a component or
layer total, field-level records deliberately identify the value as shared and
non-additive instead of inventing false per-field precision. Registry evidence
references likewise do not claim to be exact runtime selected catalog rows.

### Provider Parity

AWS, Azure, and GCP do not expose equivalent managed Digital Twin and visualization
services. The executable capability contract marks GCP L4/L5 unsupported and planned;
those rows cannot enter scoring or deployment. AWS/Azure L4/L5 are contract-tested but
still await final supervised live-cloud E2E evidence. Cross-cloud glue behavior remains
partly planned. See [Provider Capabilities](../architecture/provider-capabilities.md).

### Simulator And Live Data Flow

Simulator/session architecture exists, but selected bugs and provider-specific behavior
need further hardening. A successful simulator UI interaction is not equivalent to a
complete production telemetry proof.

### Persistence And Scale

SQLite is appropriate to the thesis/local single-node runtime. Multi-replica production
requires external relational storage, coordinated migrations, backups, and operations.

## Interpretation Rule

“Enterprise-grade” in this repository means explicit ownership, typed contracts,
fail-closed security, auditability, broad deterministic tests, and visible limitations.
It does not mean unsupported claims of universal provider correctness or production
scale without external evidence.
