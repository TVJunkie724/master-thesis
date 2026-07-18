# Resolved Deployment Review

## Purpose

The configuration workspace exposes the exact immutable cloud-resource
selection produced by the Optimizer without allowing Flutter to become a
second deployment source of truth.

## Data Flow

```text
workload inputs
  -> Management API creates Optimizer run
  -> Optimizer returns result + ResolvedDeploymentSpecification v1
  -> Management validates and persists result/specification atomically
  -> Flutter requests whole-run selection
  -> Management verifies pricing and account context
  -> selected run gates deployment preparation
  -> final summary renders the frozen resources read-only
```

Flutter calls only `ManagementApi`. It never calls the Optimizer or Deployer
directly and never sends provider resource values back to the server.

## State Contract

| Review state | Meaning | User action |
| --- | --- | --- |
| `absent` | no modern calculation run exists | calculate |
| `selectionRequired` | a valid current run exists but is not selected | verify selection |
| `selecting` | Management is verifying the whole run | wait |
| `ready` | the latest supported run is selected | continue |
| `failed` | selection verification failed | retry or recalculate |
| `legacy` | the saved run predates the specification contract | recalculate |
| `unsupported` | the app cannot consume the saved schema version | recalculate with a compatible app |

The newest run is authoritative for review. An older selection never makes a
newer run deployable. Direct navigation and final completion both require the
same `ready` projection.

## Display Contract

The recommendation task shows only a compact selection status. The final
summary shows:

- all seven architecture slots in stable order;
- required transition and cross-cloud runtime components;
- provider and service identity;
- deployable dimensions such as SKU, capacity, memory, storage class, mode,
  replication, or schedule.

Technical evidence is collapsed initially. It contains the full digest,
architecture and optimization contracts, catalog references, component IDs,
formula/evidence references, and dimension classifications.

The classification determines meaning:

| Classification | Meaning |
| --- | --- |
| `deployable_selection` | exact value translated into an allowlisted Terraform target |
| `usage_tier` | pricing behavior used by a formula, not a Terraform SKU |
| `account_scope` | provider-account state that cannot be changed per twin |
| `non_deployable_assumption` | disclosed calculation input that Terraform cannot enforce |

No credential, provider payload, endpoint, unrestricted JSON, or token belongs
in this view.

## Failure Behavior

- Known v1 payloads are strictly typed and digest-verified.
- List/detail, run/twin identity, compatibility, timestamp, and selection
  mismatches fail as API-contract errors.
- Selection failures preserve the cost result for diagnosis but block
  deployment preparation.
- Any changed workload input invalidates the result, optimization projection,
  and deployment run together. Late calculation or selection responses are
  ignored.
- Duplicate calculate and selection commands are ignored while an operation is
  active; save, finish, and navigation are also blocked during verification.
- Legacy and future-version runs remain inspectable without becoming
  deployable.

Demo runtimes load a byte-identical generated copy of the canonical mixed
provider contract fixture. Scenario and specification assets bypass the global
asset Future cache so sequential demo runtimes remain isolated in one process.

## Extension Boundary

To add a specification version:

1. advance the canonical repository contract and generated service copies;
2. add a new typed Flutter parser without weakening v1 parsing;
3. extend the neutral `ResolvedDeploymentReview` projection;
4. implement both network and demo adapter behavior;
5. add model, adapter, BLoC, journey, responsive widget, and contract fixtures.

Do not add provider-specific resource editing to Flutter. New provider values
must originate in the Optimizer deployment registry and pass Management and
Deployer validation before they are rendered.

## Verification

```bash
cd twin2multicloud_flutter
flutter analyze
flutter test
flutter build web --release --dart-define-from-file=config/dev.example.json
flutter build macos --release --dart-define-from-file=config/dev.example.json
```
