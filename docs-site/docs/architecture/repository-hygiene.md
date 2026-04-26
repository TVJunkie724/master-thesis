# Repository Hygiene

Repository hygiene separates active product files, versioned templates, runtime artifacts, local credentials, and documentation.

## Target State

- `docs-site/` is the source of published documentation.
- `3-cloud-deployer/upload/template/` is treated as a transition template source until it can be migrated safely.
- `3-cloud-deployer/upload/` becomes runtime-only.
- Real credentials live outside versioned product paths.
- Generated Terraform state, ZIPs, build caches, and upload versions are not treated as source files.
- GitHub Issues and Milestones are the active backlog.

## Guardrail Check

Run the report-only hygiene check from the repository root:

```bash
python3 scripts/check_repo_hygiene.py
```

For machine-readable output:

```bash
python3 scripts/check_repo_hygiene.py --format json
```

For future CI enforcement:

```bash
python3 scripts/check_repo_hygiene.py --mode enforce
```

`report` mode always exits successfully and is intended for the transition phase. `enforce` exits non-zero when forbidden workspace artifacts are present.

## Credential Safety

The check reports credential file paths only. It never opens or prints credential contents.

Current valid local credentials under `3-cloud-deployer/upload/template/` must not be deleted until the credential source-of-truth phase provides a replacement path and tests.
