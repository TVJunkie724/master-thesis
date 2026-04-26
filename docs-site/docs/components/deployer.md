# Cloud Deployer

The Deployer is the infrastructure execution engine.

Responsibilities:

- validate deployer-specific configuration,
- materialize deployment workspaces,
- run Terraform-first deployment and destroy workflows,
- manage provider-specific packaging and post-Terraform operations,
- return structured deployment outputs and logs.

It should not own user lifecycle state. The Management API owns user/twin state and calls the Deployer through typed contracts.

Current architecture direction:

- keep one canonical provider/Terraform path,
- remove or isolate legacy deployment paths,
- replace global project state with explicit deployment context,
- separate versioned templates from runtime upload artifacts,
- support credential preflight checks and least-privilege bootstrap flows.
