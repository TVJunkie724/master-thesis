# Management API

The Management API is the orchestrator boundary for the platform.

Responsibilities:

- persist users, twins, configuration, state, and deployment history,
- expose the API consumed by Flutter,
- proxy and coordinate calls to Optimizer and Deployer,
- own authentication and user-scoped Cloud Connections,
- stream deployment status and logs back to the UI.

It should not contain cloud-provider deployment logic. Provider-specific deployment behavior belongs in the Deployer.

## Implementation Notes

- split large routes into thin HTTP adapters,
- move data access into repositories,
- move state transitions into lifecycle services,
- use typed Optimizer and Deployer clients,
- centralize deployment workflows in a deployment orchestrator.

This is the main difference between a quick integration backend and the intended thesis platform: the API should coordinate domain workflows without embedding optimizer algorithms or cloud-provider deployment logic in route handlers.
