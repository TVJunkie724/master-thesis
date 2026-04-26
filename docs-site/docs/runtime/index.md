# Runtime And Deployment State

The runtime model has to separate three concerns that were previously mixed together: local services, cloud credentials, and generated deployment files.

## Local Services

The default Compose stack runs the platform services needed for development:

| Service | Responsibility | Port |
|---------|----------------|------|
| Management API | UI-facing orchestration boundary | 5005 |
| Twin2Clouds Optimizer | cost and provider-placement calculation | 5003 |
| Cloud Deployer | infrastructure deploy/destroy executor | 5004 |
| Docs Site | MkDocs documentation server | 5010 |

The docs site runs behind the `docs` profile so documentation can reload independently while Markdown files are edited.

## Deployment Files

Versioned templates and generated deployment workspaces must not be treated as the same thing.

- Template files describe reusable provider deployment structure.
- Deployment manifests describe one requested deployment.
- Generated workspaces contain concrete Terraform files, function packages, and provider outputs for one deployment run.

The Deployer should materialize a fresh workspace from templates and a manifest, then return structured outputs to the Management API. A workspace can be inspected for debugging, but it should not become the source of truth for a twin.

## Credentials

The target source of truth is a user-scoped Cloud Connection stored through the Management API. The local repository should not contain live credentials as normal development state.

For real cloud deployments, credentials should enter the system through an explicit cloud workflow: the user provides temporary bootstrap/admin credentials, the app creates or imports a least-privilege deployment identity, stores only that resulting connection, and discards bootstrap material. The default local stack should continue to work without real cloud credentials.

Some legacy files still exist while the migration is in progress, especially around deployment templates and test material. They should be handled as transitional artifacts and never documented with real credential values.
