# Twin2MultiCloud Documentation

This site is the canonical published documentation source for the Twin2MultiCloud platform.

Twin2MultiCloud combines:

- the Flutter user interface,
- the Management API as orchestrator,
- Twin2Clouds as cost optimizer,
- the Cloud Deployer as infrastructure executor,
- the thesis source in LaTeX.

The documentation is intentionally centralized here so project-local docs can become developer notes, historical originals, or temporary migration sources instead of competing published documentation roots.

## Current Documentation Areas

- **Architecture**: target architecture, cross-service responsibilities, deployment state, and roadmap decisions.
- **Components**: Management API, Flutter UI, Optimizer, and Deployer responsibility boundaries.
- **Runtime**: Docker profiles, credential source of truth, deployment manifests, and workspaces.
- **User Guide**: user-facing workflows for creating, configuring, deploying, and operating digital twins.
- **Cloud Setup**: provider setup, credentials, bootstrap, and least-privilege guidance.
- **API**: Management API, Optimizer, and Deployer contracts.
- **References**: scientific papers and thesis PDFs referenced by the documentation.
- **Archive**: historical docs retained for traceability after migration.

## Local Development

Run the docs site from the repository root:

```bash
docker compose up docs
```

The site is available at `http://localhost:5010`. Markdown changes under `docs-site/docs/` reload automatically in development mode.
