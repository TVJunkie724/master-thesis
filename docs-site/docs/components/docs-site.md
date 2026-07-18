# Documentation Site

`docs-site` is the canonical published user and developer documentation source. It uses
MkDocs Material, supports light/dark mode, full-text search, contextual assets, and
automatic local reload. Service-local READMEs remain concise entrypoints; they do not
form a parallel canonical manual.

## Structure

```text
docs-site/
  mkdocs.yml              navigation, theme, site metadata
  Dockerfile              reproducible MkDocs runtime
  docs/
    getting-started/      first-use paths
    user-guide/           user workflows
    architecture/         boundaries, flows, evolution
    contracts-and-data-flow/
                          visual cross-project contracts and runtime flows
    components/           project internals
    runtime/              configuration and operation
    cloud-setup/          provider/security setup
    developer-guide/      contracts, tests, extensions
    references/           papers, diagrams, provenance
```

Research hypotheses, theoretical evaluations, and material for later thesis synthesis
live separately under `docs/research/`. Final thesis prose lives under
`twin2multicloud-latex/`.

## Authoring Rules

- document current behavior from code/config/tests first;
- mark planned, externally gated, verification-pending, and historical claims;
- keep research hypotheses and thesis evaluations in `docs/research/`;
- do not present proposed research contributions as implemented product behavior;
- never include live credentials, account IDs, private endpoints, or ignored files;
- place diagrams beside the explanation they support;
- preserve useful ASCII diagrams in their existing context;
- use Mermaid for the dedicated cross-project contract and runtime-flow reference;
- keep each diagram paired with prose or a table that defines its exact semantics;
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
