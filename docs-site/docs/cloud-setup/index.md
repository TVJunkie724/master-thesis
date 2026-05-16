# Cloud Setup

Cloud setup is one of the most fragile parts of the platform because the original projects expected broad local credentials and provider-specific manual setup. The thesis version should make cloud access explicit, reproducible, and least-privilege where possible.

## Setup Model

Each provider setup should document:

- required cloud account and billing prerequisites,
- APIs or services that must be enabled,
- one-time bootstrap permissions,
- generated deployment identity permissions,
- local development behavior,
- failure symptoms when a required provider step is missing.

The intended app workflow is Cloud Connections: a user creates or imports a provider connection, the Management API stores it as user-scoped secret material, and deployments reference that connection instead of reading random files from the workspace.

During the migration period, encrypted per-twin legacy credential columns still exist so older test data can be used deliberately. They are lower priority than Cloud Connections, are clearable through the wizard contract, and should be removed after the CloudConnection-only flow covers the thesis demo path.

## Provider Overview

| Provider | Setup focus | Important caveat |
|----------|-------------|------------------|
| AWS | IAM credentials, pricing API access, IoT Core, Lambda, DynamoDB, S3, API Gateway, TwinMaker, Managed Grafana | Managed Grafana setup depends on IAM Identity Center in the deployment region. |
| Azure | App registration/service principal, subscription access, Functions, Cosmos DB, Blob Storage, API Management, Digital Twins, Managed Grafana | Function hosting choices matter because Linux Consumption is being retired for Azure Functions. |
| GCP | project, billing, service account, enabled APIs, Pub/Sub, Cloud Functions, Firestore, Cloud Storage, API Gateway, Scheduler, Workflows | GCP currently supports the lower deployment layers; managed Digital Twin and Grafana equivalents are not first-class in the same way as AWS/Azure. |

The old documentation has two GCP paths: private account setup using an existing project, and organization setup where Terraform can create a project for a deployment. The current app should present that as an explicit setup choice, not as hidden provider behavior.

## Bootstrap Credentials

Bootstrap/admin credentials are temporary setup material. They may be used to create a constrained deployment identity for a provider, but they should not remain readable in the app and should not be persisted as the regular deployment credential.

The intended flow for creating a new deployment identity is:

1. User starts provider setup from the app.
2. User supplies temporary bootstrap/admin material for that provider.
3. The backend runs a provider-specific bootstrap script that creates or verifies the least-privilege deployment identity.
4. The generated deployment identity is stored as a Cloud Connection.
5. Bootstrap/admin material is discarded and is not available for later reads.

Real credential values must never be committed or pasted into documentation. Examples should use placeholders or schema-only files.

## Provider Material

The provider pages are migrated from the original optimizer and deployer docs as the setup flows are cleaned up. Start with [Provider Links](provider-links.md) for cloud-console, API, and pricing references that are already used by the platform.
