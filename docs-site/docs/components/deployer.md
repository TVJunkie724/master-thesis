# Cloud Deployer

`3-cloud-deployer` is the infrastructure execution boundary. It validates canonical
deployment packages, provisions/destroys provider resources, packages user functions,
runs bounded status/verification probes, and owns Terraform/runtime state.

It does not own users, twin lifecycle, reusable credential storage, cost formulas, or
Flutter-facing orchestration.

## Internal Structure

| Path | Responsibility |
|---|---|
| `rest_api.py`, `src/main.py`, `src/api/` | FastAPI entrypoint and operation contracts |
| `src/core/` | context, paths, storage, registry, workspace, observability, secure files |
| `src/providers/` | provider protocol and AWS/Azure/GCP implementations |
| `src/providers/terraform/` | Terraform lifecycle, package builders, runtime outcomes |
| `src/deployment_specification/` | Manifest v2 binding, generated contract validation, typed tfvars translation |
| `src/configuration_validation/`, `src/validation/` | aggregate package/config validation |
| `src/project_archive/` | archive extraction and security policy |
| `src/operation_packages.py` | staged immutable package/token lifecycle |
| `src/log_tracing/`, `src/status/`, `src/verification/` | logs, status probes, data-flow evidence |
| `src/simulator/`, `src/iot_device_simulator/` | simulator session and provider senders |
| `templates/digital-twin/` | canonical versioned template source |
| `upload/template/` | preserved legacy/example project material, not canonical runtime truth |

## Canonical Contract

The Management API sends one validated ZIP containing `deployment_manifest.json`
version `2.0`, the frozen `ResolvedDeploymentSpecification v1`, and the exact
generated/project artifacts for an operation. The Deployer:

1. applies upload limits and safe archive policy;
2. validates the archive inventory, manifest/specification digest, provider
   path, closed-world components, dimensions, and formula/evidence bindings;
3. writes a runtime project definition;
4. stages exact bytes as an operation package;
5. returns a token and package metadata;
6. requires the token for deploy/destroy;
7. acquires it exclusively and invalidates it after use;
8. translates only allowlisted `deployable_selection` dimensions into typed,
   collision-free Terraform variables.

Legacy layer-specific endpoints and the interactive CLI are historical, not canonical
application interfaces. Legacy manifests remain inspectable through diagnostic
paths but are not deployable.

The component list contains the seven fixed baseline slots, followed by exactly
two source-owned storage transition runtimes and then any required
destination-owned cross-cloud glue. The Deployer derives transition ownership
from the selected source storage provider and rejects missing, reordered, or
destination-owned mover components. The translator emits only the registered
function runtime and schedule variables; destination writer variables remain
owned by the existing cross-cloud glue components.

## Storage And Workspace Model

```text
versioned template (read-only source)
       |
Management API archive
       v
runtime project definition ----> staged operation package
                                      |
                                      v
                               ephemeral workspace
                                      |
                         Terraform + provider SDK operations
                                      |
                     allowlisted durable outputs only
```

`ProjectStorage` centralizes validated project names and paths, blocks traversal,
protects template writes, and suppresses sensitive filenames from generic file trees
and content endpoints. Operation workspaces reject symlinks and exclude caches/build
artifacts.

Durable synchronized outputs include Terraform state/backup, IoT device auth material,
generated simulator configuration, and selected build metadata. Generated tfvars,
provider caches, and ordinary build products remain ephemeral.

## Terraform And Provider Pattern

`CloudProvider`/`BaseProvider` define provider behavior; `ProviderRegistry` resolves
AWS, Azure, and GCP implementations. `TerraformDeployerStrategy` owns common deploy and
destroy lifecycles while provider package builders generate provider-specific modules,
functions, variables, and glue artifacts.

Terraform is retained because infrastructure state, planning, idempotence, and destroy
semantics fit the problem. Files are an implementation artifact inside an isolated
operation workspace, not the user-facing source of truth.

