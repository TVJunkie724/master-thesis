# Twin2MultiCloud Documentation

This site documents the Twin2MultiCloud thesis platform for thesis writing and for developers working with the repository.

Twin2MultiCloud combines:

- the Flutter user interface,
- the Management API as orchestrator,
- Twin2Clouds as cost optimizer,
- the Cloud Deployer as infrastructure executor,
- the thesis source in LaTeX.

The documentation is intentionally centralized here so setup guides, architecture notes, cloud-provider instructions, roadmap decisions, and project-specific internals are easy to find. It replaces the scattered HTML and service-local documentation step by step, while keeping the original project context visible where it helps explain the thesis work.

## How To Read This Site

- **Architecture** explains the integrated platform, the original bachelor-project origins, and the active debt-reduction roadmap.
- **Components** documents what the Flutter UI, Management API, Optimizer, and Deployer are responsible for, including implementation details that differ from the original projects.
- **Runtime** describes how the local Docker stack, generated deployment files, credentials, and deployment state fit together.
- **Developer Guide** contains the practical project setup, service ports, and safe verification commands.
- **User Guide** follows the intended application workflow from twin creation to deployment and operation.
- **Cloud Setup** collects provider setup, bootstrap, credentials, and least-privilege notes.
- **API** documents the service contracts and keeps the Management API as the user-interface boundary.
- **References** preserves the papers, thesis PDFs, diagrams, and external links used by the documentation.

During the migration, some detailed provider instructions still live in the original service docs. When content moves here, it should be rewritten into the surrounding topic instead of copied as an isolated archive page.

## Local Development

Run the docs site from the repository root:

```bash
docker compose --profile docs up docs
```

The site is available at `http://localhost:5010`. Markdown changes under `docs-site/docs/` reload automatically in development mode.

For the full repository setup, start with [Project Setup](developer-guide/setup.md).
