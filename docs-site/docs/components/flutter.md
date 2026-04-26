# Flutter UI

The Flutter app is the user-facing interface for Twin2MultiCloud.

Responsibilities:

- collect user intent,
- display optimizer recommendations,
- let users select Cloud Connections and deployment options,
- show deployment progress, logs, verification, and outputs,
- present twin dashboards and operations.

Flutter must call only the Management API. Direct calls to the Optimizer or Deployer are architecture violations.

## Implementation Notes

- Riverpod owns app/service providers,
- BLoC owns feature state machines,
- wizard and twin views are sliced into focused feature surfaces,
- API responses become typed UI models instead of broad dynamic maps,
- dev authentication is tied to explicit dev configuration.

The UI should present a coherent twin workflow, not the internal shape of the three backend services. That is why direct Optimizer or Deployer calls from Flutter are treated as architecture violations.