Generated tfvars are private and deterministic. Usage tiers, account-scoped
plans, and non-deployable formula assumptions never become Terraform
variables. Unknown mappings, provider drift, digest drift, contradictory
targets, or collisions with legacy configuration fail before package,
workspace, or Terraform side effects.

The canonical transition variables are intentionally provider-specific. AWS
and Azure resource binding is complete under #132 and #133; GCP remains
governed by #120. Until the remaining provider gate passes, the platform does
not claim cross-provider end-to-end Terraform continuity for the resolved
specification.

### AWS Deployment Specification Binding

AWS Terraform consumes specification-derived values for the Lambda memory
profiles used by L1, L2, L3, L4, and cross-cloud glue, DynamoDB billing mode,
S3 cool/archive storage classes, and both source-owned mover schedules and
memory profiles. A Terraform guard rejects an active AWS component whose
required specification value is absent. Variable validation rejects values
outside the closed-world registry before provider side effects.

S3 writers and movers receive the selected storage class through runtime
environment variables. Local movers require it only when AWS owns the
destination; cross-cloud source movers leave the destination class to the
registered destination writer. Runtime code does not maintain a second
storage-class allowlist.

The baseline deploys legacy EventBridge scheduled rules for the two storage
movers. These rules are not custom event-bus ingestion, so the Optimizer does
not apply the custom event-bus row to their trigger cost. Migrating to
EventBridge Scheduler would require a distinct pricing and deployment
contract. TwinMaker account pricing plans remain account-scoped evidence, and
Managed Grafana configuration remains a tested baseline invariant rather than
a per-twin pricing selection.

### Azure Deployment Specification Binding

Azure Terraform consumes the specification-selected IoT Hub SKU and capacity,
the Consumption/Y1 Function plan selections, Cosmos DB serverless mode, Blob
account tier and replication, cool/archive access tiers, both transition
NCRONTAB schedules, and the Managed Grafana SKU. IoT Hub combination guards
enforce F1/S1/S2/S3 capacity limits before provider execution.

Blob writers and source-owned movers consume access tiers through Function App
settings. Timer decorators reference the specification-backed app settings;
hot-to-cool runs daily and cool-to-archive runs weekly under the baseline
contract. A source mover requires a local destination tier only when Azure owns
that destination.

The shared Azure L0 Function App exists only when the static function registry
requires an Azure cross-cloud receiver or when Azure owns L4 and therefore the
ADT Pusher. Its plan comes from the L4 pusher and/or glue component, whose
values must agree when they share the app. Merely selecting Azure for an
unrelated source slot does not provision an empty L0 runtime.

Azure Function Apps require a host storage account even when Azure owns no
costed cool/archive Blob slot. In that support-only case, Standard/LRS remains
an explicit infrastructure invariant. Its small provider-billed usage is not
misrepresented as a selected storage component and remains part of empirical
formula validation under #42.

## Five-Layer Mapping

| Layer | AWS | Azure | GCP |
|---|---|---|---|
| acquisition | IoT Core | IoT Hub | Pub/Sub / supported ingress path |
| processing | Lambda / Step Functions | Functions / Logic Apps | Cloud Functions / Workflows |
| storage | DynamoDB and S3 tiers | Cosmos DB and Blob tiers | Firestore and Cloud Storage tiers |
| Digital Twin management | IoT TwinMaker | Azure Digital Twins | limited/custom equivalent |
| visualization | Managed Grafana | Managed Grafana | limited/custom equivalent |

Provider capability is not uniform. Unsupported or limited L4/L5 behavior must remain
visible instead of being represented as equivalent deployment support.

`GET /capabilities/providers` publishes the provisioning-side matrix. Complete config
validation and the Terraform package builder enforce that same registry, rejecting an
unsupported row with `CAPABILITY_UNAVAILABLE` before filesystem or Terraform side
effects. See [Provider Capabilities](../architecture/provider-capabilities.md).

## Azure L4 Update Path

