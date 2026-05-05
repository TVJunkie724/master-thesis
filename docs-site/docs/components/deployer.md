# Cloud Deployer

The Deployer is the infrastructure execution engine.

Responsibilities:

- validate deployer-specific configuration,
- materialize deployment workspaces,
- run Terraform-first deployment and destroy workflows,
- manage provider-specific packaging and post-Terraform operations,
- return structured deployment outputs and logs.

It should not own user lifecycle state. The Management API owns user/twin state and calls the Deployer through typed contracts.

## Implementation Notes

- keep one canonical provider/Terraform path,
- remove or isolate legacy deployment paths,
- replace global project state with explicit deployment context,
- separate versioned templates from runtime upload artifacts,
- support credential preflight checks and least-privilege bootstrap flows.

Terraform remains the infrastructure execution layer, but it should be driven from explicit manifests and generated workspaces. The template directory is source material; deployment output is runtime state.

The canonical default template is `3-cloud-deployer/templates/digital-twin/`. Runtime project folders belong under `3-cloud-deployer/upload/<project-name>/`. The old `upload/template/` path is treated as a local legacy fallback only and must not be mutated by normal deployment flows.

## Provider Responsibilities

The provider modules translate one conceptual Digital Twin deployment into provider-specific resources:

| Layer | AWS examples | Azure examples | GCP examples |
|-------|--------------|----------------|--------------|
| Data acquisition | IoT Core | IoT Hub | Pub/Sub or HTTP ingress |
| Processing | Lambda | Azure Functions | Cloud Functions |
| Storage | DynamoDB, S3 | Cosmos DB, Blob Storage | Firestore, Cloud Storage |
| Management | IoT TwinMaker | Azure Digital Twins | limited managed equivalent |
| Visualization | Managed Grafana | Managed Grafana | limited managed equivalent |

Cross-cloud boundaries require connector or wrapper functions. Those functions are part of the deployer implementation detail, while the Management API should still see one deployment workflow.
