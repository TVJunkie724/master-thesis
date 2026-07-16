# Runtime

The normal local runtime is credential-free and consists of three application
containers plus host-run Flutter. Optional profiles add MkDocs or LaTeX without
changing application startup.

| Service | Host port | Internal port | Health/contract |
|---|---:|---:|---|
| Optimizer (`2twin2clouds`) | 5003 | 8000 | `/`, `/docs`, pricing/validation APIs |
| Deployer (`3cloud-deployer`) | 5004 | 8000 | `/`, `/docs`, project/infrastructure APIs |
| Management API | 5005 | 5005 | `/health`, `/docs` |
| MkDocs (`docs` profile) | 5010 | 8000 | documentation site |

```text
host Flutter -> localhost:5005
Management API -> http://2twin2clouds:8000
Management API -> http://3cloud-deployer:8000
```

Use `./thesis.sh` rather than memorizing raw commands. Port, Compose project, Docker
context, device, API origin, and secret-directory overrides are explicit environment
variables documented by `./thesis.sh help`.

- [Authentication](authentication.md)
- [Configuration Reference](configuration.md)
- [State and Persistence](state-and-persistence.md)
- [Operations and Logging](operations.md)
- [Troubleshooting](troubleshooting.md)