The canonical five-layer baseline has one executable Azure Digital Twins update path
for both same-cloud and cross-cloud assignments:

```text
selected L2 Persister (AWS, Azure, or GCP)
  |
  | HTTPS + X-Inter-Cloud-Token
  v
Azure L0 ADT Pusher
  |
  | Azure SDK + user-assigned managed identity
  v
Azure Digital Twins
```

| Component or edge | Activation | Contract |
|---|---|---|
| provider L2 Persister | selected L2 provider | writes the deterministic storage item, then performs the required ADT push |
| ADT Pusher package | `layer_4_provider == azure` | included exactly once in the Azure L0 package |
| Persister to Pusher | Azure L4 | HTTPS endpoint and token are mandatory; missing configuration fails before storage |
| Pusher to ADT | Azure L4 | managed identity and `DefaultAzureCredential`; no static Azure credential |
| failed Pusher delivery | after storage write | Persister fails so an upstream retry repeats the idempotent storage write and ADT update |

There is no active `adt-updater` Function App and no ADT Event Grid subscription in
`five-layer-baseline@1`. The current synchronous path provides visible failure and
bounded sender retries, but not durable replay or a dead-letter queue. Those delivery
capabilities remain tracked in
[#60](https://github.com/TVJunkie724/master-thesis/issues/60) and are not presented as
part of the baseline.

## User Functions And Packaging

The package builders discover typed function definitions by layer and role, generate
provider-specific archives, and preserve required wrapper/entrypoint conventions.
User code is validated before packaging. Azure blueprints and provider dependency
layouts differ from AWS Lambda and GCP Cloud Functions; see
[User Function Patterns](user-functions.md).

## Operations, Logging, And Errors

- request/operation context provides project, provider, operation ID, and phase;
- structured progress is streamed without exposing credential payloads;
- formatter and error boundaries redact sensitive values;
- Terraform subprocess outcomes become typed provider/runtime failures;
- workspace sync failures are explicit and do not hide the original operation error;
- deployment, destroy, cleanup, status, logs, simulator, and verification are distinct APIs;
- project/package contention returns conflicts instead of concurrent mutation.
- specification and manifest failures expose stable bounded codes without
  archive paths, credential fields, or provider payloads.

## Preflight And Verification

Provider permission sets are versioned and can be checked before deployment. Data-flow
verification runs explicit phases/probes with outcomes rather than treating logs as
proof. Safe unit/integration tests mock cloud boundaries; real provider proof remains
an opt-in supervised E2E activity.

Detailed Terraform drift detection requires an `X-Operation-Package` token so
it uses the same validated credential-bearing context as deployment. It never
reconstructs credentials from the durable secret-free project.

## Tests

```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/ --ignore=tests/e2e -v
```

Coverage includes API contracts, archive attacks/limits, storage, operation tokens,
workspace cleanup/sync, validation aggregation, Terraform lifecycles, providers,
permission checks, logging/redaction, simulator sessions, status, and verification.

## Extension Points

- implement/register a provider through the provider protocol and capability tests;
- add provider package-builder behavior without branching orchestration routes;
- register new user-function metadata and validate provider packaging contracts;
- add a verification probe with typed phase output and side-effect bounds;
- add durable workspace output only through the explicit sync allowlist;
- evolve manifests with a new version and compatibility/validation tests.
- extend a deployable dimension only through the canonical generated registry,
  provider Terraform variable/resource contract, and cross-stack drift tests.

## Evolution And Gaps

Originally, `upload/template` served simultaneously as template, development project,
credential location, and runtime output. Global/current-project state and multiple CLI,
layer, and REST paths made concurrent, reproducible operation difficult. The current
manifest, project storage, token, and ephemeral-workspace design establishes one path.

Provider feature parity, selected simulator behavior, durable cross-cloud replay, and
final least-privilege/live deployment evidence remain visible gaps. They must not be
hidden behind fallback endpoints or template mutation.
