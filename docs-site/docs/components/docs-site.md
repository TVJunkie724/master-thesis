# Documentation Site

`docs-site` is the canonical published documentation source. It uses MkDocs Material,
supports light/dark mode, full-text search, contextual assets, and automatic local
reload. Service-local READMEs remain concise entrypoints; they do not form a parallel
canonical manual.

## Structure

```text
docs-site/
  mkdocs.yml              navigation, theme, site metadata
  Dockerfile              reproducible MkDocs runtime
  docs/
    getting-started/      first-use paths
    user-guide/           user workflows
    architecture/         boundaries, flows, evolution
    components/           project internals
    runtime/              configuration and operation
    cloud-setup/          provider/security setup
    developer-guide/      contracts, tests, extensions
    thesis/               decisions, evidence, limitations
    references/           papers, diagrams, provenance
```

## Authoring Rules

- document current behavior from code/config/tests first;
- mark planned, externally gated, verification-pending, and historical claims;
- never include live credentials, account IDs, private endpoints, or ignored files;
- place diagrams beside the explanation they support;
- prefer ASCII for maintained flows and existing images for historical/contextual value;
- link exact API fields to live OpenAPI rather than copying large drifting schemas;
- use GitHub issues for active work, not new `future-work.md` backlogs;
- update provenance when historical source material is revised or retired.

External `http`/`https` links are decorated by `javascripts/external-links.js` to open
in a new tab with safe `rel` attributes. Internal links remain same-tab navigation.

## Local Preview And Verification

```bash
./thesis.sh docs up
./thesis.sh docs logs
./thesis.sh docs down
```

The site runs on `http://localhost:5010` by default and reloads Markdown changes.
Production-style verification uses a strict build:

```bash
docker compose --profile docs run --rm docs mkdocs build --strict
```

## Evolution

The original projects contained independent HTML sites, Markdown investigations,
future-work files, implementation notes, and duplicated PDFs/diagrams. They remain
provenance until every concern has a current target or explicit historical disposition.
The [Source Provenance Appendix](../references/source-provenance.md) records the source
families and evaluation rules; the site is not a blind file dump.
