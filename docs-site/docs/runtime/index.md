# Runtime And Deployment State

This section will describe the canonical runtime model.

Planned content:

- Docker Compose profiles for default, development, demo, and cloud integration.
- Credential source-of-truth behavior.
- Cloud Connection lifecycle.
- Deployment manifest generation.
- Ephemeral deployment workspaces.
- Separation between versioned templates and generated runtime artifacts.

The target state is that the default local stack starts without real cloud credentials. Cloud deployments become an explicit profile and workflow, not an accidental default.
