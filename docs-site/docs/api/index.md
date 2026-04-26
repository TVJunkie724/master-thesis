# API

The Management API is the only API boundary the Flutter app should know about. Optimizer and Deployer APIs are internal service contracts used by the Management API.

## Contract Boundaries

| Contract | Consumer | Purpose |
|----------|----------|---------|
| Flutter -> Management API | Flutter UI | users, twins, configuration, optimizer requests, deployment actions, status streams |
| Management API -> Optimizer | Management API | scenario evaluation and provider placement |
| Management API -> Deployer | Management API | deployment preflight, deploy, destroy, logs, outputs |

This keeps frontend state independent from provider-specific deployment mechanics and lets the backend normalize errors, retries, and long-running deployment events.

## Local API Docs

When the stack is running, service-local OpenAPI pages are available for implementation detail:

- Management API: `http://localhost:5005/docs`
- Optimizer: `http://localhost:5003/docs`
- Deployer: `http://localhost:5004/docs`

The published docs site should describe stable contracts and behavior. Raw service-local OpenAPI output is useful for development, but it should not replace the higher-level contract explanation.

## Contract Topics

| Topic | Belongs in | Notes |
|-------|------------|-------|
| Twin configuration | Management API | UI creates and edits this through typed twin/config endpoints. |
| Cost calculation | Optimizer contract | The Management API sends scenario inputs and receives provider placement plus cost explanation. |
| Deployment manifest | Management API -> Deployer | The manifest should be the deployer input, not an ad hoc folder layout assembled by Flutter. |
| Deploy/destroy stream | Deployer contract, exposed through Management API | Long-running events should use stable event names and payload shapes. |
| Credential validation | Cloud Connection workflow | Provider-specific checks belong behind a user-scoped credential abstraction. |
| Verification and logs | Deployer contract, exposed through Management API | UI receives status, logs, outputs, and verification results through backend-owned routes. |

The old deployer docs include several legacy layer-specific and Lambda-management endpoints. Those are useful historical context, but they should not be published as the current app contract unless they are part of the canonical Management API workflow.
