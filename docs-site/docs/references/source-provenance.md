# Source Provenance Appendix

The current documentation was reconstructed from the integrated codebase rather than
copied from one predecessor site. This appendix records the source families used so the
platform evolution remains auditable without duplicating every current explanation in
a migration table.

## Source Families

| Source family | Original contribution | Current treatment |
|---|---|---|
| `2-twin2clouds/docs/` | standalone Optimizer architecture, provider pricing, formulas, patterns, tests, and legacy UI | validated against the frozen pricing snapshots, calculation engine, fixed Six-layer contract, and tests; current behavior is documented under Optimizer and Pricing & Optimization |
| `3-cloud-deployer/docs/` | standalone Deployer architecture, provider setup, deployment, user functions, simulator, patterns, and CLI/API usage | validated against manifests, storage/workspaces, provider/Terraform implementations, bootstrap artifacts, and tests; legacy CLI/layer paths are historical |
| root plans, assessment, integration and frontend documents | architecture debt, intended integration, decisions, roadmaps, and refactoring evidence | used to explain motivation and evolution; never treated as stronger evidence than current code/contracts/tests |
| original papers, PDFs, and diagrams | five-layer model, project lineage, and research context | preserved centrally and linked in context from architecture and references |

## Evaluation Rule

For each material concern, evidence was resolved in this order:

1. current code, schemas, configuration, migrations, and executable contracts;
2. current deterministic tests and safe local runtime behavior;
3. merged implementation plans and GitHub issue history for decision rationale;
4. legacy HTML/Markdown and papers for historical context.

When an older source conflicts with the executable system, the current documentation
states the present behavior and records the transformation in
[Original to Current State](../architecture/evolution.md) or the relevant component.

## Historical Material

Historical implementation plans and handoffs are not part of the user workflow.
Superseded material is recoverable from Git history after its durable research
rationale has moved into the active target concept and development/decision log.
Focused future-work concepts describe possible research extensions without
promising delivery or acting as a product roadmap.
